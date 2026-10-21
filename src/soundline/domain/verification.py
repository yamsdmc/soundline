"""Quote verification: the matching ladder of GEN-030 to GEN-039.

exact → normalized (case, Unicode, whitespace, typography) → fuzzy (long quotes only, edit
similarity, and the critical tokens must agree). Whatever the rung, the displayed quote is
always the source text at the returned span (INV-GEN-1).
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

from soundline.domain.quotes import Span

_TYPOGRAPHY = str.maketrans(
    {
        "\u2019": "'",  # right single quotation mark (typographic apostrophe)
        "\u2018": "'",  # left single quotation mark
        "\u201c": '"',  # left double quotation mark
        "\u201d": '"',  # right double quotation mark
        "\u00ab": '"',  # left guillemet
        "\u00bb": '"',  # right guillemet
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2011": "-",  # non-breaking hyphen
    }
)
# Digit groups may be separated by a space, a no-break space or a narrow no-break space.
_NUMBER = re.compile("\\d+(?:[ \u00a0\u202f]\\d{3})*(?:[.,]\\d+)?(?:\\s?%)?")
_WORD = re.compile(r"\S+")


class Method(Enum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    FUZZY = "fuzzy"
    FAILED = "failed"


@dataclass(frozen=True)
class Verification:
    method: Method
    span: Span = field(default_factory=lambda: Span(0, 0))
    quote: str = ""
    """The source text at `span`: what users see, never the model's version."""
    reason: str | None = None
    similarity: float = 1.0

    @property
    def approximate(self) -> bool:
        return self.method is Method.FUZZY  # GEN-038


@dataclass(frozen=True)
class VerificationSettings:
    fuzzy_threshold: float = 0.9
    fuzzy_min_chars: int = 30


def verify_quote(
    quote: str, evidence: str, settings: VerificationSettings | None = None
) -> Verification:
    settings = settings or VerificationSettings()
    if not quote.strip():
        return Verification(Method.FAILED, reason="blank_quote")
    start = evidence.find(quote)
    if start != -1:
        return _found(Method.EXACT, evidence, Span(start, start + len(quote)))

    folded_evidence, origins = _fold(evidence)
    folded_quote, _ = _fold(quote)
    start = folded_evidence.find(folded_quote)
    if start != -1:
        end = origins[start + len(folded_quote) - 1] + 1
        return _found(Method.NORMALIZED, evidence, Span(origins[start], end))

    if len(quote.strip()) < settings.fuzzy_min_chars:
        return Verification(Method.FAILED, reason="not_found")
    window, similarity = _best_window(folded_quote, folded_evidence)
    if window is None or similarity < settings.fuzzy_threshold:
        return Verification(Method.FAILED, reason="not_found", similarity=similarity)
    span = Span(origins[window.start], origins[window.end - 1] + 1)
    if critical_tokens(quote) != critical_tokens(evidence[span.start : span.end]):
        return Verification(Method.FAILED, reason="critical_token_mismatch", similarity=similarity)
    return _found(Method.FUZZY, evidence, span, similarity)


def critical_tokens(text: str) -> Counter[str]:
    """Numbers, amounts, percentages, and the digits of dates and identifiers (GEN-037),
    canonicalized: '5,5 %' and '5.5%' agree, '1 250' and '1250' agree."""
    canonical = (re.sub(r"\s", "", match).replace(",", ".") for match in _NUMBER.findall(text))
    return Counter(canonical)


def _found(method: Method, evidence: str, span: Span, similarity: float = 1.0) -> Verification:
    return Verification(method, span, evidence[span.start : span.end], similarity=similarity)


def _fold(text: str) -> tuple[str, list[int]]:
    """Case-folded, NFKC, typographic quotes and dashes unified, whitespace collapsed; each
    character keeps the offset it came from."""
    chars: list[str] = []
    origins: list[int] = []
    for offset, char in enumerate(text):
        if char.isspace():
            if chars and chars[-1] != " ":
                chars.append(" ")
                origins.append(offset)
            continue
        for folded in unicodedata.normalize("NFKC", char).translate(_TYPOGRAPHY).casefold():
            chars.append(folded)
            origins.append(offset)
    while chars and chars[-1] == " ":
        chars.pop()
        origins.pop()
    return "".join(chars), origins


def _best_window(quote: str, text: str) -> tuple[Span | None, float]:
    """Word-aligned windows of about the quote's length: a cheap trigram Jaccard prefilter
    keeps the most promising ones, edit similarity decides."""
    words = [Span(m.start(), m.end()) for m in _WORD.finditer(text)]
    length = len(_WORD.findall(quote))
    windows = [
        Span(words[i].start, words[i + n - 1].end)
        for n in range(max(1, length - 2), length + 3)
        for i in range(len(words) - n + 1)
    ]
    grams = _trigrams(quote)
    shortlist = sorted(windows, key=lambda w: -_jaccard(grams, _trigrams(text[w.start : w.end])))[
        :8
    ]
    scored = [(w, _similarity(quote, text[w.start : w.end])) for w in shortlist]
    return max(scored, key=lambda pair: pair[1], default=(None, 0.0))


def _trigrams(text: str) -> set[str]:
    return {text[i : i + 3] for i in range(max(1, len(text) - 2))}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 0.0


def _similarity(a: str, b: str) -> float:
    """1 - Levenshtein distance / length of the longer string."""
    if not a or not b:
        return 0.0
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b))
            )
        previous = current
    return 1 - previous[-1] / max(len(a), len(b))
