import pytest

from soundline.application.ask import GenerationSettings, ask
from soundline.domain.answers import Answer, AnswerStatus
from soundline.domain.chunks import Chunk
from soundline.domain.quotes import Span
from soundline.testing import InMemoryIndex, ScriptedLanguageModel

OFFICIAL = "The penalty is 10 % of the rent per month of delay."
BLOG = "The penalty is 50 % of the rent per month of delay."
OFFICIAL_CASE = "Without a forwarding address, the penalty is not due."


def index(*documents: tuple[str, str]) -> InMemoryIndex:
    built = InMemoryIndex()
    for source, text in documents:
        built.add(Chunk(source=source, text=text, span=Span(0, len(text))))
    return built


def output(conflicts: object, *claims: tuple[str, str, str]) -> dict[str, object]:
    return {
        "claims": [
            {"text": text, "citations": [{"evidence_id": evidence_id, "quote": quote}]}
            for text, evidence_id, quote in claims
        ],
        "insufficient_evidence": None,
        "conflicts": conflicts,
    }


PENALTIES = (
    ("The official sheet says 10 %.", "E1", "The penalty is 10 % of the rent"),
    ("A blog says 50 %.", "E2", "The penalty is 50 % of the rent"),
)


def ask_penalty(conflicts: object, *claims: tuple[str, str, str], verify: bool = True) -> Answer:
    llm = ScriptedLanguageModel(output(conflicts, *claims))
    documents = index(("official.html", OFFICIAL), ("blog.html", BLOG))
    return ask("What is the penalty?", documents, llm, GenerationSettings(verify=verify))


@pytest.mark.spec("GEN-090", "GEN-091")
def test_a_conflict_between_two_cited_documents_is_kept_with_their_citations():
    answer = ask_penalty([{"about": "the penalty", "evidence_ids": ["E1", "E2"]}], *PENALTIES)

    assert answer.status is AnswerStatus.ANSWERED
    [conflict] = answer.conflicts
    assert conflict.about == "the penalty"
    assert [c.source for c in conflict.citations] == ["official.html", "blog.html"]


@pytest.mark.spec("GEN-091")
@pytest.mark.parametrize(
    "evidence_ids",
    [["E1", "E9"], ["E1"], ["E1", "E1"]],
    ids=["unknown-id", "one-item", "same-item-twice"],
)
def test_a_conflict_without_two_cited_documents_is_dropped(evidence_ids: list[str]):
    answer = ask_penalty([{"about": "the penalty", "evidence_ids": evidence_ids}], *PENALTIES)

    assert answer.conflicts == ()


@pytest.mark.spec("GEN-091")
def test_a_conflict_with_an_uncited_item_is_dropped():
    answer = ask_penalty([{"about": "the penalty", "evidence_ids": ["E1", "E2"]}], PENALTIES[0])

    assert answer.conflicts == ()


@pytest.mark.spec("GEN-091")
def test_passages_of_one_document_are_not_a_conflict():
    llm = ScriptedLanguageModel(
        output(
            [{"about": "the penalty", "evidence_ids": ["E1", "E2"]}],
            ("It is 10 %.", "E1", "The penalty is 10 % of the rent"),
            ("Not without an address.", "E2", "Without a forwarding address"),
        )
    )
    documents = InMemoryIndex()
    documents.add(Chunk("official.html", OFFICIAL, Span(0, len(OFFICIAL))))
    end = len(OFFICIAL) + 1 + len(OFFICIAL_CASE)
    documents.add(Chunk("official.html", OFFICIAL_CASE, Span(len(OFFICIAL) + 1, end)))

    answer = ask("penalty rent", documents, llm)  # E1 official, E2 its case

    assert len(answer.claims) == 2
    assert answer.conflicts == ()


@pytest.mark.spec("GEN-093")
@pytest.mark.parametrize("conflicts", [None, "yes", [{"about": 3}], [{"evidence_ids": "E1"}]])
def test_a_missing_or_malformed_conflicts_field_reads_as_no_conflict(conflicts: object):
    answer = ask_penalty(conflicts, *PENALTIES)

    assert answer.status is AnswerStatus.ANSWERED
    assert answer.conflicts == ()


@pytest.mark.spec("GEN-091", "GEN-080")
def test_without_verification_conflicts_are_kept_on_the_citations_shown():
    answer = ask_penalty(
        [{"about": "the penalty", "evidence_ids": ["E1", "E2"]}],
        ("The official sheet says 10 %.", "E1", "a quote the model made up"),
        PENALTIES[1],
        verify=False,
    )

    assert len(answer.conflicts) == 1
