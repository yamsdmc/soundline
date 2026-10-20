"""Ports: what the application needs from the outside world (see docs/spec/02-architecture.md)."""

from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from typing import Protocol

from soundline.domain.chunks import Chunk
from soundline.domain.filters import Filter
from soundline.domain.manifest import Manifest


@dataclass(frozen=True)
class StoredDocument:
    source: str
    revision: str
    """Content hash of the document's raw bytes."""
    text: str
    """Normalized text, which chunk and citation spans refer to."""


class DocumentStore(Protocol):
    def get(self, source: str) -> StoredDocument | None: ...

    def save(self, document: StoredDocument) -> None:
        """Inserts or replaces the document of `document.source`."""
        ...

    def remove(self, source: str) -> None: ...

    def sources(self) -> list[str]:
        """Sorted."""
        ...


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
    def model_id(self) -> str:
        """Names the embedding space: vectors from different model IDs never mix (ING-073)."""
        ...

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

    def remove(self, source: str) -> None:
        """Removes every chunk of `source`."""
        ...

    def search(self, text: str, limit: int, filter: Filter | None = None) -> list[Chunk]:
        """As if only the chunks matching `filter` were indexed (RET-041)."""
        ...


class VectorIndex(Protocol):
    def add(self, chunk: Chunk, vector: Vector) -> None:
        """Raises ValueError when the vector's dimension differs from the index's (STO-011)."""
        ...

    def remove(self, source: str) -> None:
        """Removes every chunk of `source`."""
        ...

    def search(self, vector: Vector, limit: int, filter: Filter | None = None) -> list[Chunk]:
        """Nearest chunks first, by cosine similarity (RET-021); filters as for LexicalIndex."""
        ...


class ManifestStore(Protocol):
    def load(self) -> Manifest | None: ...

    def save(self, manifest: Manifest) -> None: ...


@dataclass(frozen=True)
class Index:
    """All persisted data of a corpus (see the glossary): documents, both search indexes and
    the manifest, plus how to make several writes atomic (STO-020)."""

    documents: DocumentStore
    lexical: LexicalIndex
    dense: VectorIndex
    manifest: ManifestStore
    transaction: Callable[[], AbstractContextManager[object]] = field(default=nullcontext)
