"""Ports: what the application needs from the outside world (see docs/spec/02-architecture.md)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from soundline.domain.chunks import Chunk
from soundline.domain.filters import Filter


@dataclass(frozen=True)
class GenerationRequest:
    system: str
    prompt: str


class LanguageModel(Protocol):
    def generate(self, request: GenerationRequest) -> Mapping[str, object]:
        """Returns the model's structured output."""
        ...


type Vector = tuple[float, ...]


class Embedder(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        """Unit-length vectors, one per text, in order."""
        ...

    def embed_query(self, text: str) -> Vector: ...


class Retriever(Protocol):
    def search(self, text: str, limit: int) -> list[Chunk]:
        """Most relevant chunks first."""
        ...


class LexicalIndex(Protocol):
    def add(self, chunk: Chunk) -> None: ...

    def search(self, text: str, limit: int, filter: Filter | None = None) -> list[Chunk]:
        """As if only the chunks matching `filter` were indexed (RET-041)."""
        ...


class VectorIndex(Protocol):
    def add(self, chunk: Chunk, vector: Vector) -> None:
        """Raises ValueError when the vector's dimension differs from the index's (STO-011)."""
        ...

    def search(self, vector: Vector, limit: int, filter: Filter | None = None) -> list[Chunk]:
        """Nearest chunks first, by cosine similarity (RET-021); filters as for LexicalIndex."""
        ...
