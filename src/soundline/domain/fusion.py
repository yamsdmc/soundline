from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FusedHit:
    item: str
    score: float
    ranks: Mapping[str, int | None]
    """1-based rank of the item in each retriever's ranking; None when absent (RET-005)."""


def fuse(
    rankings: Mapping[str, Sequence[str]],
    weights: Mapping[str, float] | None = None,
    k: int = 60,
) -> list[FusedHit]:
    """Reciprocal Rank Fusion: score(item) = Σ w / (k + rank) over the rankings (RET-030).

    A retriever with weight 0 is ignored entirely (RET-032). Ties are broken by item (RET-006).
    """

    def weight(retriever: str) -> float:
        return (weights or {}).get(retriever, 1.0)

    active = {
        retriever: {item: rank for rank, item in enumerate(ranking, 1)}
        for retriever, ranking in rankings.items()
        if weight(retriever) != 0
    }
    items = {item for ranks in active.values() for item in ranks}
    hits = [
        FusedHit(
            item,
            sum(
                weight(retriever) / (k + ranks[item])
                for retriever, ranks in active.items()
                if item in ranks
            ),
            {retriever: ranks.get(item) for retriever, ranks in active.items()},
        )
        for item in items
    ]
    return sorted(hits, key=lambda hit: (-hit.score, hit.item))
