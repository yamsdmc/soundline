"""The public Python API, and the composition root that wires adapters to ports (ARC-006)."""

import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from soundline.application.ask import GenerationSettings, ask
from soundline.application.diagnostics import Check, diagnose
from soundline.application.evaluate import DatasetFile, EvalSettings, run_retrieval_eval
from soundline.application.hybrid_retriever import HybridRetriever
from soundline.application.ingest import IngestionReport, IngestionStatus, Ingestor
from soundline.application.ingest_sources import ingest_sources
from soundline.application.pipeline import check_pipeline, pipeline_manifest
from soundline.application.ports import Embedder, Index, LanguageModel, RunStore, SourceReader
from soundline.domain.answers import Answer
from soundline.domain.chunking import ChunkingSettings
from soundline.domain.datasets import DatasetError
from soundline.domain.errors import ConfigurationError
from soundline.domain.filters import Filter, Metadata, parse_filter
from soundline.domain.hits import Hit, SearchResult
from soundline.domain.manifest import Manifest
from soundline.domain.runs import EvalRun
from soundline.testing import (
    HashingEmbedder,
    InMemoryDocumentStore,
    InMemoryIndex,
    InMemoryManifestStore,
    InMemoryRunStore,
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
        runs: RunStore | None = None,
        generation: GenerationSettings | None = None,
    ) -> None:
        chunking = chunking or ChunkingSettings()
        self._index = index
        self._embedder = embedder
        self._documents = index.documents
        self._manifest = pipeline_manifest(embedder, chunking)
        self._ingestor = Ingestor(index, embedder, chunking)
        self._retriever = HybridRetriever(index.lexical, index.dense, embedder)
        self._llm = llm
        self._reader = reader or _local_files()
        self._runs = runs or InMemoryRunStore()
        self._generation = generation or GenerationSettings()

    @classmethod
    def open(
        cls,
        home: str | Path,
        llm: LanguageModel | None = None,
        embedder: Embedder | None = None,
        chunking: ChunkingSettings | None = None,
        *,
        generation: GenerationSettings | None = None,
    ) -> Self:
        """A persistent index in `home` (one SQLite file, STO-040)."""
        from soundline.adapters.stores.sqlite import (  # noqa: PLC0415  # composition only
            SqliteDocumentStore,
            SqliteLexicalIndex,
            SqliteManifestStore,
            SqliteVectorIndex,
            describe_database,
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
            describe=lambda: describe_database(database),
        )
        from soundline.adapters.evals.json_files import JsonRunStore  # noqa: PLC0415

        runs = JsonRunStore(Path(home) / "evals" / "runs")
        return cls(index, embedder, llm, chunking, runs=runs, generation=generation)

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
        cls,
        llm: LanguageModel,
        embedder: Embedder | None = None,
        max_tokens: int = 384,
        *,
        generation: GenerationSettings | None = None,
    ) -> Self:
        """A non-persistent, offline instance, for tests and notebooks."""
        embedder = embedder or HashingEmbedder()
        dense = InMemoryVectorIndex(embedder.dimension)
        index = Index(InMemoryDocumentStore(), InMemoryIndex(), dense, InMemoryManifestStore())
        return cls(
            index, embedder, llm, ChunkingSettings(max_tokens=max_tokens), generation=generation
        )

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
        return self.search_result(query, k, filters).hits

    def search_result(
        self, query: str, k: int = 8, filters: Filter | Mapping[str, object] | None = None
    ) -> SearchResult:
        """Like search, and says whether a retriever failed and the result is degraded."""
        condition = parse_filter(filters) if isinstance(filters, Mapping) else filters
        check_pipeline(self._index.manifest, self._manifest)  # STO-012
        return self._retriever.search_result(query, k, condition)

    def ask(self, question: str) -> Answer:
        if self._llm is None:
            raise ConfigurationError(  # CLI-004
                "asking needs a language model: set SOUNDLINE_LLM (e.g."
                " anthropic:claude-sonnet-5-5), or use search, which needs none"
            )
        return ask(question, self._retriever, self._llm, self._generation)

    def evaluate(
        self,
        dataset: str | Path,
        name: str | None = None,
        ks: Sequence[int] = (1, 3, 5, 10),
        *,
        allow_missing_sources: bool = False,
    ) -> EvalRun:
        """Retrieval-only evaluation of a JSONL dataset; the run is stored (EVL-060, EVL-062)."""
        check_pipeline(self._index.manifest, self._manifest)
        if not Path(dataset).is_file():
            raise DatasetError(f"dataset file not found: {dataset}")
        run = run_retrieval_eval(
            name or datetime.now(UTC).strftime("run-%Y%m%d-%H%M%S"),
            DatasetFile(str(dataset), Path(dataset).read_text(encoding="utf-8")),
            self._index,
            self._retriever.hits,
            EvalSettings(tuple(ks), allow_missing_sources),
        )
        self._runs.save(run)
        return run

    def load_run(self, name_or_path: str) -> EvalRun:
        return self._runs.load(name_or_path)

    def diagnose(self) -> list[Check]:
        """Checks storage, embedder and index compatibility with real calls (CLI-005)."""
        return diagnose(self._index, self._embedder, self._manifest)

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


def llm_from_spec(spec: str) -> LanguageModel:
    """`<provider>:<model>` (CFG-010), e.g. `anthropic:claude-sonnet-5-5`."""
    provider, _, model = spec.partition(":")
    if provider == "anthropic" and model:
        try:
            from soundline.adapters.llms.anthropic import AnthropicLanguageModel  # noqa: PLC0415
        except ImportError as error:  # ARC-012, CFG-014
            raise ConfigurationError(
                'the Anthropic provider needs: pip install "soundline[anthropic]"'
            ) from error
        return AnthropicLanguageModel(model)
    if provider in ("openai", "ollama") and model:
        try:
            from soundline.adapters.llms.openai_compatible import (  # noqa: PLC0415
                OpenAICompatibleLanguageModel,
            )
        except ImportError as error:  # ARC-012, CFG-014
            raise ConfigurationError(
                'OpenAI-compatible providers need: pip install "soundline[openai]"'
            ) from error
        if provider == "openai":
            return OpenAICompatibleLanguageModel(model)
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        # Local models: deterministic sampling, the lenient parser for loose JSON (CFG-013), and
        # no thinking: minutes of reasoning per answer on a laptop, for an answer verified anyway.
        import openai  # noqa: PLC0415

        client = openai.OpenAI(base_url=f"{host}/v1", api_key="ollama")
        return OpenAICompatibleLanguageModel(
            model, client, temperature=0.0, reasoning_effort="none", provider="ollama"
        )
    raise ConfigurationError(
        f"unknown language model {spec!r}; use anthropic:<model>, openai:<model> or ollama:<model>"
    )


def _default_embedder() -> Embedder:
    return embedder_from_spec(DEFAULT_EMBEDDER)


def _local_files() -> SourceReader:
    from soundline.adapters.sources.local_files import LocalFiles  # noqa: PLC0415

    return LocalFiles()
