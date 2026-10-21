from collections.abc import Callable

import pytest

from soundline.application.ask import GenerationSettings, ask
from soundline.domain.answers import AbstentionReason, AnswerStatus
from soundline.domain.chunks import Chunk
from soundline.domain.conversation import Turn
from soundline.domain.quotes import Span
from soundline.testing import InMemoryIndex, ScriptedLanguageModel

LEASE = "Late fees are 10 euros per day. Rent is due on the 5th."
HISTORY = [Turn("When is rent due?", "Rent is due on the 5th. Parking costs 50 euros.")]


class SpyRetriever:
    def __init__(self) -> None:
        self.index = InMemoryIndex()
        self.index.add(Chunk(source="lease.md", text=LEASE, span=Span(0, len(LEASE))))
        self.queries: list[str] = []

    def search(self, text: str, limit: int) -> list[Chunk]:
        self.queries.append(text)
        return self.index.search(text, limit)


def citing(quote: str) -> dict[str, object]:
    return {
        "claims": [{"text": quote + ".", "citations": [{"evidence_id": "E1", "quote": quote}]}],
        "insufficient_evidence": None,
    }


@pytest.mark.spec("RET-071", "GEN-060")
def test_a_follow_up_is_condensed_into_a_standalone_query_for_retrieval():
    retriever = SpyRetriever()
    llm = ScriptedLanguageModel(
        {"query": "What are the late fees for rent in the lease?"},
        citing("Late fees are 10 euros per day"),
    )

    answer = ask("And late fees?", retriever, llm, history=HISTORY)

    assert retriever.queries == ["What are the late fees for rent in the lease?"]
    assert answer.query is not None
    assert answer.query.search_query == "What are the late fees for rent in the lease?"
    assert answer.status is AnswerStatus.ANSWERED
    assert "When is rent due?" in llm.requests[0].prompt
    assert llm.requests[0].output.name == "standalone_query"


@pytest.mark.spec("RET-070")
def test_without_history_the_question_is_searched_as_is_and_nothing_is_rewritten():
    retriever = SpyRetriever()
    llm = ScriptedLanguageModel(citing("Rent is due on the 5th"))

    answer = ask("When is rent due?", retriever, llm)

    assert retriever.queries == ["When is rent due?"]
    assert len(llm.requests) == 1
    assert answer.query is not None
    assert answer.query.search_query == "When is rent due?"


@pytest.mark.spec("RET-073")
@pytest.mark.parametrize("output", ["no json here", {"query": "  "}, {"other": "x"}])
def test_a_failed_condensation_falls_back_to_the_question_with_a_warning(output: object):
    retriever = SpyRetriever()
    llm = ScriptedLanguageModel(output, citing("Late fees are 10 euros per day"))  # type: ignore[arg-type]

    answer = ask("late fees?", retriever, llm, history=HISTORY)

    assert retriever.queries == ["late fees?"]
    assert any("condens" in warning for warning in answer.warnings)
    assert answer.status is AnswerStatus.ANSWERED


@pytest.mark.spec("GEN-070")
def test_condensation_is_a_rewrite_stage_in_the_usage():
    llm = ScriptedLanguageModel({"query": "late fees"}, citing("Late fees are 10 euros per day"))

    answer = ask("And late fees?", SpyRetriever(), llm, history=HISTORY)

    assert [stage.stage for stage in answer.usage.stages] == ["rewrite", "generation"]


@pytest.mark.spec("GEN-060", "GEN-063")
def test_a_previous_answer_is_context_but_never_citable_evidence():
    llm = ScriptedLanguageModel(
        {"query": "parking price late fees"},
        citing("Parking costs 50 euros"),  # said in the history, absent from the evidence
    )

    answer = ask("How much is parking?", SpyRetriever(), llm, history=HISTORY)

    prompt = llm.requests[1].prompt
    assert "Parking costs 50 euros" in prompt  # the model sees the history...
    assert "not evidence" in prompt
    assert answer.status is AnswerStatus.ABSTAINED  # ...but cannot cite it
    assert answer.abstention_reason is AbstentionReason.UNSUPPORTED_CLAIMS


@pytest.mark.spec("GEN-062")
def test_history_beyond_its_budget_is_dropped_whole_and_reported():
    history = [Turn(f"question {n}", "answer " * 50) for n in range(5)]
    llm = ScriptedLanguageModel({"query": "late fees"}, citing("Late fees are 10 euros per day"))

    answer = ask(
        "And late fees?",
        SpyRetriever(),
        llm,
        GenerationSettings(history_budget_tokens=200),
        history,
    )

    assert answer.query is not None
    assert (answer.query.history_turns, answer.query.history_dropped) == (1, 4)
    assert "question 4" in llm.requests[1].prompt
    assert "question 3" not in llm.requests[1].prompt


@pytest.mark.spec("GEN-060", "GEN-014")
def test_the_prompt_with_history_is_approved(approve: Callable[[str], None]):
    llm = ScriptedLanguageModel({"query": "late fees"}, citing("Late fees are 10 euros per day"))

    ask("And late fees?", SpyRetriever(), llm, history=HISTORY)

    condense, generate = llm.requests
    approve(
        f"=== condense system ===\n{condense.system}\n=== condense prompt ===\n{condense.prompt}\n"
        f"=== system ===\n{generate.system}\n=== prompt ===\n{generate.prompt}\n"
    )
