"""Grounded answers (docs/spec/05-generation.md): the model proposes, the code verifies."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from soundline.application.ports import GenerationRequest, LanguageModel, Retriever
from soundline.application.prompts import DEFAULT_PROMPT, PromptTemplate
from soundline.domain.answers import (
    AbstentionReason,
    Answer,
    AnswerStatus,
    Citation,
    Claim,
    render,
)
from soundline.domain.chunks import Chunk
from soundline.domain.errors import GenerationError
from soundline.domain.usage import Price, StageUsage, Usage, price_for
from soundline.domain.verification import Method, verify_quote

_FENCED = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


class _InvalidOutputError(Exception):
    """The model's output does not follow the expected format; the message says why."""


@dataclass(frozen=True)
class _ModelClaim:
    text: str
    citations: list[tuple[str, str]]  # (evidence_id, quote)


@dataclass(frozen=True)
class _ModelOutput:
    claims: list[_ModelClaim]
    insufficient_evidence: str | None
    lenient: bool


@dataclass(frozen=True)
class GenerationSettings:
    """The `[generation]` configuration section (docs/spec/09-configuration.md)."""

    k: int = 5
    prompt: PromptTemplate = DEFAULT_PROMPT  # GEN-014
    prices: Mapping[str, Price] = field(default_factory=dict[str, Price])  # GEN-070


def ask(
    question: str,
    retriever: Retriever,
    llm: LanguageModel,
    settings: GenerationSettings | None = None,
) -> Answer:
    settings = settings or GenerationSettings()
    prompt = settings.prompt
    hits = retriever.search(question, settings.k)
    evidence = {f"E{rank}": chunk for rank, chunk in enumerate(hits, 1)}
    if not evidence:  # GEN-001: no evidence, no model call
        return Answer(AnswerStatus.ABSTAINED, abstention_reason=AbstentionReason.NO_EVIDENCE)

    calls = _Calls(llm, settings.prices)
    output = _generate(calls, prompt.render(question, evidence))
    usage = Usage(tuple(calls.stages))
    if output.insufficient_evidence is not None:  # GEN-021
        return Answer(
            AnswerStatus.ABSTAINED,
            abstention_reason=AbstentionReason.MODEL_INSUFFICIENT_EVIDENCE,
            abstention_message=output.insufficient_evidence,
            lenient_parse=output.lenient,
            prompt_version=prompt.version,
            usage=usage,
        )

    verified = [_verified(claim, evidence) for claim in output.claims]
    supported = [claim for claim in verified if claim.citations]
    dropped = [claim.text for claim in verified if not claim.citations]  # GEN-033
    if not supported:
        return Answer(
            AnswerStatus.ABSTAINED,
            abstention_reason=AbstentionReason.UNSUPPORTED_CLAIMS,
            dropped_claims=dropped,
            lenient_parse=output.lenient,
            prompt_version=prompt.version,
            usage=usage,
        )
    text, citations = render(supported)
    status = AnswerStatus.PARTIAL if dropped else AnswerStatus.ANSWERED  # GEN-034
    return Answer(
        status,
        text=text,
        citations=citations,
        dropped_claims=dropped,
        lenient_parse=output.lenient,
        prompt_version=prompt.version,
        usage=usage,
    )


class _Calls:
    """Calls the model and records each call's usage as a stage (GEN-070)."""

    def __init__(self, llm: LanguageModel, prices: Mapping[str, Price]) -> None:
        self._llm = llm
        self._prices = prices
        self.stages: list[StageUsage] = []

    def generate(self, stage: str, request: GenerationRequest) -> str:
        generation = self._llm.generate(request)
        model = self._llm.model_id
        price = price_for(model, self._prices)
        cost = price.cost(generation.usage) if price else None
        self.stages.append(StageUsage(stage, model, generation.usage, cost))
        return generation.text


def _generate(calls: _Calls, request: GenerationRequest) -> _ModelOutput:
    """One corrective retry with the validation error, then a GenerationError (GEN-020)."""
    try:
        return _parse(calls.generate("generation", request))
    except _InvalidOutputError as first:
        retry = GenerationRequest(
            request.system,
            f"{request.prompt}\n\nYour previous output was invalid: {first}. "
            "Respond again with JSON only, in one of the two forms above.",
            request.output,
        )
        try:
            return _parse(calls.generate("generation_retry", retry))
        except _InvalidOutputError as second:
            raise GenerationError(
                f"the model did not follow the output format twice: {second}"
            ) from second


def _parse(raw: str) -> _ModelOutput:
    """Strict JSON first; then lenient: JSON in a Markdown fence or amid prose (GEN-023)."""
    lenient = False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        lenient = True
        data = _lenient_json(raw)
    if not isinstance(data, Mapping):
        raise _InvalidOutputError("the output must be a JSON object")
    output = cast("Mapping[str, object]", data)
    claims = output.get("claims")
    # Claims win over the declaration: small models often fill it with "" while answering,
    # and the claims are verified anyway (GEN-021, GEN-023).
    if isinstance(output.get("insufficient_evidence"), str) and not claims:
        return _ModelOutput([], str(output["insufficient_evidence"]), lenient)
    if not isinstance(claims, list):
        raise _InvalidOutputError("'claims' must be a list of claims")
    return _ModelOutput([_claim(c) for c in cast("list[object]", claims)], None, lenient)


def _lenient_json(raw: str) -> object:
    fenced = _FENCED.search(raw)
    candidate = fenced.group(1) if fenced else raw[raw.find("{") : raw.rfind("}") + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as error:
        raise _InvalidOutputError(f"no JSON object found ({error.msg})") from error


def _claim(item: object) -> _ModelClaim:
    if not isinstance(item, Mapping):
        raise _InvalidOutputError("each claim must be an object")
    claim = cast("Mapping[str, object]", item)
    citations: list[tuple[str, str]] = []
    for citation in cast("list[object]", claim.get("citations") or []):
        entry: Mapping[str, object] = (
            cast("Mapping[str, object]", citation) if isinstance(citation, Mapping) else {}
        )
        citations.append((str(entry.get("evidence_id", "")), str(entry.get("quote", ""))))
    return _ModelClaim(str(claim.get("text", "")), citations)


def _verified(claim: _ModelClaim, evidence: Mapping[str, Chunk]) -> Claim:
    """Keeps only citations whose quote is verified in the cited evidence (GEN-030 to 039)."""
    citations: list[Citation] = []
    for evidence_id, quote in claim.citations:
        chunk = evidence.get(evidence_id)
        if chunk is None:
            continue  # unknown evidence ID (GEN-030)
        result = verify_quote(quote, chunk.text)
        if result.method is Method.FAILED:
            continue
        span = result.span.shifted_by(chunk.span.start)
        citations.append(
            Citation(chunk.source, result.quote, span, result.approximate, chunk.section_path)
        )
    return Claim(claim.text, tuple(citations))
