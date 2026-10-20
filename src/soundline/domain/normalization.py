import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedText:
    """Normalized text and, for each of its characters, the offset it came from (ING-021)."""

    text: str
    origins: tuple[int, ...]
    original_length: int

    def original_offset(self, offset: int) -> int:
        """Maps a normalized offset back to the original text; `len(text)` maps past the end."""
        if offset < len(self.origins):
            return self.origins[offset]
        return self.origins[-1] + 1 if self.origins else 0


def normalize(raw: str) -> NormalizedText:
    """NFC, `\\n` line endings, single spaces, at most one blank line, trimmed (ING-020)."""
    out: list[tuple[str, int]] = []
    for char, origin in _without_carriage_returns(_composed(raw)):
        if char == "\n":
            while out and out[-1][0] == " ":
                out.pop()
            if len(out) >= 2 and out[-1][0] == out[-2][0] == "\n":
                continue
            out.append(("\n", origin))
        elif char.isspace():
            if out and out[-1][0] in " \n":
                continue
            out.append((" ", origin))
        else:
            out.append((char, origin))
    while out and out[0][0] in " \n":
        out.pop(0)
    while out and out[-1][0] in " \n":
        out.pop()
    return NormalizedText(
        "".join(char for char, _ in out), tuple(origin for _, origin in out), len(raw)
    )


def _composed(raw: str) -> list[tuple[str, int]]:
    """NFC per cluster (a base character and its combining marks), keeping cluster origins."""
    composed: list[tuple[str, int]] = []
    start = 0
    for end in range(1, len(raw) + 1):
        if end == len(raw) or not unicodedata.combining(raw[end]):
            composed.extend((char, start) for char in unicodedata.normalize("NFC", raw[start:end]))
            start = end
    return composed


def _without_carriage_returns(chars: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """CRLF and lone CR become LF, mapped to where the original line break starts."""
    result: list[tuple[str, int]] = []
    for char, origin in chars:
        if char == "\n" and result and result[-1][0] == "\r":
            result[-1] = ("\n", result[-1][1])
        else:
            result.append((char, origin))
    return [("\n", origin) if char == "\r" else (char, origin) for char, origin in result]
