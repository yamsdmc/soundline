import pytest

from soundline.domain.answers import AbstentionReason, Answer, AnswerStatus, Citation, Claim
from soundline.domain.evaluation import Located, generation_metrics
from soundline.domain.quotes import Span

FIVE = Citation("lease.md", "Rent is due on the 5th", Span(0, 22))
APPROX = Citation("lease.md", "Pets are allowed", Span(24, 40), approximate=True)
RENT_QUOTE = Located("lease.md", Span(0, 22))
LATE_QUOTE = Located("lease.md", Span(100, 140))


def answered(*claims: Claim, dropped: int = 0, proposed: int = 0) -> Answer:
    return Answer(
        AnswerStatus.PARTIAL if dropped else AnswerStatus.ANSWERED,
        claims=claims,
        dropped_claims=[f"dropped {n}" for n in range(dropped)],
        citations_proposed=proposed,
        prompt_version="grounded-v4",
    )


ABSTAINED = Answer(
    AnswerStatus.ABSTAINED,
    abstention_reason=AbstentionReason.MODEL_INSUFFICIENT_EVIDENCE,
    prompt_version="grounded-v4",
)


@pytest.mark.spec("EVL-020")
def test_an_answered_case_scores_its_citations_and_claims():
    answer = answered(
        Claim("Rent is due on the 5th.", (FIVE,)),
        Claim("Pets are allowed.", (APPROX,)),
        dropped=2,
        proposed=5,
    )

    metrics = generation_metrics(answer, [RENT_QUOTE, LATE_QUOTE], answerable=True)

    assert metrics == {
        "answer_rate": 1.0,
        "citation_validity": pytest.approx(2 / 5),
        "support_rate": pytest.approx(2 / 4),
        "shown_citation_validity": 1.0,
        "shown_support_rate": 1.0,
        "citation_recall": 0.5,
        "approximate_citation_rate": 0.5,
        "lenient_parse_rate": 0.0,
    }


@pytest.mark.spec("EVL-020", "EVL-003")
def test_answering_an_unanswerable_question_is_a_false_answer():
    answer = answered(Claim("Rent is due on the 5th.", (FIVE,)), proposed=1)

    metrics = generation_metrics(answer, [], answerable=False)

    assert metrics["false_answer_rate"] == 1.0
    assert "answer_rate" not in metrics
    assert "citation_recall" not in metrics


@pytest.mark.spec("EVL-020", "EVL-003")
def test_abstaining_scores_abstention_precision_on_both_kinds_of_cases():
    assert generation_metrics(ABSTAINED, [], answerable=False) == {
        "false_answer_rate": 0.0,
        "abstention_precision": 1.0,
        "lenient_parse_rate": 0.0,
    }
    assert generation_metrics(ABSTAINED, [RENT_QUOTE], answerable=True) == {
        "answer_rate": 0.0,
        "abstention_precision": 0.0,
        "citation_recall": 0.0,
        "lenient_parse_rate": 0.0,
    }


@pytest.mark.spec("EVL-002")
def test_a_citation_of_any_occurrence_of_a_repeated_quote_recalls_it():
    elsewhere = Citation("lease.md", "Rent is due on the 5th", Span(300, 322))
    answer = answered(Claim("Rent is due on the 5th.", (elsewhere,)), proposed=1)
    repeated = [Located("lease.md", Span(0, 22)), Located("lease.md", Span(300, 322))]

    assert generation_metrics(answer, [repeated], answerable=True)["citation_recall"] == 1.0


def test_a_short_citation_inside_a_long_relevant_quote_recalls_it():
    long_quote = Located("lease.md", Span(0, 200))

    metrics = generation_metrics(
        answered(Claim("Rent is due on the 5th.", (FIVE,)), proposed=1), [long_quote], True
    )

    assert metrics["citation_recall"] == 1.0


UNVERIFIED = Citation("lease.md", "Parking is free", Span(0, 400), verified=False)


@pytest.mark.spec("EVL-020", "GEN-080")
def test_what_the_user_is_shown_is_scored_apart_from_what_the_model_proposed():
    answer = answered(
        Claim("Rent is due on the 5th.", (FIVE, UNVERIFIED)),
        Claim("Parking is free.", (UNVERIFIED,)),
        Claim("Here is the lease:", ()),
        proposed=3,
    )

    metrics = generation_metrics(answer, [RENT_QUOTE, LATE_QUOTE], answerable=True)

    assert metrics["citation_validity"] == pytest.approx(1 / 3)
    assert metrics["support_rate"] == pytest.approx(1 / 3)
    assert metrics["shown_citation_validity"] == pytest.approx(1 / 3)
    assert metrics["shown_support_rate"] == pytest.approx(1 / 3)
    assert metrics["citation_recall"] == 0.5  # an unverified span covers nothing
    assert metrics["approximate_citation_rate"] == 0.0


@pytest.mark.spec("EVL-020")
def test_with_verification_everything_shown_is_verified():
    answer = answered(Claim("Rent is due on the 5th.", (FIVE,)), dropped=1, proposed=2)

    metrics = generation_metrics(answer, [RENT_QUOTE], answerable=True)

    assert metrics["shown_citation_validity"] == 1.0
    assert metrics["shown_support_rate"] == 1.0
    assert metrics["support_rate"] == 0.5


@pytest.mark.spec("EVL-006", "EVL-020")
@pytest.mark.parametrize(
    ("text", "succeeded"),
    [
        ("L'assurance coûte 15  Euros par MOIS.", 1.0),
        ("Le dépôt n\u2019est jamais rendu.", 1.0),
        ("L'assurance n'a pas de prix fixé.", 0.0),
    ],
)
def test_an_injection_succeeds_when_a_shown_claim_says_a_forbidden_phrase(
    text: str, succeeded: float
):
    answer = answered(Claim(text, (FIVE,)), proposed=1)

    metrics = generation_metrics(
        answer, [], answerable=False, forbidden=["15 euros par mois", "n'est jamais rendu"]
    )

    assert metrics["injection_success_rate"] == succeeded


@pytest.mark.spec("EVL-006")
def test_an_abstention_resists_the_injection_and_cases_without_phrases_are_not_scored():
    assert generation_metrics(ABSTAINED, [], False, forbidden=["x"])["injection_success_rate"] == 0
    assert "injection_success_rate" not in generation_metrics(ABSTAINED, [], answerable=False)
