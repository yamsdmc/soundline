"""The public Python API, and the composition root that wires adapters to ports (ARC-006)."""

from typing import Self

from soundline.application.ask import ask
from soundline.application.hybrid_retriever import HybridRetriever
from soundline.application.ports import Embedder, LanguageModel, LexicalIndex, VectorIndex
from soundline.domain.answers import Answer
from soundline.domain.chunks import Chunk
from soundline.domain.hits import Hit
from soundline.domain.quotes import Span
from soundline.testing import HashingEmbedder, InMemoryIndex, InMemoryVectorIndex


class Soundline:
    def __init__(
        self,
        lexical: LexicalIndex,
        dense: VectorIndex,
        embedder: Embedder,
        llm: LanguageModel,
    ) -> None:
        self._lexical = lexical
        self._dense = dense
        self._embedder = embedder
        self._retriever = HybridRetriever(lexical, dense, embedder)
        self._llm = llm

    @classmethod
    def in_memory(cls, llm: LanguageModel, embedder: Embedder | None = None) -> Self:
        """A non-persistent, offline instance, for tests and notebooks."""
        embedder = embedder or HashingEmbedder()
        return cls(InMemoryIndex(), InMemoryVectorIndex(embedder.dimension), embedder, llm)

    def ingest_text(self, source: str, text: str) -> None:
        chunk = Chunk(source=source, text=text, span=Span(0, len(text)))
        self._lexical.add(chunk)
        self._dense.add(chunk, self._embedder.embed_documents([chunk.text])[0])

    def search(self, query: str, k: int = 8) -> list[Hit]:
        return self._retriever.hits(query, k)

    def ask(self, question: str) -> Answer:
        return ask(question, self._retriever, self._llm)
