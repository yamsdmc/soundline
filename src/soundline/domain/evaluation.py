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


def retrieval_metrics(
    quotes: Sequence[Located],
    hits: Sequence[Located],
    ks: Sequence[int] = (1, 3, 5, 10),
    min_overlap: float = 0.5,
) -> dict[str, float]:
    """recall@k, hit_rate@k, precision@k, ndcg@k (binary) for each k, and mrr up to max(ks).

    A hit gains only for quotes that no earlier hit covered, so a quote counts once.
    """
    found: list[set[int]] = []  # quotes each hit newly covers
    seen: set[int] = set()
    for hit in hits:
        new = {i for i, quote in enumerate(quotes) if covers(hit, quote, min_overlap)} - seen
        found.append(new)
        seen |= new
    relevant = [any(covers(hit, quote, min_overlap) for quote in quotes) for hit in hits]

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
