"""Evaluation use cases (docs/spec/06-evaluation.md)."""

import difflib
import hashlib
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath

from soundline.application.judges import CorrectnessJudge, FaithfulnessJudge
from soundline.application.ports import DocumentStore, Index
from soundline.domain.answers import Answer, AnswerStatus, answer_to_dict
from soundline.domain.datasets import Dataset, DatasetError, RelevantQuote, parse_dataset
from soundline.domain.evaluation import Located, generation_metrics, retrieval_metrics
from soundline.domain.hits import Hit
from soundline.domain.quotes import Span
from soundline.domain.runs import EvalRun, aggregate
from soundline.domain.statistics import describe

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


def resolve_dataset(
    dataset: Dataset, documents: DocumentStore, *, allow_missing_sources: bool = False
) -> dict[str, list[tuple[Located, ...]]]:
    """Locates every relevant quote in the indexed documents (EVL-002).

    A quote's `source` names a document by its source or by its file name. Quotes match
    regardless of case and whitespace, and resolve to the exact span of the source text.
    Every problem is reported at once, with the closest sentence as a hint. A sentence that a
    document repeats (across variants of a page) resolves to every occurrence, and so do a
    quote's alternatives: covering any occurrence covers the quote.
    """
    sources = documents.sources()
    resolved: dict[str, list[tuple[Located, ...]]] = {}
    problems: list[str] = []
    for case in dataset.cases:
        resolved[case.id] = [
            tuple(
                occurrence
                for variant in (relevant, *relevant.alternatives)
                for occurrence in _locate(
                    case.id, variant, sources, documents, allow_missing_sources, problems
                )
            )
            for relevant in case.relevant
        ]
    if problems:
        raise DatasetError("\n".join(problems))
    return resolved


def _locate(  # noqa: PLR0913, PLR0917  # one quote, with what resolving it needs
    case_id: str,
    relevant: RelevantQuote,
    sources: list[str],
    documents: DocumentStore,
    allow_missing_sources: bool,
    problems: list[str],
) -> list[Located]:
    """Every occurrence of one excerpt; problems are collected, not raised one by one."""
    matches = [s for s in sources if s == relevant.source or _file_name(s) == relevant.source]
    if not matches and allow_missing_sources:
        # The answer is in a document the index lacks: no hit can cover it (recall 0).
        return [Located(f"missing:{relevant.source}", Span(0, len(relevant.quote)))]
    if len(matches) != 1:
        reason = "no indexed document matches" if not matches else "several documents match"
        problems.append(f"case {case_id!r}: {reason} {relevant.source!r}")
        return []
    document = documents.get(matches[0])
    text = document.text if document else ""
    spans = _find(relevant.quote, text)
    if not spans:
        problems.append(_not_found(case_id, relevant, text))
    return [Located(matches[0], span) for span in spans]


def _find(quote: str, text: str) -> list[Span]:
    pattern = r"\s+".join(re.escape(word) for word in quote.split())
    return [Span(m.start(), m.end()) for m in re.finditer(pattern, text, re.IGNORECASE)]


def _not_found(case_id: str, relevant: RelevantQuote, text: str) -> str:
    sentences = [s.strip() for s in _SENTENCE.findall(text) if s.strip()]
    closest = difflib.get_close_matches(relevant.quote, sentences, n=1, cutoff=0.4)
    hint = f"; closest: {closest[0]!r}" if closest else ""
    return f"case {case_id!r}: {relevant.quote!r} not found in {relevant.source}{hint}"


def _file_name(source: str) -> str:
    return PurePosixPath(source).name


@dataclass(frozen=True)
class DatasetFile:
    path: str
    text: str


@dataclass(frozen=True)
class EvalSettings:
    ks: tuple[int, ...] = (1, 3, 5, 10)
    allow_missing_sources: bool = False


@dataclass(frozen=True)
class Generator:
    """What an end-to-end run calls on each question, and how to describe it in the run."""

    answer: Callable[[str], Answer]
    settings: Mapping[str, object]
    """Recorded in the run: model ID, prompt version (EVL-060)."""
    judge: FaithfulnessJudge | None = None
    """Optional, enabled explicitly (EVL-021)."""
    judge_calibration: str = "uncalibrated"
    """Shown next to judge metrics (EVL-043)."""
    correctness: CorrectnessJudge | None = None
    """Scores answers against reference answers (EVL-045)."""


_OPERATIONS = (
    "latency_ms",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "judge_tokens_in",
    "judge_tokens_out",
)


def run_eval(  # noqa: PLR0913  # keyword-only collaborators
    name: str,
    dataset_file: DatasetFile,
    index: Index,
    search: Callable[[str, int], list[Hit]],
    settings: EvalSettings,
    *,
    generator: Generator | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> EvalRun:
    """Scores retrieval on answerable cases and, with a generator, every answer end to end
    (EVL-060). Without one, the run is retrieval-only: no model call, deterministic, cheap
    enough for every commit (EVL-062)."""
    dataset = parse_dataset(dataset_file.text.splitlines())
    quotes = resolve_dataset(
        dataset, index.documents, allow_missing_sources=settings.allow_missing_sources
    )
    per_case: dict[str, dict[str, float]] = {}
    answers: dict[str, dict[str, object]] = {}
    unreadable = 0
    cache_hits = 0
    for case in dataset.cases:
        metrics: dict[str, float] = {}
        if case.answerable:  # retrieval metrics need relevant quotes (EVL-003)
            hits = search(case.question, max(settings.ks))
            located = [Located(hit.source, hit.chunk.span) for hit in hits]
            metrics.update(retrieval_metrics(quotes[case.id], located, settings.ks))
        if generator is not None:
            started = clock()
            answer = generator.answer(case.question)
            cached = [stage for stage in answer.usage.stages if stage.cached]
            cache_hits += len(cached)
            # A cached call took no time now: count it at its original duration (EVL-030).
            latency_ms = (clock() - started) * 1000 + sum(s.latency_ms for s in cached)
            metrics.update(
                generation_metrics(
                    answer, quotes.get(case.id, []), case.answerable, forbidden=case.forbidden
                )
            )
            metrics.update(_operational(answer, latency_ms))
            answers[case.id] = answer_to_dict(answer)
            if generator.judge is not None:
                judged, failed = judge_claims(generator.judge, answer, metrics)
                answers[case.id]["judgments"] = judged
                unreadable += failed
            if generator.correctness is not None and case.reference_answer is not None:
                verdict = judge_correctness(
                    generator.correctness, case.question, case.reference_answer, answer, metrics
                )
                if verdict is not None:
                    answers[case.id]["correctness"] = verdict
                elif answer.status is not AnswerStatus.ABSTAINED and answer.claims:
                    unreadable += 1
        if metrics:
            per_case[case.id] = metrics
    manifest = index.manifest.load()
    mode: dict[str, object] = {"mode": "retrieval-only"}
    if generator is not None:
        mode = {"mode": "end-to-end", **generator.settings}
        if generator.judge is not None:
            judge: dict[str, object] = {
                "model": generator.judge.model_id,
                "version": generator.judge.version,
                "calibration": generator.judge_calibration,  # EVL-043
            }
            if generator.correctness is not None:
                judge["correctness_version"] = generator.correctness.version
            mode["judge"] = judge
    return EvalRun(
        name=name,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        dataset={
            "path": dataset_file.path,
            "sha256": hashlib.sha256(dataset_file.text.encode()).hexdigest(),
            "cases": len(per_case),
        },
        index={
            "fingerprint": manifest.fingerprint if manifest else None,
            "components": dict(manifest.components) if manifest else {},
        },
        settings={"ks": list(settings.ks), **mode},
        per_case=per_case,
        metrics=aggregate(per_case),
        warnings=_judge_warnings(generator, unreadable) + _cache_warnings(cache_hits),
        answers=answers,
        operations={
            metric: describe([m[metric] for m in per_case.values() if metric in m])
            for metric in _OPERATIONS
            if any(metric in m for m in per_case.values())
        },
    )


def judge_claims(
    judge: FaithfulnessJudge, answer: Answer, metrics: dict[str, float]
) -> tuple[list[dict[str, object]], int]:
    """Faithfulness of the case: entailed claims among those with a readable verdict
    (EVL-041). Returns the verdicts and the number of unreadable ones."""
    verdicts: list[dict[str, object]] = []
    failed = 0
    before = judge.usage
    for claim in answer.claims:
        judgment = judge.judge(claim)
        if judgment is None:
            failed += 1
            continue
        verdicts.append(
            {"claim": claim.text, "entailed": judgment.entailed, "rationale": judgment.rationale}
        )
    if verdicts:
        metrics["faithfulness"] = sum(bool(v["entailed"]) for v in verdicts) / len(verdicts)
    spent = judge.usage - before
    metrics["judge_tokens_in"] = float(spent.total_input)
    metrics["judge_tokens_out"] = float(spent.output)
    return verdicts, failed


def judge_correctness(
    judge: CorrectnessJudge,
    question: str,
    reference: str,
    answer: Answer,
    metrics: dict[str, float],
) -> dict[str, object] | None:
    """Correctness of an answered case against its reference, the claims read as plain text
    so the judge cannot tell which system wrote them (EVL-044, EVL-045). None when the case
    abstained or the verdict cannot be read."""
    if answer.status is AnswerStatus.ABSTAINED or not answer.claims:
        return None
    before = judge.usage
    judgment = judge.judge(question, reference, " ".join(c.shown_text for c in answer.claims))
    spent = judge.usage - before
    metrics["judge_tokens_in"] = metrics.get("judge_tokens_in", 0.0) + spent.total_input
    metrics["judge_tokens_out"] = metrics.get("judge_tokens_out", 0.0) + spent.output
    if judgment is None:
        return None
    metrics["correctness"] = judgment.score
    return {"score": judgment.score, "rationale": judgment.rationale}


def _cache_warnings(cache_hits: int) -> list[str]:
    if not cache_hits:
        return []
    calls = "1 model call" if cache_hits == 1 else f"{cache_hits} model calls"
    return [f"{calls} answered from the cache; latencies count their original duration"]


def _judge_warnings(generator: Generator | None, unreadable: int) -> list[str]:
    if generator is None or generator.judge is None:
        return []
    warnings: list[str] = []
    if generator.judge.model_id == generator.settings.get("model"):
        warnings.append(
            "the judge is the same model as the generator: prefer another family (EVL-042)"
        )
    if unreadable:
        warnings.append(f"{unreadable} unreadable judge verdicts: those claims are unjudged")
    return warnings


def _operational(answer: Answer, latency_ms: float) -> dict[str, float]:
    """Latency includes retrieval and verification: the cost of trust is visible (EVL-030)."""
    tokens = answer.usage.tokens
    metrics = {
        "latency_ms": latency_ms,
        "tokens_in": float(tokens.total_input),
        "tokens_out": float(tokens.output),
    }
    if answer.usage.cost_usd is not None:
        metrics["cost_usd"] = answer.usage.cost_usd
    return metrics
