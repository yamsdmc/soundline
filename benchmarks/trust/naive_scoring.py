"""Scores the naive baseline with Soundline's own metrics (EVL-092).

The baseline answers in free text with [n] markers. Each sentence becomes a claim citing the
context pieces its markers name. Such a citation points at a whole chunk: it is not a quote
and nothing checked it, so it is flagged unverified.
"""

import hashlib
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from soundline.application.evaluate import DatasetFile, judge_claims
from soundline.application.judges import FaithfulnessJudge
from soundline.domain.answers import (
    AbstentionReason,
    Answer,
    AnswerStatus,
    Citation,
    Claim,
    answer_to_dict,
)
from soundline.domain.datasets import parse_dataset
from soundline.domain.evaluation import generation_metrics
from soundline.domain.quotes import Span
from soundline.domain.runs import EvalRun, aggregate
from soundline.domain.statistics import describe

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_MARKER = re.compile(r"\s*\[(\d+)\]")
_REFUSAL = re.compile(
    r"je ne sais pas|aucune information"
    r"|ne (?:contient|mentionne|précise|permet|fournit|donne|indique) pas",
    re.IGNORECASE,
)


def naive_answer(text: str, context: Sequence[Mapping[str, str]]) -> Answer:
    """An uncited refusal is an abstention; anything else is an answer, shown as written."""
    if not _MARKER.search(text) and _REFUSAL.search(text):
        return Answer(
            AnswerStatus.ABSTAINED,
            abstention_reason=AbstentionReason.MODEL_INSUFFICIENT_EVIDENCE,
            abstention_message=text,
        )
    claims = tuple(
        _claim(sentence, context) for sentence in _SENTENCE_END.split(text.strip()) if sentence
    )
    return Answer(AnswerStatus.ANSWERED, text=text, claims=claims)


def _claim(sentence: str, context: Sequence[Mapping[str, str]]) -> Claim:
    citations: list[Citation] = []
    for marker in _MARKER.findall(sentence):
        number = int(marker)
        if 1 <= number <= len(context):
            piece = context[number - 1]
            citation = Citation(
                piece["source"], piece["text"], Span(0, len(piece["text"])), verified=False
            )
            if citation not in citations:
                citations.append(citation)
    return Claim(_MARKER.sub("", sentence), tuple(citations))


_QUOTE_METRICS = ("citation_recall", "shown_citation_validity", "shown_support_rate")
_OPERATIONS = ("latency_ms", "tokens_in", "tokens_out")


def naive_run(
    name: str,
    dataset_file: DatasetFile,
    records: Mapping[str, Mapping[str, Any]],
    settings: Mapping[str, object],
    judge: FaithfulnessJudge | None = None,
) -> EvalRun:
    """The baseline's answers as a run, with the dataset hash of Soundline's runs on the same
    file, so that `soundline eval compare` pairs them case by case (EVL-051)."""
    dataset = parse_dataset(dataset_file.text.splitlines())
    per_case: dict[str, dict[str, float]] = {}
    answers: dict[str, dict[str, object]] = {}
    for case in dataset.cases:
        record = records[case.id]
        answer = naive_answer(record["text"], record["context"])
        metrics = generation_metrics(answer, [], case.answerable, forbidden=case.forbidden)
        for metric in _QUOTE_METRICS:  # chunk pointers are not quotes
            metrics.pop(metric, None)
        metrics.update({metric: float(record[metric]) for metric in _OPERATIONS})
        answers[case.id] = answer_to_dict(answer)
        if judge is not None:
            answers[case.id]["judgments"], _ = judge_claims(judge, answer, metrics)
        per_case[case.id] = metrics
    return EvalRun(
        name=name,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        dataset={
            "path": dataset_file.path,
            "sha256": hashlib.sha256(dataset_file.text.encode()).hexdigest(),
            "cases": len(per_case),
        },
        index={"fingerprint": None, "components": {}},
        settings={"mode": "end-to-end", "system": "naive-langchain", **settings},
        per_case=per_case,
        metrics=aggregate(per_case),
        answers=answers,
        operations={
            metric: describe([m[metric] for m in per_case.values()]) for metric in _OPERATIONS
        },
    )
