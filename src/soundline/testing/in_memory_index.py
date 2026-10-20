import re

from soundline.domain.chunks import Chunk
from soundline.domain.filters import Filter, matches

_TERM = re.compile(r"\w+")


def _terms(text: str) -> set[str]:
    return set(_TERM.findall(text.lower()))


class InMemoryIndex:
    """Fake lexical index: ranks chunks by the number of distinct query terms they contain."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []

    def add(self, chunk: Chunk) -> None:
        self._chunks.append(chunk)

    def remove(self, source: str) -> None:
        self._chunks = [chunk for chunk in self._chunks if chunk.source != source]

    def search(self, text: str, limit: int, filter: Filter | None = None) -> list[Chunk]:
        query = _terms(text)
        candidates = [c for c in self._chunks if filter is None or matches(filter, c.metadata)]
        scored = [(len(query & _terms(chunk.text)), chunk) for chunk in candidates]
        ranked = sorted((pair for pair in scored if pair[0] > 0), key=lambda pair: -pair[0])
        return [chunk for _, chunk in ranked[:limit]]
