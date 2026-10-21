"""Judge calibration against human labels (EVL-043)."""

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from soundline.domain.datasets import DatasetError

type QuoteLabel = tuple[str, tuple[str, ...], str]
"""source, section path, quote."""


@dataclass(frozen=True)
class Label:
    id: str
    claim: str
    quotes: tuple[QuoteLabel, ...]
    entailed: bool
    """The human verdict: do the quotes, with their sections, support the claim?"""
    reviewed: bool = True
    """False while the verdict is a suggestion nobody has checked yet."""


@dataclass(frozen=True)
class Agreement:
    cases: int
    accuracy: float
    kappa: float
    """Cohen's kappa: agreement beyond chance; 0 when chance explains everything."""
    true_accepts: int
    true_rejects: int
    false_accepts: int
    """The judge accepted a claim a human rejected: the costly error for faithfulness."""
    false_rejects: int


def agreement(pairs: Sequence[tuple[bool, bool]]) -> Agreement:
    """`pairs` are (human, judge) verdicts."""
    n = len(pairs)
    true_accepts = sum(h and j for h, j in pairs)
    true_rejects = sum(not h and not j for h, j in pairs)
    false_accepts = sum(not h and j for h, j in pairs)
    false_rejects = sum(h and not j for h, j in pairs)
    observed = (true_accepts + true_rejects) / n if n else 0.0
    human_yes = (true_accepts + false_rejects) / n if n else 0.0
    judge_yes = (true_accepts + false_accepts) / n if n else 0.0
    chance = human_yes * judge_yes + (1 - human_yes) * (1 - judge_yes)
    kappa = (observed - chance) / (1 - chance) if chance < 1 else 0.0
    return Agreement(n, observed, kappa, true_accepts, true_rejects, false_accepts, false_rejects)


def parse_labels(lines: Iterable[str]) -> list[Label]:
    labels: list[Label] = []
    for number, line in enumerate(lines, 1):
        if line.strip():
            labels.append(_label(line, number))
    return labels


def _label(line: str, number: int) -> Label:
    def fail(reason: str) -> DatasetError:
        return DatasetError(f"line {number}: {reason}")

    try:
        data = json.loads(line)
    except json.JSONDecodeError as error:
        raise fail(f"invalid JSON ({error.msg})") from error
    if not isinstance(data, Mapping):
        raise fail("a label must be a JSON object")
    entry = cast("Mapping[str, object]", data)
    label_id, claim, entailed = entry.get("id"), entry.get("claim"), entry.get("entailed")
    if not isinstance(label_id, str) or not label_id:
        raise fail("'id' must be a non-empty string")
    if not isinstance(claim, str) or not claim.strip():
        raise fail("'claim' must be a non-empty string")
    if not isinstance(entailed, bool):
        raise fail("'entailed' must be true or false")
    quotes = entry.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        raise fail("'quotes' must list the claim's cited quotes")
    return Label(
        label_id,
        claim,
        tuple(_quote(q, fail) for q in cast("list[object]", quotes)),
        entailed,
        reviewed=entry.get("reviewed", True) is True,
    )


def _quote(value: object, fail: Callable[[str], DatasetError]) -> QuoteLabel:
    entry: Mapping[str, object] = (
        cast("Mapping[str, object]", value) if isinstance(value, Mapping) else {}
    )
    source, section, quote = entry.get("source"), entry.get("section", []), entry.get("quote")
    if not isinstance(source, str) or not isinstance(quote, str) or not isinstance(section, list):
        raise fail("each quote needs 'source', 'quote' and a 'section' list")
    return source, tuple(str(part) for part in cast("list[object]", section)), quote
