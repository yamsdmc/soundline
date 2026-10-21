from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum

from soundline.domain.quotes import Span
from soundline.domain.usage import Usage


class AnswerStatus(Enum):
    ANSWERED = "answered"
    PARTIAL = "partial"
    """Some claims could not be supported and were removed (GEN-034)."""
    ABSTAINED = "abstained"


class AbstentionReason(Enum):
    NO_EVIDENCE = "no_evidence"
    MODEL_INSUFFICIENT_EVIDENCE = "model_insufficient_evidence"
    UNSUPPORTED_CLAIMS = "unsupported_claims"


_CLOSING_PUNCTUATION = ".!?…"


@dataclass(frozen=True)
class Citation:
    """A verified quote: it exists verbatim in `source` at `span`."""

    source: str
    quote: str
    span: Span
    approximate: bool = False
    """Verified by fuzzy matching; the quote shown is still the source text (GEN-038)."""
    section_path: tuple[str, ...] = ()
    """Where the quote sits in its document (GEN-031)."""


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
    abstention_message: str | None = None
    dropped_claims: list[str] = field(default_factory=list[str])
    """Claims removed because none of their citations could be verified (GEN-033)."""
    lenient_parse: bool = False
    """The model's output needed the lenient parser (GEN-023)."""
    prompt_version: str | None = None
    """The prompt template the model saw; None when the model was not called (GEN-014)."""
    usage: Usage = field(default_factory=Usage)
    """Tokens and estimated cost per stage (GEN-070)."""


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


def answer_to_dict(answer: Answer) -> dict[str, object]:
    return {
        "status": answer.status.value,
        "text": answer.text,
        "citations": [
            {
                "source": c.source,
                "quote": c.quote,
                "span": [c.span.start, c.span.end],
                "section_path": list(c.section_path),
                "approximate": c.approximate,
            }
            for c in answer.citations
        ],
        "dropped_claims": answer.dropped_claims,
        "abstention_reason": answer.abstention_reason.value if answer.abstention_reason else None,
        "abstention_message": answer.abstention_message,
        "prompt_version": answer.prompt_version,
        "usage": {
            "stages": [
                {
                    "stage": stage.stage,
                    "model": stage.model,
                    "tokens": asdict(stage.tokens),
                    "cost_usd": stage.cost_usd,
                }
                for stage in answer.usage.stages
            ],
            "tokens": asdict(answer.usage.tokens),
            "cost_usd": answer.usage.cost_usd,
        },
    }
