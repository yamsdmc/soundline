"""Structure-aware chunking (ING-040 to ING-049).

Elements are cut into pieces that fit `max_tokens` (at sentence, then word boundaries for
prose; between rows for tables; between lines for code), then neighbouring pieces of the
same section are merged while they still fit.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from soundline.domain.markdown import Element, ParsedDocument
from soundline.domain.quotes import Span

type TokenCounter = Callable[[str], int]

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n+")
_WORD_GAP = re.compile(r"\s+")


def approximate_token_count(text: str) -> int:
    """About four characters per token. Placeholder until the Tokenizer port lands; chunk
    sizes only need to be stable and roughly proportional to model token counts."""
    return -(-len(text) // 4)


@dataclass(frozen=True)
class ChunkingSettings:
    """Everything that decides how a document is cut; part of the pipeline fingerprint."""

    max_tokens: int = 384
    section_split_level: int = 2
    count_tokens: TokenCounter = approximate_token_count


@dataclass(frozen=True)
class PlannedChunk:
    span: Span
    section_path: tuple[str, ...]


def chunk_document(
    document: ParsedDocument,
    max_tokens: int,
    count_tokens: TokenCounter,
    section_split_level: int = 2,
) -> list[PlannedChunk]:
    text = document.text
    chunks: list[PlannedChunk] = []
    headings: list[tuple[int, str]] = []
    current: PlannedChunk | None = None

    def flush() -> None:
        nonlocal current
        if current:
            chunks.append(current)
        current = None

    for element in document.elements:
        if element.kind == "heading":
            if element.level <= section_split_level:
                flush()
            headings = [h for h in headings if h[0] < element.level]
            headings.append((element.level, text[element.span.start : element.span.end]))
        path = tuple(title for _, title in headings)
        for piece in _pieces(text, element, max_tokens, count_tokens):
            if current and count_tokens(text[current.span.start : piece.end]) <= max_tokens:
                current = PlannedChunk(Span(current.span.start, piece.end), current.section_path)
            else:
                flush()
                current = PlannedChunk(piece, path)
    flush()
    return chunks


def _pieces(text: str, element: Element, max_tokens: int, count: TokenCounter) -> list[Span]:
    span = element.span
    if count(text[span.start : span.end]) <= max_tokens:
        return [span]
    if element.kind in ("table", "code"):
        units = _split(text, span, re.compile(r"\n"))
    else:
        units = _split(text, span, _SENTENCE_END)
    return [piece for unit in units for piece in _fit(text, unit, max_tokens, count)]


def _fit(text: str, span: Span, max_tokens: int, count: TokenCounter) -> list[Span]:
    """Packs the words of `span` greedily into pieces of at most `max_tokens`."""
    if count(text[span.start : span.end]) <= max_tokens:
        return [span]
    pieces: list[Span] = []
    for word in _split(text, span, _WORD_GAP):
        last = pieces[-1] if pieces else None
        if last and count(text[last.start : word.end]) <= max_tokens:
            pieces[-1] = Span(last.start, word.end)
        else:
            pieces.extend(_cut(text, word, max_tokens, count))
    return pieces


def _cut(text: str, word: Span, max_tokens: int, count: TokenCounter) -> list[Span]:
    """Last resort for a single word longer than the limit (e.g. a URL): the longest prefixes
    that fit, found by binary search; at least one character per piece."""
    pieces: list[Span] = []
    start = word.start
    while start < word.end:
        low, high = start + 1, word.end
        while low < high:
            middle = (low + high + 1) // 2
            if count(text[start:middle]) <= max_tokens:
                low = middle
            else:
                high = middle - 1
        pieces.append(Span(start, low))
        start = low
    return pieces


def _split(text: str, span: Span, gap: re.Pattern[str]) -> list[Span]:
    """Sub-spans of `span` separated by `gap` matches, without the gaps."""
    parts: list[Span] = []
    start = span.start
    for match in gap.finditer(text, span.start, span.end):
        if match.start() > start:
            parts.append(Span(start, match.start()))
        start = match.end()
    if start < span.end:
        parts.append(Span(start, span.end))
    return parts
