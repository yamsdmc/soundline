from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """A half-open range [start, end) of code-point offsets in a text."""

    start: int
    end: int

    def shifted_by(self, offset: int) -> "Span":
        return Span(self.start + offset, self.end + offset)


def locate_quote(quote: str, text: str) -> Span | None:
    start = text.find(quote) if quote.strip() else -1
    if start == -1:
        return None
    return Span(start, start + len(quote))
