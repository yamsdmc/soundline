import json

import pytest

from soundline.application.ask import ask
from soundline.application.judges import FaithfulnessJudge
from soundline.domain.answers import Citation, Claim, answer_to_dict, render
from soundline.domain.chunks import Chunk
from soundline.domain.conditions import missing_conditions
from soundline.domain.quotes import Span
from soundline.testing import InMemoryIndex, ScriptedLanguageModel

SHEET = "preavis.html"
EMPTY = ("Préavis", "Logement vide", "Vous vivez seul")
FURNISHED = ("Préavis", "Logement meublé")


def chunk(path: tuple[str, ...], source: str = SHEET) -> Chunk:
    return Chunk(source=source, text="…", span=Span(0, 1), section_path=path)


def cited(path: tuple[str, ...], source: str = SHEET) -> Citation:
    return Citation(source, "Le délai de préavis est de 3 mois", Span(0, 33), section_path=path)


EVIDENCE = [chunk(EMPTY), chunk(FURNISHED)]


@pytest.mark.spec("GEN-094", "GEN-095")
def test_a_section_with_a_sibling_in_the_evidence_is_a_condition_the_claim_must_name():
    claim = Claim("Le préavis est de 3 mois.", (cited(EMPTY),))

    assert missing_conditions(claim, EVIDENCE) == ("Logement vide",)


@pytest.mark.spec("GEN-095")
@pytest.mark.parametrize(
    "text", ["Pour un logement VIDE, le préavis est de 3 mois.", "En location vide : 3 mois."]
)
def test_a_claim_naming_a_distinguishing_word_keeps_no_condition(text: str):
    assert missing_conditions(Claim(text, (cited(EMPTY),)), EVIDENCE) == ()


@pytest.mark.spec("GEN-094")
def test_without_a_sibling_in_the_evidence_a_section_is_no_condition():
    claim = Claim("Le préavis est de 3 mois.", (cited(EMPTY),))

    assert missing_conditions(claim, [chunk(EMPTY)]) == ()
    assert missing_conditions(claim, [chunk(EMPTY), chunk(FURNISHED, "autre.html")]) == ()


@pytest.mark.spec("GEN-094")
def test_a_claim_cited_under_both_siblings_states_a_shared_rule():
    claim = Claim("Le préavis est de 3 mois.", (cited(EMPTY), cited(FURNISHED)))

    assert missing_conditions(claim, EVIDENCE) == ()


@pytest.mark.spec("GEN-094")
def test_nested_conditions_are_each_checked():
    alone, couple = EMPTY, ("Préavis", "Logement vide", "Vous vivez en couple")
    evidence = [chunk(alone), chunk(couple), chunk(FURNISHED)]
    claim = Claim("Pour un logement vide, le préavis est de 3 mois.", (cited(alone),))

    assert missing_conditions(claim, evidence) == ("Vous vivez seul",)


@pytest.mark.spec("GEN-095")
def test_conditions_are_rendered_after_the_claim_text_and_before_its_markers():
    claim = Claim("Le préavis est de 3 mois.", (cited(EMPTY),), conditions=("Logement vide",))

    text, _ = render([claim])

    assert text == "Le préavis est de 3 mois (Logement vide) [1]."
    assert claim.shown_text == "Le préavis est de 3 mois (Logement vide)."


@pytest.mark.spec("GEN-095")
def test_an_answer_shows_the_conditions_its_claims_leave_out():
    empty_text, furnished_text = "Le délai de préavis est de 3 mois.", "Le préavis est de 1 mois."
    index = InMemoryIndex()
    index.add(Chunk(SHEET, empty_text, Span(0, 34), section_path=EMPTY))
    index.add(Chunk(SHEET, furnished_text, Span(35, 60), section_path=FURNISHED))
    llm = ScriptedLanguageModel(
        {
            "claims": [
                {
                    "text": "Le préavis est de 3 mois.",
                    "citations": [
                        {"evidence_id": "E1", "quote": "Le délai de préavis est de 3 mois"}
                    ],
                }
            ],
            "insufficient_evidence": None,
            "conflicts": [],
        }
    )

    answer = ask("délai de préavis 3 mois", index, llm)

    assert answer.text == "Le préavis est de 3 mois (Logement vide) [1]."
    assert answer.claims[0].conditions == ("Logement vide",)
    assert '"conditions": ["Logement vide"]' in json.dumps(
        answer_to_dict(answer), ensure_ascii=False
    )


@pytest.mark.spec("GEN-096", "EVL-041")
def test_the_judge_reads_the_claim_with_its_conditions():
    llm = ScriptedLanguageModel({"rationale": "ok", "entailed": True})
    claim = Claim("Le préavis est de 3 mois.", (cited(EMPTY),), conditions=("Logement vide",))

    FaithfulnessJudge(llm).judge(claim)

    assert "Le préavis est de 3 mois (Logement vide)." in llm.requests[0].prompt
