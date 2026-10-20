from soundline.application.ports import Vector
from soundline.domain.chunks import Chunk


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

    def search(self, vector: Vector, limit: int) -> list[Chunk]:
        def similarity(entry: tuple[Chunk, Vector]) -> float:
            return sum(x * y for x, y in zip(vector, entry[1], strict=True))

        return [chunk for chunk, _ in sorted(self._entries, key=similarity, reverse=True)[:limit]]
