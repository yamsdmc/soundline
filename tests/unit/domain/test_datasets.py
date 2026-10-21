import json

import pytest

from soundline.domain.datasets import DatasetError, RelevantQuote, parse_dataset


def line(**case: object) -> str:
    base: dict[str, object] = {
        "id": "lease-1",
        "question": "When is rent due?",
        "answerable": True,
        "relevant": [{"source": "lease.md", "quote": "Rent is due on the 5th"}],
    }
    return json.dumps(base | case)


@pytest.mark.spec("EVL-001")
def test_a_valid_case_is_parsed():
    dataset = parse_dataset([line(tags=["fr"], reference_answer="On the 5th.")])

    case = dataset.cases[0]
    assert (case.id, case.question, case.answerable) == ("lease-1", "When is rent due?", True)
    assert case.relevant == (RelevantQuote("lease.md", "Rent is due on the 5th"),)
    assert case.tags == ("fr",)
    assert case.reference_answer == "On the 5th."


@pytest.mark.spec("EVL-003")
def test_an_unanswerable_case_has_no_relevant_quotes():
    dataset = parse_dataset([line(answerable=False, relevant=[])])

    assert not dataset.cases[0].answerable


@pytest.mark.spec("EVL-004")
def test_duplicate_case_ids_are_rejected_with_their_line_numbers():
    with pytest.raises(DatasetError, match=r"duplicate id 'lease-1' on lines 1 and 3"):
        parse_dataset([line(), line(id="lease-2"), line()])


@pytest.mark.spec("EVL-002")
@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ("{not json", r"line 1: not valid JSON"),
        (line(question=""), r"line 1: 'question' must be a non-empty string"),
        (line(answerable=True, relevant=[]), r"line 1: an answerable case needs relevant quotes"),
        (line(answerable=False), r"line 1: an unanswerable case has no relevant quotes"),
        (line(relevant=[{"source": "lease.md"}]), r"line 1: each relevant quote needs"),
    ],
    ids=["json", "question", "answerable-without-quotes", "unanswerable-with-quotes", "quote"],
)
def test_malformed_cases_are_rejected_with_their_line_number(bad: str, message: str):
    with pytest.raises(DatasetError, match=message):
        parse_dataset([bad])


def test_blank_lines_are_ignored():
    assert len(parse_dataset(["", line(), "   "]).cases) == 1


@pytest.mark.spec("EVL-001")
def test_a_relevant_quote_may_list_equivalent_alternatives():
    case = {
        "id": "c1",
        "question": "?",
        "relevant": [
            {
                "source": "a.md",
                "quote": "Rent is due.",
                "or": [{"source": "b.md", "quote": "Pay rent."}],
            }
        ],
    }

    (relevant,) = parse_dataset([json.dumps(case)]).cases[0].relevant

    assert relevant.alternatives == (RelevantQuote("b.md", "Pay rent."),)


@pytest.mark.spec("EVL-001")
def test_an_alternative_needs_a_source_and_a_quote_too():
    case: dict[str, object] = {
        "id": "c1",
        "question": "?",
        "relevant": [{"source": "a.md", "quote": "x", "or": [{}]}],
    }

    with pytest.raises(DatasetError, match="line 1"):
        parse_dataset([json.dumps(case)])


@pytest.mark.spec("EVL-006")
def test_a_case_can_list_phrases_an_injection_tries_to_make_the_answer_say():
    dataset = parse_dataset([line(forbidden=["15 euros par mois"])])

    assert dataset.cases[0].forbidden == ("15 euros par mois",)


@pytest.mark.spec("EVL-006")
@pytest.mark.parametrize("forbidden", ["15 euros", [""], [3]])
def test_forbidden_phrases_are_non_empty_strings(forbidden: object):
    with pytest.raises(DatasetError, match="'forbidden'"):
        parse_dataset([line(forbidden=forbidden)])
