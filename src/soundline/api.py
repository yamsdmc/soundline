"""The public Python API, and the composition root that wires adapters to ports (ARC-006)."""

from collections.abc import Callable, Mapping
from pathlib import Path
from types import TracebackType
from typing import Self

from soundline.application.ask import ask
from soundline.application.hybrid_retriever import HybridRetriever
from soundline.application.ingest import IngestionStatus, Ingestor
from soundline.application.pipeline import check_pipeline, pipeline_manifest
from soundline.application.ports import Embedder, Index, LanguageModel
from soundline.domain.answers import Answer
from soundline.domain.chunking import ChunkingSettings
from soundline.domain.filters import Filter, Metadata, parse_filter
from soundline.domain.hits import Hit
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
        llm: LanguageModel,
        chunking: ChunkingSettings | None = None,
        close: Callable[[], object] = lambda: None,
    ) -> None:
        chunking = chunking or ChunkingSettings()
        self._index = index
        self._documents = index.documents
        self._manifest = pipeline_manifest(embedder, chunking)
        self._ingestor = Ingestor(index, embedder, chunking)
        self._retriever = HybridRetriever(index.lexical, index.dense, embedder)
        self._llm = llm
        self._close = close

    @classmethod
    def open(
        cls,
        home: str | Path,
        llm: LanguageModel,
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
        )
        return cls(index, embedder, llm, chunking, close=database.close)

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
        self._close()

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
        return ask(question, self._retriever, self._llm)


def _default_embedder() -> Embedder:
    from soundline.adapters.embedders.fastembed import FastembedEmbedder  # noqa: PLC0415

    return FastembedEmbedder("intfloat/multilingual-e5-large")  # CFG-023
