"""Evaluation datasets: JSONL, one case per line (EVL-001 to EVL-005)."""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import cast

from soundline.domain.errors import SoundlineError


class DatasetError(SoundlineError):
    code = "invalid_dataset"


@dataclass(frozen=True)
class RelevantQuote:
    """A short exact excerpt a correct answer must rely on (ADR 0008)."""

    source: str
    quote: str
    alternatives: tuple["RelevantQuote", ...] = ()
    """Equivalent excerpts (the same rule in another document or variant of a page):
    covering any of them covers this quote (EVL-001)."""


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    answerable: bool
    relevant: tuple[RelevantQuote, ...]
    reference_answer: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Dataset:
    cases: tuple[EvalCase, ...]


def parse_dataset(lines: Iterable[str]) -> Dataset:
    cases: list[EvalCase] = []
    first_seen: dict[str, int] = {}
    for number, text in enumerate(lines, 1):
        if not text.strip():
            continue
        case = _parse_case(text, number)
        if case.id in first_seen:
            raise DatasetError(
                f"duplicate id {case.id!r} on lines {first_seen[case.id]} and {number}"
            )
        first_seen[case.id] = number
        cases.append(case)
    return Dataset(tuple(cases))


def _parse_case(text: str, number: int) -> EvalCase:
    def fail(reason: str) -> DatasetError:
        return DatasetError(f"line {number}: {reason}")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise fail(f"not valid JSON ({error.msg})") from error
    if not isinstance(data, Mapping):
        raise fail("a case is a JSON object")
    case = cast("Mapping[str, object]", data)
    for key in ("id", "question"):
        if not isinstance(case.get(key), str) or not str(case[key]).strip():
            raise fail(f"{key!r} must be a non-empty string")
    answerable = case.get("answerable", True)
    if not isinstance(answerable, bool):
        raise fail("'answerable' must be true or false")
    relevant = _relevant(case.get("relevant", []), number)
    if answerable and not relevant:
        raise fail("an answerable case needs relevant quotes")
    if not answerable and relevant:
        raise fail("an unanswerable case has no relevant quotes")
    reference = case.get("reference_answer")
    tags = case.get("tags", [])
    if not isinstance(tags, list) or not all(
        isinstance(t, str) for t in cast("list[object]", tags)
    ):
        raise fail("'tags' must be a list of strings")
    return EvalCase(
        id=str(case["id"]),
        question=str(case["question"]),
        answerable=answerable,
        relevant=relevant,
        reference_answer=reference if isinstance(reference, str) else None,
        tags=tuple(cast("list[str]", tags)),
    )


def _relevant(value: object, number: int) -> tuple[RelevantQuote, ...]:
    if not isinstance(value, list):
        raise DatasetError(f"line {number}: 'relevant' must be a list")
    quotes: list[RelevantQuote] = []
    for item in cast("list[object]", value):
        entry = _mapping(item)
        alternatives = entry.get("or", [])
        if not isinstance(alternatives, list):
            raise DatasetError(f"line {number}: 'or' must be a list of relevant quotes")
        others = tuple(
            _quote(_mapping(other), number) for other in cast("list[object]", alternatives)
        )
        quotes.append(replace(_quote(entry, number), alternatives=others))
    return tuple(quotes)


def _mapping(item: object) -> Mapping[str, object]:
    return cast("Mapping[str, object]", item) if isinstance(item, Mapping) else {}


def _quote(entry: Mapping[str, object], number: int) -> RelevantQuote:
    source, quote = entry.get("source"), entry.get("quote")
    if not (isinstance(source, str) and source and isinstance(quote, str) and quote.strip()):
        raise DatasetError(
            f"line {number}: each relevant quote needs a non-empty 'source' and 'quote'"
        )
    return RelevantQuote(source, quote)
