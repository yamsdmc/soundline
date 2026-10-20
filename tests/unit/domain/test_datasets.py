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
