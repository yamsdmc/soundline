from dataclasses import dataclass

from soundline.domain.quotes import Span


@dataclass(frozen=True)
class Chunk:
    """A contiguous span of a document's text: the unit of retrieval (ING-040)."""

    source: str
    text: str
    span: Span
