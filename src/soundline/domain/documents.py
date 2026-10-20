"""Parsed documents: structural elements over one normalized text (ING-020 to ING-022)."""

from collections.abc import Sequence
from dataclasses import dataclass

from soundline.domain.normalization import NormalizedText
from soundline.domain.quotes import Span

_SEPARATOR = "\n\n"


@dataclass(frozen=True)
class Element:
    kind: str  # heading | paragraph | list_item | table | code
    span: Span
    level: int = 0  # heading level, 0 otherwise


@dataclass(frozen=True)
class ParsedDocument(NormalizedText):
    elements: tuple[Element, ...] = ()


@dataclass(frozen=True)
class Block:
    """An element before assembly: its kind, level and normalized text with origins."""

    kind: str
    level: int
    text: NormalizedText


def assemble(blocks: Sequence[Block], original_length: int) -> ParsedDocument:
    """Joins non-empty blocks with blank lines into one document; every character keeps its
    origin in the original (separators take the origin of the block they introduce)."""
    text, origins, elements = "", list[int](), list[Element]()
    for block in (b for b in blocks if b.text.text):
        if text:
            text += _SEPARATOR
            origins += [block.text.origins[0]] * len(_SEPARATOR)
        span = Span(len(text), len(text) + len(block.text.text))
        elements.append(Element(block.kind, span, block.level))
        text += block.text.text
        origins += block.text.origins
    return ParsedDocument(text, tuple(origins), original_length, tuple(elements))
