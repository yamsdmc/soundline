from pathlib import Path

import pytest

from soundline import (
    AbstentionReason,
    AnswerStatus,
    GenerationSettings,
    PromptTemplate,
    Soundline,
)
from soundline.domain.events import RetrievalCompleted
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


@pytest.mark.spec("GEN-014")
def test_a_custom_prompt_template_is_used_and_its_version_recorded(tmp_path: Path):
    prompt = tmp_path / "house-v1"
    prompt.mkdir()
    (prompt / "system.txt").write_text("House rules.")
    (prompt / "user.txt").write_text("$history$evidence\n$question\n$language_instruction")
    llm = ScriptedLanguageModel({"claims": [], "insufficient_evidence": "unclear"})
    generation = GenerationSettings(prompt=PromptTemplate.from_directory(prompt))
    soundline = Soundline.in_memory(llm=llm, generation=generation)
    soundline.ingest_text("lease.md", "Rent is due on the 5th.")

    answer = soundline.ask("When is rent due?")

    assert llm.requests[0].system == "House rules."
    assert answer.prompt_version == "house-v1"


@pytest.mark.spec("GEN-061", "RET-071", "GEN-063")
def test_a_conversation_carries_previous_turns_as_text_into_follow_ups():
    llm = ScriptedLanguageModel(
        answer_citing("Rent is due on the 5th.", "Rent is due on the 5th"),
        {"query": "late fees for rent"},
        answer_citing("Late fees are 10 euros per day.", "Late fees are 10 euros per day"),
    )
    soundline = Soundline.in_memory(llm=llm)
    soundline.ingest_text("lease.md", "Rent is due on the 5th. Late fees are 10 euros per day.")
    chat = soundline.conversation()

    chat.ask("When is rent due?")
    follow_up = chat.ask("And late fees?")

    assert follow_up.query is not None
    assert follow_up.query.search_query == "late fees for rent"
    assert "Assistant: Rent is due on the 5th." in llm.requests[1].prompt  # no [1] marker
    assert [turn.question for turn in chat.turns] == ["When is rent due?", "And late fees?"]


@pytest.mark.spec("GEN-050", "GEN-061")
def test_a_conversation_streams_its_answers_and_remembers_them():
    llm = ScriptedLanguageModel(
        answer_citing("Rent is due on the 5th.", "Rent is due on the 5th"),
        {"query": "late fees for rent"},
        answer_citing("Late fees are 10 euros per day.", "Late fees are 10 euros per day"),
    )
    soundline = Soundline.in_memory(llm=llm)
    soundline.ingest_text("lease.md", "Rent is due on the 5th. Late fees are 10 euros per day.")
    chat = soundline.conversation()

    first = list(chat.ask_stream("When is rent due?"))
    second = list(chat.ask_stream("And late fees?"))

    assert [type(event).__name__ for event in first] == [
        "RetrievalCompleted",
        "ClaimVerified",
        "AnswerCompleted",
    ]
    assert isinstance(second[0], RetrievalCompleted)
    assert second[0].search_query == "late fees for rent"
    assert [turn.question for turn in chat.turns] == ["When is rent due?", "And late fees?"]


@pytest.mark.spec("CLI-007")
def test_an_answer_renders_as_a_self_contained_citation_viewer():
    llm = ScriptedLanguageModel(answer_citing("Rent is due on the 5th.", "Rent is due on the 5th"))
    soundline = Soundline.in_memory(llm=llm)
    soundline.ingest_text("lease.md", "Rent is due on the 5th. Pets are allowed.")

    html = soundline.viewer_html(soundline.ask("When is rent due?"))

    assert html.startswith("<!doctype html>")
    assert "<h1>When is rent due?</h1>" in html
    assert "<mark>Rent is due on the 5th</mark>" in html
