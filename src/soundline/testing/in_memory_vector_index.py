from soundline.application.ports import Vector
from soundline.domain.chunks import Chunk
from soundline.domain.filters import Filter, matches


class InMemoryVectorIndex:
    """Fake vector index: brute-force cosine similarity over unit vectors."""

    def __init__(self, dimension: int) -> None:
        self._dimension = dimension
        self._entries: list[tuple[Chunk, Vector]] = []

    def add(self, chunk: Chunk, vector: Vector) -> None:
        if len(vector) != self._dimension:
            raise ValueError(
                f"vector dimension {len(vector)} differs from the index dimension {self._dimension}"
            )
        self._entries.append((chunk, vector))

    def remove(self, source: str) -> None:
        self._entries = [entry for entry in self._entries if entry[0].source != source]

    def search(self, vector: Vector, limit: int, filter: Filter | None = None) -> list[Chunk]:
        def similarity(entry: tuple[Chunk, Vector]) -> float:
            return sum(x * y for x, y in zip(vector, entry[1], strict=True))

        candidates = [e for e in self._entries if filter is None or matches(filter, e[0].metadata)]
        return [chunk for chunk, _ in sorted(candidates, key=similarity, reverse=True)[:limit]]
