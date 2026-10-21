import pytest

from soundline.application.ask import ask_stream
from soundline.domain.answers import AnswerStatus
from soundline.domain.chunks import Chunk
from soundline.domain.errors import GenerationError
from soundline.domain.events import AnswerCompleted, ClaimVerified, RetrievalCompleted, StreamError
from soundline.domain.quotes import Span
from soundline.testing import InMemoryIndex, ScriptedLanguageModel

LEASE = "Rent is due on the 5th. Pets are allowed."


def index_with_lease() -> InMemoryIndex:
    index = InMemoryIndex()
    index.add(Chunk(source="lease.md", text=LEASE, span=Span(0, len(LEASE))))
    return index


def claim(text: str, quote: str) -> dict[str, object]:
    return {"text": text, "citations": [{"evidence_id": "E1", "quote": quote}]}


@pytest.mark.spec("GEN-050", "GEN-051")
def test_events_come_in_order_and_only_verified_claims_are_streamed():
    llm = ScriptedLanguageModel(
        {
            "claims": [
                claim("Rent is due on the 5th.", "Rent is due on the 5th"),
                claim("Parking is free.", "Parking is free"),  # not in the evidence
                claim("Pets are allowed.", "Pets are allowed"),
            ],
            "insufficient_evidence": None,
        }
    )

    events = list(ask_stream("rent pets", index_with_lease(), llm))

    assert [type(event) for event in events] == [
        RetrievalCompleted,
        ClaimVerified,
        ClaimVerified,
        AnswerCompleted,
    ]
    retrieval, first, second, completed = events
    assert isinstance(retrieval, RetrievalCompleted)
    assert [chunk.source for chunk in retrieval.evidence] == ["lease.md"]
    assert isinstance(first, ClaimVerified)
    assert isinstance(second, ClaimVerified)
    assert [first.claim.text, second.claim.text] == ["Rent is due on the 5th.", "Pets are allowed."]
    assert all(c.citations for c in (first.claim, second.claim))
    assert isinstance(completed, AnswerCompleted)
    assert completed.answer.status is AnswerStatus.PARTIAL


@pytest.mark.spec("GEN-050", "GEN-001")
def test_without_evidence_the_stream_completes_with_an_abstention():
    events = list(ask_stream("anything", InMemoryIndex(), ScriptedLanguageModel()))

    assert [type(event) for event in events] == [RetrievalCompleted, AnswerCompleted]


@pytest.mark.spec("GEN-050")
def test_a_failure_ends_the_stream_with_an_error_event():
    llm = ScriptedLanguageModel("not json", "still not json")

    events = list(ask_stream("When is rent due?", index_with_lease(), llm))

    assert [type(event) for event in events] == [RetrievalCompleted, StreamError]
    error = events[-1]
    assert isinstance(error, StreamError)
    assert isinstance(error.error, GenerationError)
