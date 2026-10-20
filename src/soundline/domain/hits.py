from collections.abc import Mapping
from dataclasses import dataclass

from soundline.domain.chunks import Chunk


@dataclass(frozen=True)
class Hit:
    """A chunk in a ranked search result, with how each retriever ranked it (RET-004, RET-005)."""

    chunk: Chunk
    score: float
    ranks: Mapping[str, int | None]

    @property
    def source(self) -> str:
        return self.chunk.source

    @property
    def text(self) -> str:
        return self.chunk.text
