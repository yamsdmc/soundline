"""The public Python API, and the composition root that wires adapters to ports (ARC-006)."""

from collections.abc import Mapping
from typing import Self

from soundline.application.ask import ask
from soundline.application.hybrid_retriever import HybridRetriever
from soundline.application.ports import Embedder, LanguageModel, LexicalIndex, VectorIndex
from soundline.domain.answers import Answer
from soundline.domain.chunking import TokenCounter, approximate_token_count, chunk_document
from soundline.domain.chunks import Chunk
from soundline.domain.filters import Filter, Metadata, parse_filter
from soundline.domain.hits import Hit
from soundline.domain.markdown import parse_markdown
from soundline.testing import HashingEmbedder, InMemoryIndex, InMemoryVectorIndex


class Soundline:
    def __init__(
        self,
        lexical: LexicalIndex,
        dense: VectorIndex,
        embedder: Embedder,
        llm: LanguageModel,
        *,
        max_tokens: int = 384,
        count_tokens: TokenCounter = approximate_token_count,
    ) -> None:
        self._max_tokens = max_tokens
        self._count_tokens = count_tokens
        self._documents: dict[str, str] = {}
        self._lexical = lexical
        self._dense = dense
        self._embedder = embedder
        self._retriever = HybridRetriever(lexical, dense, embedder)
        self._llm = llm

    @classmethod
    def in_memory(
        cls, llm: LanguageModel, embedder: Embedder | None = None, max_tokens: int = 384
    ) -> Self:
        """A non-persistent, offline instance, for tests and notebooks."""
        embedder = embedder or HashingEmbedder()
        dense = InMemoryVectorIndex(embedder.dimension)
        return cls(InMemoryIndex(), dense, embedder, llm, max_tokens=max_tokens)

    def ingest_text(self, source: str, text: str, metadata: Metadata | None = None) -> None:
        """Parses Markdown (plain text is valid Markdown), chunks it and indexes the chunks."""
        document = parse_markdown(text)
        self._documents[source] = document.text
        chunks = [
            Chunk(
                source=source,
                text=document.text[planned.span.start : planned.span.end],
                span=planned.span,
                metadata=metadata or {},
                section_path=planned.section_path,
            )
            for planned in chunk_document(document, self._max_tokens, self._count_tokens)
        ]
        vectors = self._embedder.embed_documents([chunk.text for chunk in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._lexical.add(chunk)
            self._dense.add(chunk, vector)

    def document_text(self, source: str) -> str:
        """The normalized text that chunk and citation spans refer to."""
        return self._documents[source]

    def search(
        self, query: str, k: int = 8, filters: Filter | Mapping[str, object] | None = None
    ) -> list[Hit]:
        """`filters` is a builder filter (`F.eq(...)`) or its canonical JSON form (API-002)."""
        condition = parse_filter(filters) if isinstance(filters, Mapping) else filters
        return self._retriever.hits(query, k, condition)

    def ask(self, question: str) -> Answer:
        return ask(question, self._retriever, self._llm)
