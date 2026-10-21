import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum

from soundline.domain.chunks import Chunk
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
    verified: bool = True
    """False only with verification disabled, for benchmarking (GEN-080): the quote is the
    model's and the span is the whole evidence item."""


@dataclass(frozen=True)
class Claim:
    text: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class Conflict:
    """Documents that disagree on what the question asks (GEN-090)."""

    about: str
    citations: tuple[Citation, ...]
    """The shown citations of the disagreeing evidence, from at least two documents."""


def conflict_among(
    about: str, evidence: Sequence[Chunk], claims: Sequence[Claim]
) -> Conflict | None:
    """The conflict the model reported between `evidence` items, if the shown claims cite them
    from at least two documents (GEN-091)."""
    cited: list[Citation] = []
    for claim in claims:
        for citation in claim.citations:
            if citation not in cited and any(_within(citation, item) for item in evidence):
                cited.append(citation)
    if len({citation.source for citation in cited}) < 2:
        return None
    return Conflict(about, tuple(cited))


def _within(citation: Citation, item: Chunk) -> bool:
    return (
        citation.source == item.source
        and item.span.start <= citation.span.start
        and citation.span.end <= item.span.end
    )


@dataclass(frozen=True)
class QueryInfo:
    question: str
    search_query: str
    """What the retrievers saw: the question, or a follow-up condensed (RET-071)."""
    history_turns: int = 0
    history_dropped: int = 0
    """Older turns left out of the prompt to fit its budget (GEN-062)."""


@dataclass(frozen=True)
class Answer:
    status: AnswerStatus
    text: str = ""
    citations: list[Citation] = field(default_factory=list[Citation])
    abstention_reason: AbstentionReason | None = None
    abstention_message: str | None = None
    dropped_claims: list[str] = field(default_factory=list[str])
    """Claims removed because none of their citations could be verified (GEN-033)."""
    claims: tuple[Claim, ...] = ()
    """The supported claims, each with its verified citations only."""
    citations_proposed: int = 0
    """Citations the model wrote, before verification (`citation_validity`, EVL-020)."""
    lenient_parse: bool = False
    """The model's output needed the lenient parser (GEN-023)."""
    prompt_version: str | None = None
    """The prompt template the model saw; None when the model was not called (GEN-014)."""
    usage: Usage = field(default_factory=Usage)
    """Tokens and estimated cost per stage (GEN-070)."""
    query: QueryInfo | None = None
    warnings: tuple[str, ...] = ()
    """Degradations that did not prevent an answer, e.g. a failed condensation (RET-073)."""
    conflicts: tuple[Conflict, ...] = ()
    """Documents that disagree, shown with the answer (GEN-090 to GEN-092)."""


def render(claims: Sequence[Claim]) -> tuple[str, list[Citation]]:
    """Renders claims as text with [n] markers numbered by first appearance (GEN-040)."""
    numbered: list[Citation] = []
    sentences: list[str] = []
    for claim in claims:
        for citation in claim.citations:
            if citation not in numbered:
                numbered.append(citation)
        markers = "".join(f"[{numbered.index(c) + 1}]" for c in claim.citations)
        if not markers:  # only with verification disabled (GEN-080)
            sentences.append(claim.text)
            continue
        body = claim.text.rstrip(_CLOSING_PUNCTUATION)
        closing = claim.text[len(body) :]
        sentences.append(f"{body} {markers}{closing}")
    return " ".join(sentences), numbered


_MARKER = re.compile(r" \[\d+\]")


def history_text(answer: Answer) -> str:
    """The answer as a previous turn: text without [n] markers, whose citations are not
    carried over (GEN-063)."""
    if answer.status is AnswerStatus.ABSTAINED:
        return f"(no answer: {answer.abstention_message or 'the documents do not say'})"
    return _MARKER.sub("", answer.text)


def answer_to_dict(answer: Answer) -> dict[str, object]:
    return {
        "status": answer.status.value,
        "text": answer.text,
        "citations": [_citation_to_dict(c) for c in answer.citations],
        "claims": [
            {"text": claim.text, "citations": [_citation_to_dict(c) for c in claim.citations]}
            for claim in answer.claims
        ],
        "citations_proposed": answer.citations_proposed,
        "dropped_claims": answer.dropped_claims,
        "conflicts": [
            {
                "about": conflict.about,
                "citations": [answer.citations.index(c) + 1 for c in conflict.citations],
            }
            for conflict in answer.conflicts
        ],
        "abstention_reason": answer.abstention_reason.value if answer.abstention_reason else None,
        "abstention_message": answer.abstention_message,
        "prompt_version": answer.prompt_version,
        "query": asdict(answer.query) if answer.query else None,
        "warnings": list(answer.warnings),
        "usage": {
            "stages": [
                {
                    "stage": stage.stage,
                    "model": stage.model,
                    "tokens": asdict(stage.tokens),
                    "cost_usd": stage.cost_usd,
                    "latency_ms": stage.latency_ms,
                    "cached": stage.cached,
                }
                for stage in answer.usage.stages
            ],
            "tokens": asdict(answer.usage.tokens),
            "cost_usd": answer.usage.cost_usd,
        },
    }


def _citation_to_dict(citation: Citation) -> dict[str, object]:
    return {
        "source": citation.source,
        "quote": citation.quote,
        "span": [citation.span.start, citation.span.end],
        "section_path": list(citation.section_path),
        "approximate": citation.approximate,
        "verified": citation.verified,
    }
