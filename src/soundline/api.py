"""The public Python API, and the composition root that wires adapters to ports (ARC-006)."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import Self

from soundline.application.ask import ask
from soundline.application.hybrid_retriever import HybridRetriever
from soundline.application.ingest import IngestionReport, IngestionStatus, Ingestor
from soundline.application.ingest_sources import ingest_sources
from soundline.application.pipeline import check_pipeline, pipeline_manifest
from soundline.application.ports import Embedder, Index, LanguageModel, SourceReader
from soundline.domain.answers import Answer
from soundline.domain.chunking import ChunkingSettings
from soundline.domain.errors import ConfigurationError
from soundline.domain.filters import Filter, Metadata, parse_filter
from soundline.domain.hits import Hit
from soundline.domain.manifest import Manifest
from soundline.testing import (
    HashingEmbedder,
    InMemoryDocumentStore,
    InMemoryIndex,
    InMemoryManifestStore,
    InMemoryVectorIndex,
)


class Soundline:
    def __init__(
        self,
        index: Index,
        embedder: Embedder,
        llm: LanguageModel | None,
        chunking: ChunkingSettings | None = None,
        *,
        reader: SourceReader | None = None,
    ) -> None:
        chunking = chunking or ChunkingSettings()
        self._index = index
        self._documents = index.documents
        self._manifest = pipeline_manifest(embedder, chunking)
        self._ingestor = Ingestor(index, embedder, chunking)
        self._retriever = HybridRetriever(index.lexical, index.dense, embedder)
        self._llm = llm
        self._reader = reader or _local_files()

    @classmethod
    def open(
        cls,
        home: str | Path,
        llm: LanguageModel | None = None,
        embedder: Embedder | None = None,
        chunking: ChunkingSettings | None = None,
    ) -> Self:
        """A persistent index in `home` (one SQLite file, STO-040)."""
        from soundline.adapters.stores.sqlite import (  # noqa: PLC0415  # composition only
            SqliteDocumentStore,
            SqliteLexicalIndex,
            SqliteManifestStore,
            SqliteVectorIndex,
            open_database,
        )

        embedder = embedder or _default_embedder()
        Path(home).mkdir(parents=True, exist_ok=True)
        database = open_database(str(Path(home) / "index.db"))
        index = Index(
            SqliteDocumentStore(database),
            SqliteLexicalIndex(database),
            SqliteVectorIndex(database, embedder.dimension),
            SqliteManifestStore(database),
            transaction=lambda: database,  # commits on success, rolls back on error
            close=database.close,
        )
        return cls(index, embedder, llm, chunking)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._index.close()

    @classmethod
    def in_memory(
        cls, llm: LanguageModel, embedder: Embedder | None = None, max_tokens: int = 384
    ) -> Self:
        """A non-persistent, offline instance, for tests and notebooks."""
        embedder = embedder or HashingEmbedder()
        dense = InMemoryVectorIndex(embedder.dimension)
        index = Index(InMemoryDocumentStore(), InMemoryIndex(), dense, InMemoryManifestStore())
        return cls(index, embedder, llm, ChunkingSettings(max_tokens=max_tokens))

    def ingest_text(
        self, source: str, text: str, metadata: Metadata | None = None
    ) -> IngestionStatus:
        """Parses Markdown (plain text is valid Markdown), chunks it and indexes the chunks.

        Unchanged content is a no-op (ING-007); changed content replaces the source (ING-009).
        """
        return self._ingestor.ingest_text(source, text, metadata)

    def ingest(self, inputs: Sequence[str | Path]) -> IngestionReport:
        """Files and directories, recursively. Never deletes anything (ING-011)."""
        return ingest_sources(
            [str(i) for i in inputs], self._reader, self._ingestor, self._documents
        )

    def sync(self, inputs: Sequence[str | Path]) -> IngestionReport:
        """Like ingest, and deletes documents under `inputs` whose files disappeared (ING-011)."""
        return ingest_sources(
            [str(i) for i in inputs],
            self._reader,
            self._ingestor,
            self._documents,
            delete_missing=True,
        )

    def document_text(self, source: str) -> str:
        """The normalized text that chunk and citation spans refer to."""
        document = self._documents.get(source)
        if document is None:
            raise KeyError(source)
        return document.text

    def search(
        self, query: str, k: int = 8, filters: Filter | Mapping[str, object] | None = None
    ) -> list[Hit]:
        """`filters` is a builder filter (`F.eq(...)`) or its canonical JSON form (API-002)."""
        condition = parse_filter(filters) if isinstance(filters, Mapping) else filters
        check_pipeline(self._index.manifest, self._manifest)  # STO-012
        return self._retriever.hits(query, k, condition)

    def ask(self, question: str) -> Answer:
        if self._llm is None:
            raise ConfigurationError(  # CLI-004
                "asking needs a language model; configure one (generation.model) or use search"
            )
        return ask(question, self._retriever, self._llm)

    def manifest(self) -> Manifest | None:
        """How this index was built, or None while it is empty (STO-004)."""
        return self._index.manifest.load()


DEFAULT_EMBEDDER = "fastembed:intfloat/multilingual-e5-large"  # CFG-023


def embedder_from_spec(spec: str) -> Embedder:
    """`<provider>:<model>` (CFG-010): `fastembed:<model>`, or `hashing:<dimension>` (offline,
    deterministic, no semantics: for tests and demos)."""
    provider, _, model = spec.partition(":")
    if provider == "fastembed" and model:
        from soundline.adapters.embedders.fastembed import FastembedEmbedder  # noqa: PLC0415

        return FastembedEmbedder(model)
    if provider == "hashing" and model.isdigit():
        return HashingEmbedder(dimension=int(model))
    raise ConfigurationError(
        f"unknown embedder {spec!r}; use 'fastembed:<model>' or 'hashing:<dimension>'"
    )


def _default_embedder() -> Embedder:
    return embedder_from_spec(DEFAULT_EMBEDDER)


def _local_files() -> SourceReader:
    from soundline.adapters.sources.local_files import LocalFiles  # noqa: PLC0415

    return LocalFiles()
