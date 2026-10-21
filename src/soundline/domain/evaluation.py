"""Retrieval evaluation (docs/spec/06-evaluation.md).

Relevance is labeled by quote, not by chunk ID (ADR 0008): a retrieved chunk is relevant to a
quote when it covers at least `min_overlap` of the quote's characters (EVL-001).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from soundline.domain.quotes import Span


@dataclass(frozen=True)
class Located:
    """A span of a document's normalized text."""

    source: str
    span: Span


def covers(hit: Located, quote: Located, min_overlap: float = 0.5) -> bool:
    if hit.source != quote.source:
        return False
    overlap = min(hit.span.end, quote.span.end) - max(hit.span.start, quote.span.start)
    return overlap > 0 and overlap >= min_overlap * (quote.span.end - quote.span.start)


type Quote = Located | Sequence[Located]
"""A relevant quote, or every occurrence of it when a document repeats the sentence."""


def retrieval_metrics(
    quotes: Sequence[Quote],
    hits: Sequence[Located],
    ks: Sequence[int] = (1, 3, 5, 10),
    min_overlap: float = 0.5,
) -> dict[str, float]:
    """recall@k, hit_rate@k, precision@k, ndcg@k (binary) for each k, and mrr up to max(ks).

    A hit covers a quote when it covers any of its occurrences. A hit gains only for quotes
    that no earlier hit covered, so a quote counts once.
    """
    occurrences = [(q,) if isinstance(q, Located) else tuple(q) for q in quotes]

    def hit_covers(hit: Located, quote: tuple[Located, ...]) -> bool:
        return any(covers(hit, occurrence, min_overlap) for occurrence in quote)

    found: list[set[int]] = []  # quotes each hit newly covers
    seen: set[int] = set()
    for hit in hits:
        new = {i for i, quote in enumerate(occurrences) if hit_covers(hit, quote)} - seen
        found.append(new)
        seen |= new
    relevant = [any(hit_covers(hit, quote) for quote in occurrences) for hit in hits]

    metrics: dict[str, float] = {}
    for k in ks:
        top = found[:k]
        covered = len(set[int]().union(*top))
        metrics[f"recall@{k}"] = covered / len(quotes)
        metrics[f"hit_rate@{k}"] = 1.0 if covered else 0.0
        metrics[f"precision@{k}"] = sum(relevant[:k]) / len(relevant[:k]) if hits else 0.0
        ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(quotes), k) + 1))
        gains = sum(1 / math.log2(rank + 1) for rank, new in enumerate(top, 1) if new)
        metrics[f"ndcg@{k}"] = gains / ideal
    first = next((rank for rank, r in enumerate(relevant[: max(ks)], 1) if r), None)
    metrics["mrr"] = 1 / first if first else 0.0
    return metrics
