import hashlib
from dataclasses import dataclass, field
from functools import cached_property

from soundline.domain.filters import Metadata
from soundline.domain.quotes import Span


@dataclass(frozen=True)
class Chunk:
    """A contiguous span of a document's text: the unit of retrieval (ING-040)."""

    source: str
    text: str
    span: Span
    metadata: Metadata = field(default_factory=dict[str, str], hash=False)
    """Inherited from the document; used by filters (RET-040)."""

    @cached_property
    def id(self) -> str:
        """Deterministic: same source, span and text, same ID (ING-010)."""
        key = f"{self.source}\0{self.span.start}\0{self.span.end}\0{self.text}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
