import pytest

from soundline.application.ask import ask
from soundline.domain.chunks import Chunk
from soundline.domain.quotes import Span
from soundline.testing import InMemoryIndex, ScriptedLanguageModel

LEASE = "Rent is due on the 5th. Pets are allowed."


def index_with_lease() -> InMemoryIndex:
    index = InMemoryIndex()
    index.add(Chunk(source="lease.md", text=LEASE, span=Span(0, len(LEASE))))
    return index


def citing(evidence_id: str, quote: str) -> dict[str, object]:
    return {
        "claims": [
            {
                "text": "Rent is due on the 5th.",
                "citations": [{"evidence_id": evidence_id, "quote": quote}],
            }
        ]
    }


@pytest.mark.spec("GEN-030", "GEN-031")
def test_a_verified_citation_is_resolved_to_its_span_in_the_document():
    llm = ScriptedLanguageModel(citing("E1", "Pets are allowed"))

    answer = ask("Are pets allowed?", index_with_lease(), llm)

    assert [(c.quote, c.span) for c in answer.citations] == [("Pets are allowed", Span(24, 40))]


@pytest.mark.spec("GEN-030", "GEN-032")
def test_a_citation_whose_quote_is_not_in_the_evidence_is_removed():
    llm = ScriptedLanguageModel(citing("E1", "Parking is free"))

    answer = ask("When is rent due?", index_with_lease(), llm)

    assert answer.citations == []


@pytest.mark.spec("GEN-030")
def test_a_citation_to_an_unknown_evidence_id_is_removed():
    llm = ScriptedLanguageModel(citing("E9", "Rent is due on the 5th"))

    answer = ask("When is rent due?", index_with_lease(), llm)

    assert answer.citations == []


def test_the_model_sees_the_question_and_each_evidence_labeled_with_its_id_and_source():
    llm = ScriptedLanguageModel(citing("E1", "Rent is due on the 5th"))

    ask("When is rent due?", index_with_lease(), llm)

    prompt = llm.requests[0].prompt
    assert "When is rent due?" in prompt
    assert 'id="E1"' in prompt
    assert 'source="lease.md"' in prompt
    assert LEASE in prompt
