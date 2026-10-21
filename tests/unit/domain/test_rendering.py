import pytest

from soundline.domain.answers import (
    Answer,
    AnswerStatus,
    Citation,
    Claim,
    answer_to_dict,
    history_text,
    render,
)
from soundline.domain.quotes import Span
from soundline.domain.usage import StageUsage, TokenUsage, Usage

RENT = Citation(source="lease.md", quote="Rent is due on the 5th", span=Span(0, 22))
PETS = Citation(source="lease.md", quote="Pets are allowed", span=Span(24, 40))


def test_a_citation_marker_goes_before_the_closing_punctuation():
    text, citations = render([Claim("Rent is due on the 5th.", (RENT,))])

    assert text == "Rent is due on the 5th [1]."
    assert citations == [RENT]


def test_citations_are_numbered_by_first_appearance_and_reused():
    claims = [
        Claim("Rent is due on the 5th.", (RENT,)),
        Claim("Pets are allowed.", (PETS,)),
        Claim("Late rent is still rent!", (RENT, PETS)),
    ]

    text, citations = render(claims)

    assert text == (
        "Rent is due on the 5th [1]. Pets are allowed [2]. Late rent is still rent [1][2]!"
    )
    assert citations == [RENT, PETS]


def test_a_claim_without_closing_punctuation_ends_with_its_marker():
    text, _ = render([Claim("Rent is due on the 5th", (RENT,))])

    assert text == "Rent is due on the 5th [1]"


@pytest.mark.spec("GEN-014")
def test_the_json_form_of_an_answer_carries_its_prompt_version():
    answer = Answer(AnswerStatus.ABSTAINED, prompt_version="grounded-v4")

    assert answer_to_dict(answer)["prompt_version"] == "grounded-v4"


@pytest.mark.spec("GEN-070")
def test_the_json_form_of_an_answer_carries_its_usage():
    usage = Usage((StageUsage("generation", "ollama:m", TokenUsage(input=7, output=2), 0.0),))

    data = answer_to_dict(Answer(AnswerStatus.ANSWERED, usage=usage))

    assert data["usage"] == {
        "stages": [
            {
                "stage": "generation",
                "model": "ollama:m",
                "tokens": {"input": 7, "output": 2, "cache_read": 0, "cache_write": 0},
                "cost_usd": 0.0,
                "latency_ms": 0.0,
                "cached": False,
            }
        ],
        "tokens": {"input": 7, "output": 2, "cache_read": 0, "cache_write": 0},
        "cost_usd": 0.0,
    }


@pytest.mark.spec("GEN-063")
def test_a_previous_answer_becomes_history_text_without_its_citation_markers():
    answered = Answer(AnswerStatus.ANSWERED, text="Rent is due on the 5th [1]. Pets [2] are ok.")
    abstained = Answer(AnswerStatus.ABSTAINED, abstention_message="nothing about parking")

    assert history_text(answered) == "Rent is due on the 5th. Pets are ok."
    assert history_text(abstained) == "(no answer: nothing about parking)"


@pytest.mark.spec("EVL-020")
def test_the_json_form_lists_claims_with_their_citations_and_the_proposed_count():
    answer = Answer(
        AnswerStatus.ANSWERED,
        claims=(Claim("Rent is due on the 5th.", (RENT,)),),
        citations_proposed=2,
    )

    data = answer_to_dict(answer)

    assert data["claims"] == [
        {
            "text": "Rent is due on the 5th.",
            "conditions": [],
            "citations": [
                {
                    "source": "lease.md",
                    "quote": "Rent is due on the 5th",
                    "span": [0, 22],
                    "section_path": [],
                    "approximate": False,
                    "verified": True,
                }
            ],
        }
    ]
    assert data["citations_proposed"] == 2


@pytest.mark.spec("GEN-080")
def test_a_claim_shown_without_citation_renders_without_a_marker():
    text, citations = render([Claim("Pets are allowed.", ()), Claim("Rent is due.", (RENT,))])

    assert text == "Pets are allowed. Rent is due [1]."
    assert citations == [RENT]
