"""Grounded answers (docs/spec/05-generation.md): the model proposes, the code verifies."""

import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import cast

from soundline.application.model_output import InvalidOutputError, parse_json_object
from soundline.application.ports import GenerationRequest, LanguageModel, Retriever
from soundline.application.prompts import (
    CONDENSE_PROMPT,
    DEFAULT_PROMPT,
    PromptTemplate,
    condense_request,
    grounded_request,
)
from soundline.domain.answers import (
    AbstentionReason,
    Answer,
    AnswerStatus,
    Citation,
    Claim,
    Conflict,
    QueryInfo,
    conflict_among,
    render,
)
from soundline.domain.chunks import Chunk
from soundline.domain.conditions import missing_conditions
from soundline.domain.conversation import Turn, pack_history
from soundline.domain.errors import GenerationError, ProviderUnavailableError, SoundlineError
from soundline.domain.events import (
    AnswerCompleted,
    AskEvent,
    ClaimVerified,
    RetrievalCompleted,
    StreamError,
)
from soundline.domain.pdf import page_at
from soundline.domain.usage import Price, StageUsage, Usage, price_for
from soundline.domain.verification import Method, verify_quote


@dataclass(frozen=True)
class _ModelClaim:
    text: str
    citations: list[tuple[str, str]]  # (evidence_id, quote)


@dataclass(frozen=True)
class _ModelOutput:
    claims: list[_ModelClaim]
    insufficient_evidence: str | None
    lenient: bool
    conflicts: list[tuple[str, list[str]]] = field(default_factory=list[tuple[str, list[str]]])
    """(about, evidence IDs) as the model reported them (GEN-090)."""


@dataclass(frozen=True)
class GenerationSettings:
    """The `[generation]` configuration section (docs/spec/09-configuration.md)."""

    k: int = 5
    prompt: PromptTemplate = DEFAULT_PROMPT  # GEN-014
    condense_prompt: PromptTemplate = CONDENSE_PROMPT  # RET-071
    history_budget_tokens: int = 1500  # GEN-062
    prices: Mapping[str, Price] = field(default_factory=dict[str, Price])  # GEN-070
    verify: bool = True
    """False only to measure what verification brings (GEN-080, EVL-092)."""
    instructions: str = ""
    """Operator instructions on tone, format and length (GEN-016)."""


def ask(
    question: str,
    retriever: Retriever,
    llm: LanguageModel,
    settings: GenerationSettings | None = None,
    history: Sequence[Turn] = (),
) -> Answer:
    """`history` holds previous turns, text only: context, never evidence (GEN-060)."""
    for event in ask_stream(question, retriever, llm, settings, history):
        if isinstance(event, StreamError):
            raise event.error
        if isinstance(event, AnswerCompleted):
            return event.answer
    raise AssertionError("ask_stream ended without an answer")  # pragma: no cover


def ask_stream(
    question: str,
    retriever: Retriever,
    llm: LanguageModel,
    settings: GenerationSettings | None = None,
    history: Sequence[Turn] = (),
) -> Iterator[AskEvent]:
    """Like `ask`, as events (GEN-050). Claims are emitted once generation completes and
    each is verified (GEN-051); parsing partial output to emit them sooner is future work."""
    settings = settings or GenerationSettings()
    calls = _Calls(llm, settings.prices)
    packed = pack_history(history, settings.history_budget_tokens)
    warnings: list[str] = []
    try:
        search_query = question
        if packed.turns:
            search_query = _condensed(question, packed.turns, calls, settings, warnings)
        hits = retriever.search(search_query, settings.k)
        evidence = {f"E{rank}": chunk for rank, chunk in enumerate(hits, 1)}
        yield RetrievalCompleted(search_query, tuple(evidence.values()))
        query = QueryInfo(question, search_query, len(packed.turns), packed.dropped)

        def completed(answer: Answer) -> AnswerCompleted:
            usage = calls.usage()
            return AnswerCompleted(
                replace(answer, query=query, warnings=tuple(warnings), usage=usage)
            )

        if not evidence:  # GEN-001: no evidence, no generation call
            yield completed(
                Answer(AnswerStatus.ABSTAINED, abstention_reason=AbstentionReason.NO_EVIDENCE)
            )
            return
        request = grounded_request(
            settings.prompt, question, evidence, packed.turns, settings.instructions
        )
        output = _generate(calls, request)
        chunks = list(evidence.values())
        verified = [
            replace(claim, conditions=missing_conditions(claim, chunks))  # GEN-095
            for claim in (_verified(c, evidence, settings.verify) for c in output.claims)
        ]
        if output.insufficient_evidence is None:
            for claim in verified:
                if claim.citations:
                    yield ClaimVerified(claim)
        answer = _answer(output, verified, settings.verify)
        yield completed(
            replace(
                answer,
                conflicts=_conflicts(output, evidence, answer.claims),
                lenient_parse=output.lenient,
                prompt_version=settings.prompt.version,
                citations_proposed=sum(len(claim.citations) for claim in output.claims),
            )
        )
    except SoundlineError as error:
        yield StreamError(error)


def _condensed(
    question: str,
    history: Sequence[Turn],
    calls: "_Calls",
    settings: GenerationSettings,
    warnings: list[str],
) -> str:
    """The follow-up as a standalone query; the question itself if that fails (RET-073)."""
    request = condense_request(settings.condense_prompt, question, history)
    try:
        data, _ = parse_json_object(calls.generate("rewrite", request))
        query = data.get("query")
        if isinstance(query, str) and query.strip():
            return query.strip()
        reason = "no query in the output"
    except (InvalidOutputError, GenerationError, ProviderUnavailableError) as error:
        reason = str(error)
    warnings.append(f"follow-up condensation failed ({reason}); searched the question as asked")
    return question


def _answer(output: "_ModelOutput", verified: Sequence[Claim], verify: bool) -> Answer:
    if output.insufficient_evidence is not None:  # GEN-021
        return Answer(
            AnswerStatus.ABSTAINED,
            abstention_reason=AbstentionReason.MODEL_INSUFFICIENT_EVIDENCE,
            abstention_message=output.insufficient_evidence,
        )
    if not verify:  # GEN-080: every claim is shown as the model wrote it
        text, citations = render(verified)
        return Answer(AnswerStatus.ANSWERED, text=text, citations=citations, claims=tuple(verified))
    supported = [claim for claim in verified if claim.citations]
    dropped = [claim.text for claim in verified if not claim.citations]  # GEN-033
    if not supported:
        return Answer(
            AnswerStatus.ABSTAINED,
            abstention_reason=AbstentionReason.UNSUPPORTED_CLAIMS,
            dropped_claims=dropped,
        )
    text, citations = render(supported)
    status = AnswerStatus.PARTIAL if dropped else AnswerStatus.ANSWERED  # GEN-034
    return Answer(
        status, text=text, citations=citations, dropped_claims=dropped, claims=tuple(supported)
    )


class _Calls:
    """Calls the model and records each call's usage as a stage (GEN-070)."""

    def __init__(self, llm: LanguageModel, prices: Mapping[str, Price]) -> None:
        self._llm = llm
        self._prices = prices
        self.stages: list[StageUsage] = []

    def generate(self, stage: str, request: GenerationRequest) -> str:
        started = time.perf_counter()
        generation = self._llm.generate(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        model = self._llm.model_id
        price = price_for(model, self._prices)
        cost = price.cost(generation.usage) if price else None
        latency_ms = generation.latency_ms if generation.cached else elapsed_ms
        self.stages.append(
            StageUsage(
                stage,
                model,
                generation.usage,
                cost,
                latency_ms=latency_ms or 0.0,
                cached=generation.cached,
            )
        )
        return generation.text

    def usage(self) -> Usage:
        return Usage(tuple(self.stages))


def _generate(calls: _Calls, request: GenerationRequest) -> _ModelOutput:
    """One corrective retry with the validation error, then a GenerationError (GEN-020)."""
    try:
        return _parse(calls.generate("generation", request))
    except InvalidOutputError as first:
        retry = GenerationRequest(
            request.system,
            f"{request.prompt}\n\nYour previous output was invalid: {first}. "
            "Respond again with JSON only, in one of the two forms above.",
            request.output,
        )
        try:
            return _parse(calls.generate("generation_retry", retry))
        except InvalidOutputError as second:
            raise GenerationError(
                f"the model did not follow the output format twice: {second}"
            ) from second


def _parse(raw: str) -> _ModelOutput:
    output, lenient = parse_json_object(raw)
    claims = output.get("claims")
    # Claims win over the declaration: small models often fill it with "" while answering,
    # and the claims are verified anyway (GEN-021, GEN-023).
    if isinstance(output.get("insufficient_evidence"), str) and not claims:
        return _ModelOutput([], str(output["insufficient_evidence"]), lenient)
    if not isinstance(claims, list):
        raise InvalidOutputError("'claims' must be a list of claims")
    return _ModelOutput(
        [_claim(c) for c in cast("list[object]", claims)],
        None,
        lenient,
        _reported_conflicts(output.get("conflicts")),
    )


def _reported_conflicts(value: object) -> list[tuple[str, list[str]]]:
    """Malformed entries are ignored: a conflict is a warning, never a reason to reject an
    answer (GEN-093)."""
    reported: list[tuple[str, list[str]]] = []
    for item in cast("list[object]", value) if isinstance(value, list) else []:
        entry: Mapping[str, object] = (
            cast("Mapping[str, object]", item) if isinstance(item, Mapping) else {}
        )
        about, ids = entry.get("about"), entry.get("evidence_ids")
        if isinstance(about, str) and isinstance(ids, list):
            reported.append((about, [str(i) for i in cast("list[object]", ids)]))
    return reported


def _conflicts(
    output: _ModelOutput, evidence: Mapping[str, Chunk], claims: Sequence[Claim]
) -> tuple[Conflict, ...]:
    """Kept only between documents the shown claims cite (GEN-091)."""
    kept: list[Conflict] = []
    for about, ids in output.conflicts:
        items = [evidence[i] for i in dict.fromkeys(ids) if i in evidence]
        conflict = conflict_among(about, items, claims)
        if conflict is not None:
            kept.append(conflict)
    return tuple(kept)


def _claim(item: object) -> _ModelClaim:
    if not isinstance(item, Mapping):
        raise InvalidOutputError("each claim must be an object")
    claim = cast("Mapping[str, object]", item)
    citations: list[tuple[str, str]] = []
    for citation in cast("list[object]", claim.get("citations") or []):
        entry: Mapping[str, object] = (
            cast("Mapping[str, object]", citation) if isinstance(citation, Mapping) else {}
        )
        citations.append((str(entry.get("evidence_id", "")), str(entry.get("quote", ""))))
    return _ModelClaim(str(claim.get("text", "")), citations)


def _verified(claim: _ModelClaim, evidence: Mapping[str, Chunk], verify: bool) -> Claim:
    """Keeps only citations whose quote is verified in the cited evidence (GEN-030 to 039);
    without verification, failed ones too, flagged at the evidence's span (GEN-080)."""
    citations: list[Citation] = []
    for evidence_id, quote in claim.citations:
        chunk = evidence.get(evidence_id)
        if chunk is None:
            continue  # unknown evidence ID (GEN-030)
        result = verify_quote(quote, chunk.text)
        if result.method is Method.FAILED:
            if not verify:
                citations.append(
                    Citation(
                        chunk.source,
                        quote,
                        chunk.span,
                        False,
                        chunk.section_path,
                        False,
                        page_at(chunk.pages, chunk.span.start),
                    )
                )
            continue
        span = result.span.shifted_by(chunk.span.start)
        citations.append(
            Citation(
                chunk.source,
                result.quote,
                span,
                result.approximate,
                chunk.section_path,
                page=page_at(chunk.pages, span.start),  # GEN-031
            )
        )
    return Claim(claim.text, tuple(citations))
