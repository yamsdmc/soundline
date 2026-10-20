from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

from soundline.domain.quotes import Span


class AnswerStatus(Enum):
    ANSWERED = "answered"
    ABSTAINED = "abstained"


class AbstentionReason(Enum):
    NO_EVIDENCE = "no_evidence"


_CLOSING_PUNCTUATION = ".!?…"


@dataclass(frozen=True)
class Citation:
    """A verified quote: it exists verbatim in `source` at `span`."""

    source: str
    quote: str
    span: Span


@dataclass(frozen=True)
class Claim:
    text: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class Answer:
    status: AnswerStatus
    text: str = ""
    citations: list[Citation] = field(default_factory=list[Citation])
    abstention_reason: AbstentionReason | None = None


def render(claims: Sequence[Claim]) -> tuple[str, list[Citation]]:
    """Renders claims as text with [n] markers numbered by first appearance (GEN-040)."""
    numbered: list[Citation] = []
    sentences: list[str] = []
    for claim in claims:
        for citation in claim.citations:
            if citation not in numbered:
                numbered.append(citation)
        markers = "".join(f"[{numbered.index(c) + 1}]" for c in claim.citations)
        body = claim.text.rstrip(_CLOSING_PUNCTUATION)
        closing = claim.text[len(body) :]
        sentences.append(f"{body} {markers}{closing}")
    return " ".join(sentences), numbered
