"""The public Python API, and the composition root that wires adapters to ports (ARC-006)."""

from typing import Self

from soundline.application.ask import ask
from soundline.application.ports import LanguageModel, LexicalIndex
from soundline.domain.answers import Answer
from soundline.domain.chunks import Chunk
from soundline.domain.quotes import Span
from soundline.testing import InMemoryIndex


class Soundline:
    def __init__(self, index: LexicalIndex, llm: LanguageModel) -> None:
        self._index = index
        self._llm = llm

    @classmethod
    def in_memory(cls, llm: LanguageModel) -> Self:
        """A non-persistent instance, for tests and notebooks."""
        return cls(InMemoryIndex(), llm)

    def ingest_text(self, source: str, text: str) -> None:
        self._index.add(Chunk(source=source, text=text, span=Span(0, len(text))))

    def ask(self, question: str) -> Answer:
        return ask(question, self._index, self._llm)
