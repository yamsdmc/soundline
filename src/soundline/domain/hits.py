from collections.abc import Mapping
from dataclasses import dataclass, field

from soundline.domain.chunks import Chunk
from soundline.domain.tracing import TraceSpan


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
            "pages": [self.chunk.pages[0][0], self.chunk.pages[-1][0]]  # ING-047
            if self.chunk.pages
            else None,
        }


@dataclass(frozen=True)
class SearchResult:
    hits: list[Hit]
    degraded: bool = False
    """True when a retriever failed and the others answered alone (RET-034)."""
    warnings: list[str] = field(default_factory=list[str])
    trace: TraceSpan | None = None
    """How the search ran, step by step (OBS-004)."""
