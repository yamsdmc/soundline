"""Markdown → structural elements over one normalized text (ING-020 to ING-022, ING-024)."""

import re
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from itertools import accumulate

from soundline.domain.documents import Block, ParsedDocument, assemble
from soundline.domain.normalization import NormalizedText, normalize

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")
_LIST_ITEM = re.compile(r"^[ \t]*([-*+]|\d+[.)])[ \t]+\S")
_FENCE = "```"


@dataclass(frozen=True)
class _Line:
    start: int  # offset of the line in the original text
    content: str  # without its line break

    @property
    def end(self) -> int:
        return self.start + len(self.content)

    @property
    def blank(self) -> bool:
        return not self.content.strip()

    @property
    def stripped(self) -> str:
        return self.content.lstrip()


def parse_markdown(raw: str) -> ParsedDocument:
    return assemble(_blocks(_lines(raw)), len(raw))


def _lines(raw: str) -> list[_Line]:
    lines: list[_Line] = []
    start = 0
    for line in raw.splitlines(keepends=True):
        lines.append(_Line(start, line.rstrip("\r\n")))
        start += len(line)
    return lines


def _blocks(lines: list[_Line]) -> list[Block]:
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.blank:
            i += 1
        elif line.stripped.startswith(_FENCE):
            end = _next(lines, i + 1, lambda line: line.stripped.startswith(_FENCE))
            blocks.append(Block("code", 0, _verbatim(lines[i + 1 : end])))
            i = end + 1
        elif heading := _HEADING.match(line.content):
            title = _shifted(normalize(heading.group(2)), line.start + heading.start(2))
            blocks.append(Block("heading", len(heading.group(1)), title))
            i += 1
        elif line.stripped.startswith("|"):
            end = _next(lines, i, lambda line: not line.stripped.startswith("|"))
            blocks.append(Block("table", 0, _normalized(lines[i:end])))
            i = end
        elif _LIST_ITEM.match(line.content):
            blocks.append(Block("list_item", 0, _normalized([line])))
            i += 1
        else:
            end = _next(lines, i + 1, _starts_block)
            blocks.append(Block("paragraph", 0, _normalized(lines[i:end])))
            i = end
    return blocks


def _next(lines: list[_Line], start: int, condition: Callable[[_Line], bool]) -> int:
    """Index of the first line from `start` meeting `condition`, or len(lines)."""
    return next((j for j in range(start, len(lines)) if condition(lines[j])), len(lines))


def _starts_block(line: _Line) -> bool:
    return (
        line.blank
        or line.stripped.startswith((_FENCE, "|"))
        or bool(_HEADING.match(line.content) or _LIST_ITEM.match(line.content))
    )


def _normalized(lines: list[_Line]) -> NormalizedText:
    """Normalizes consecutive lines as one segment, mapping back through each line's start."""
    local_starts = list(accumulate((len(line.content) + 1 for line in lines[:-1]), initial=0))
    piece = normalize("\n".join(line.content for line in lines))

    def original(local: int) -> int:
        k = bisect_right(local_starts, local) - 1
        return lines[k].start + (local - local_starts[k])

    return NormalizedText(piece.text, tuple(map(original, piece.origins)), piece.original_length)


def _verbatim(lines: list[_Line]) -> NormalizedText:
    """Code keeps its whitespace: only line endings are unified (ING-020)."""
    while lines and lines[-1].blank:
        lines = lines[:-1]
    chars: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        if index:
            chars.append(("\n", lines[index - 1].end))
        chars.extend((char, line.start + offset) for offset, char in enumerate(line.content))
    return NormalizedText("".join(c for c, _ in chars), tuple(o for _, o in chars), 0)


def _shifted(piece: NormalizedText, base: int) -> NormalizedText:
    return NormalizedText(piece.text, tuple(base + o for o in piece.origins), piece.original_length)
