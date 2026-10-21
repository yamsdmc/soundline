"""Ports: what the application needs from the outside world (see docs/spec/02-architecture.md)."""

from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from typing import Protocol

from soundline.domain.calibration import Calibration
from soundline.domain.chunks import Chunk
from soundline.domain.filters import Filter
from soundline.domain.manifest import Manifest
from soundline.domain.runs import EvalRun
from soundline.domain.usage import TokenUsage


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
class OutputFormat:
    """A strict JSON schema the model's output must follow (GEN-012)."""

    name: str
    schema: Mapping[str, object]


@dataclass(frozen=True)
class GenerationRequest:
    system: str
    prompt: str
    output: OutputFormat


@dataclass(frozen=True)
class Generation:
    text: str
    """The model's raw output; parsing it is the application's job."""
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: float | None = None
    """Duration of the original model call, when known (kept by the cache, EVL-030)."""
    cached: bool = False


class LanguageModel(Protocol):
    @property
    def model_id(self) -> str:
        """`<provider>:<model>` (CFG-010), the key of the price table (GEN-070)."""
        ...

    def generate(self, request: GenerationRequest) -> Generation: ...


class GenerationCache(Protocol):
    """Model outputs by request key, so evaluation runs are reproducible (EVL-061)."""

    def get(self, key: str) -> Generation | None: ...

    def put(self, key: str, generation: Generation) -> None: ...


type Vector = tuple[float, ...]


class Embedder(Protocol):
    @property
    def model_id(self) -> str:
        """Names the embedding space: vectors from different model IDs never mix (ING-073)."""
        ...

    @property
    def dimension(self) -> int: ...

    @property
    def max_input_tokens(self) -> int:
        """Longest input the model reads without truncating, in its own tokens (ING-041)."""
        ...

    def count_tokens(self, text: str) -> int:
        """In the model's own tokenizer, which can count far more than a generic one."""
        ...

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


@dataclass(frozen=True)
class Discovery:
    sources: list[str]
    """URIs of every regular file found, supported or not, sorted."""
    scopes: list[str]
    """URIs of the inputs themselves: what a sync is allowed to delete under."""
    missing: list[str] = field(default_factory=list[str])
    """Inputs that do not exist, so that a typo is reported rather than ignored."""


class SourceReader(Protocol):
    def discover(self, inputs: Sequence[str]) -> Discovery:
        """Files and directories (recursively); hidden entries and symlinks are skipped."""
        ...

    def read(self, uri: str) -> bytes: ...


class RunStore(Protocol):
    def save(self, run: EvalRun) -> str:
        """Returns where the run was stored."""
        ...

    def load(self, name_or_path: str) -> EvalRun: ...

    def save_calibration(self, calibration: Calibration) -> None:
        """Replaces any calibration of the same judge model and version (EVL-043)."""
        ...

    def calibration(self, judge_model: str, judge_version: str) -> Calibration | None: ...


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
    close: Callable[[], object] = field(default=lambda: None)
    """Releases the index's resources (e.g. its database connection)."""
    describe: Callable[[], str] = field(default=lambda: "in-memory store")
    """What the storage is, for diagnostics (e.g. SQLite binding and versions)."""
