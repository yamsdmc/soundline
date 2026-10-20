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

    @property
    def section_path(self) -> tuple[str, ...]:
        return self.chunk.section_path

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "text": self.text,
            "score": self.score,
            "ranks": dict(self.ranks),
            "section_path": list(self.section_path),
            "span": [self.chunk.span.start, self.chunk.span.end],
            "metadata": dict(self.chunk.metadata),
        }
