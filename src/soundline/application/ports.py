"""Ports: what the application needs from the outside world (see docs/spec/02-architecture.md)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from soundline.domain.chunks import Chunk


@dataclass(frozen=True)
class GenerationRequest:
    system: str
    prompt: str


class LanguageModel(Protocol):
    def generate(self, request: GenerationRequest) -> Mapping[str, object]:
        """Returns the model's structured output."""
        ...


class LexicalIndex(Protocol):
    def add(self, chunk: Chunk) -> None: ...

    def search(self, text: str, limit: int) -> list[Chunk]: ...
