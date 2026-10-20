"""HTML → structural elements over one normalized text (ING-021 to ING-024).

Origins point to where each piece of text starts in the HTML source. Inside a text node
they are exact unless entities were decoded (`&amp;`), in which case they are approximate.
"""

from html.parser import HTMLParser
from itertools import accumulate

from soundline.domain.documents import Block, ParsedDocument, assemble
from soundline.domain.normalization import NormalizedText, normalize

_NOT_CONTENT = {"script", "style", "nav", "footer", "aside", "noscript", "template", "svg", "head"}
_HEADINGS = {f"h{level}": level for level in range(1, 7)}
_PARAGRAPHS = {"p", "blockquote", "dd", "dt", "figcaption", "caption"}
_CONTAINERS = {"div", "section", "article", "main", "body", "header", "ul", "ol", "br", "hr"}

type _Chars = list[tuple[str, int]]


def parse_html(raw: str) -> ParsedDocument:
    parser = _Parser(raw)
    parser.feed(raw)
    parser.close()
    return assemble(parser.blocks, len(raw))


class _Parser(HTMLParser):
    def __init__(self, raw: str) -> None:
        super().__init__(convert_charrefs=True)
        self._line_starts = list(
            accumulate((len(line) for line in raw.splitlines(True)), initial=0)
        )
        self.blocks: list[Block] = []
        self._skipping = 0
        self._kind: str | None = None
        self._level = 0
        self._chars: _Chars = []
        self._rows: list[tuple[bool, list[_Chars]]] | None = None
        self._cell: _Chars | None = None

    # --- structure -------------------------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _NOT_CONTENT:
            self._skipping += 1
        elif self._skipping:
            return
        elif tag == "table":
            self._flush()
            self._rows = []
        elif self._rows is not None:
            if tag == "tr":
                self._rows.append((False, []))
            elif tag in ("td", "th") and self._rows:
                self._cell = []
                self._rows[-1][1].append(self._cell)
                if tag == "th":
                    self._rows[-1] = (True, self._rows[-1][1])
        elif tag in _HEADINGS:
            self._start("heading", _HEADINGS[tag])
        elif tag in _PARAGRAPHS:
            self._start("paragraph")
        elif tag == "li":
            self._start("list_item")
        elif tag == "pre":
            self._start("code")
        elif tag in _CONTAINERS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in _NOT_CONTENT:
            self._skipping = max(0, self._skipping - 1)
        elif self._skipping:
            return
        elif tag == "table" and self._rows is not None:
            self._emit_table(self._rows)
            self._rows = self._cell = None
        elif tag in ("td", "th"):
            self._cell = None
        elif tag in _HEADINGS or tag in _PARAGRAPHS or tag in ("li", "pre") or tag in _CONTAINERS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skipping:
            return
        origin = self._offset()
        chars = [(char, min(origin + i, origin + len(data))) for i, char in enumerate(data)]
        if self._rows is not None:
            if self._cell is not None:
                self._cell.extend(chars)
            return
        if self._kind is None:
            if not data.strip():
                return
            self._start("paragraph")  # text directly in a container
        self._chars.extend(chars)

    # --- blocks ----------------------------------------------------------------------------

    def _start(self, kind: str, level: int = 0) -> None:
        self._flush()
        self._kind, self._level = kind, level

    def _flush(self) -> None:
        if self._kind is not None:
            text = _verbatim(self._chars) if self._kind == "code" else _normalized(self._chars)
            self.blocks.append(Block(self._kind, self._level, text))
        self._kind, self._level, self._chars = None, 0, []

    def _emit_table(self, rows: list[tuple[bool, list[_Chars]]]) -> None:
        """One Markdown table (ING-024): every character of a row maps to its first cell."""
        chars: _Chars = []
        for index, cells in enumerate(cells for _, cells in rows if cells):
            texts = [_normalized(cell) for cell in cells]
            origin = next((t.origins[0] for t in texts if t.origins), chars[-1][1] if chars else 0)
            line = "| " + " | ".join(t.text for t in texts) + " |"
            lines = [line, "|" + "---|" * len(cells)] if index == 0 else [line]
            for text in lines:
                if chars:
                    chars.append(("\n", origin))
                chars.extend((char, origin) for char in text)
        text = "".join(char for char, _ in chars)
        self.blocks.append(Block("table", 0, NormalizedText(text, tuple(o for _, o in chars), 0)))

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_starts[min(line - 1, len(self._line_starts) - 1)] + column


def _normalized(chars: _Chars) -> NormalizedText:
    piece = normalize("".join(char for char, _ in chars))
    return NormalizedText(piece.text, tuple(chars[i][1] for i in piece.origins), 0)


def _verbatim(chars: _Chars) -> NormalizedText:
    """Code keeps its whitespace; surrounding blank lines and CRLF are dropped (ING-020)."""
    kept = [(c, o) for c, o in chars if c != "\r"]
    start = next((i for i, (c, _) in enumerate(kept) if c != "\n"), len(kept))
    end = len(kept) - next((i for i, (c, _) in enumerate(reversed(kept)) if c != "\n"), len(kept))
    kept = kept[start:end]
    return NormalizedText("".join(c for c, _ in kept), tuple(o for _, o in kept), 0)
