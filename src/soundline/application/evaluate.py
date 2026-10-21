"""Evaluation use cases (docs/spec/06-evaluation.md)."""

import difflib
import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath

from soundline.application.ports import DocumentStore, Index
from soundline.domain.datasets import Dataset, DatasetError, RelevantQuote, parse_dataset
from soundline.domain.evaluation import Located, retrieval_metrics
from soundline.domain.hits import Hit
from soundline.domain.quotes import Span
from soundline.domain.runs import EvalRun, aggregate

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


def resolve_dataset(
    dataset: Dataset, documents: DocumentStore, *, allow_missing_sources: bool = False
) -> dict[str, list[Located]]:
    """Locates every relevant quote in the indexed documents (EVL-002).

    A quote's `source` names a document by its source or by its file name. Quotes match
    regardless of case and whitespace, and resolve to the exact span of the source text.
    Every problem is reported at once, with the closest sentence as a hint.
    """
    sources = documents.sources()
    resolved: dict[str, list[Located]] = {}
    problems: list[str] = []
    for case in dataset.cases:
        located: list[Located] = []
        for relevant in case.relevant:
            matches = [
                s for s in sources if s == relevant.source or _file_name(s) == relevant.source
            ]
            if not matches and allow_missing_sources:
                # The answer is in a document the index lacks: no hit can cover it (recall 0).
                located.append(Located(f"missing:{relevant.source}", Span(0, len(relevant.quote))))
                continue
            if len(matches) != 1:
                reason = "no indexed document matches" if not matches else "several documents match"
                problems.append(f"case {case.id!r}: {reason} {relevant.source!r}")
                continue
            document = documents.get(matches[0])
            text = document.text if document else ""
            span = _find(relevant.quote, text)
            if span is None:
                problems.append(_not_found(case.id, relevant, text))
            else:
                located.append(Located(matches[0], span))
        resolved[case.id] = located
    if problems:
        raise DatasetError("\n".join(problems))
    return resolved


def _find(quote: str, text: str) -> Span | None:
    pattern = r"\s+".join(re.escape(word) for word in quote.split())
    match = re.search(pattern, text, re.IGNORECASE)
    return Span(match.start(), match.end()) if match else None


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


def run_retrieval_eval(
    name: str,
    dataset_file: DatasetFile,
    index: Index,
    search: Callable[[str, int], list[Hit]],
    settings: EvalSettings,
) -> EvalRun:
    """Searches every answerable question and scores the hits (EVL-060, EVL-062).
    Retrieval-only: no language model, deterministic, cheap enough for every commit."""
    dataset = parse_dataset(dataset_file.text.splitlines())
    quotes = resolve_dataset(
        dataset, index.documents, allow_missing_sources=settings.allow_missing_sources
    )
    per_case: dict[str, dict[str, float]] = {}
    for case in dataset.cases:
        if not case.answerable:
            continue  # retrieval metrics need relevant quotes (EVL-003)
        hits = search(case.question, max(settings.ks))
        located = [Located(hit.source, hit.chunk.span) for hit in hits]
        per_case[case.id] = retrieval_metrics(quotes[case.id], located, settings.ks)
    manifest = index.manifest.load()
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
        settings={"ks": list(settings.ks), "mode": "retrieval-only"},
        per_case=per_case,
        metrics=aggregate(per_case),
    )
