import pytest

from soundline import AbstentionReason, AnswerStatus, Soundline
from soundline.testing import ScriptedLanguageModel


def answer_citing(claim: str, quote: str) -> dict[str, object]:
    return {"claims": [{"text": claim, "citations": [{"evidence_id": "E1", "quote": quote}]}]}


@pytest.mark.spec("GEN-030", "GEN-040")
def test_a_question_about_an_ingested_text_gets_an_answer_citing_it():
    llm = ScriptedLanguageModel(answer_citing("Rent is due on the 5th.", "Rent is due on the 5th"))
    soundline = Soundline.in_memory(llm=llm)
    soundline.ingest_text("notes.txt", "Rent is due on the 5th. Pets are allowed.")

    answer = soundline.ask("When is rent due?")

    assert answer.status is AnswerStatus.ANSWERED
    assert answer.text == "Rent is due on the 5th [1]."
    assert [(c.source, c.quote) for c in answer.citations] == [
        ("notes.txt", "Rent is due on the 5th")
    ]


@pytest.mark.spec("GEN-001")
def test_asking_an_empty_corpus_abstains_without_calling_the_model():
    llm = ScriptedLanguageModel()
    soundline = Soundline.in_memory(llm=llm)

    answer = soundline.ask("When is rent due?")

    assert answer.status is AnswerStatus.ABSTAINED
    assert answer.abstention_reason is AbstentionReason.NO_EVIDENCE
    assert llm.requests == []
