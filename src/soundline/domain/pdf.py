"""The text layer of a PDF, page by page (ING-025): paragraphs, with page boundaries kept.

A PDF has no reliable structure: each page's text is split into paragraphs at blank lines,
and the lines of a paragraph, wrapped by the layout, are joined with spaces.
"""

import re
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import replace

from soundline.domain.documents import Block, ParsedDocument, assemble
from soundline.domain.normalization import NormalizedText, normalize
from soundline.domain.quotes import Span

PAGE_BREAK = "\f"
"""Joins the pages' texts into the original that offsets map back to."""

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")


def parse_pdf_pages(pages: Sequence[str]) -> ParsedDocument:
    blocks: list[Block] = []
    numbers: list[int] = []
    base = 0
    for number, page in enumerate(pages, 1):
        start = 0
        for match in [*_PARAGRAPH_BREAK.finditer(page), None]:
            end = match.start() if match else len(page)
            piece = normalize(page[start:end])
            if piece.text:
                text = piece.text.replace("\n", " ")  # lines wrapped by the layout
                origins = tuple(base + start + origin for origin in piece.origins)
                blocks.append(Block("paragraph", 0, NormalizedText(text, origins, 0)))
                numbers.append(number)
            start = match.end() if match else len(page)
        base += len(page) + len(PAGE_BREAK)
    document = assemble(blocks, len(PAGE_BREAK.join(pages)))
    starts: list[tuple[int, int]] = []
    for number, element in zip(numbers, document.elements, strict=True):
        if not starts or starts[-1][0] != number:
            starts.append((number, element.span.start))
    return replace(document, pages=tuple(starts))


def page_at(pages: Sequence[tuple[int, int]], offset: int) -> int | None:
    """The page an offset of the text lies on; None for a document without pages."""
    index = bisect_right([start for _, start in pages], offset) - 1
    return pages[max(index, 0)][0] if pages else None


def pages_within(span: Span, pages: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    """The pages a span touches, each with the offset where it starts (ING-047)."""
    starts = [start for _, start in pages]
    first = max(bisect_right(starts, span.start) - 1, 0)
    last = bisect_right(starts, max(span.end - 1, span.start))
    return tuple(pages[first:last])
