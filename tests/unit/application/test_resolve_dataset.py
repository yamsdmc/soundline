import json

import pytest

from soundline.application.evaluate import resolve_dataset
from soundline.application.ports import StoredDocument
from soundline.domain.datasets import DatasetError, parse_dataset
from soundline.domain.evaluation import Located
from soundline.domain.quotes import Span
from soundline.testing import InMemoryDocumentStore

LEASE = "Rent is due on the 5th.\n\nA 5% penalty applies after 10 days."
URI = "file:///home/me/docs/lease.md"


def store() -> InMemoryDocumentStore:
    documents = InMemoryDocumentStore()
    documents.save(StoredDocument(URI, "r1", LEASE))
    return documents


def dataset(*quotes: tuple[str, str], case_id: str = "c1"):
    relevant = [{"source": source, "quote": quote} for source, quote in quotes]
    return parse_dataset([json.dumps({"id": case_id, "question": "?", "relevant": relevant})])


@pytest.mark.spec("EVL-001", "EVL-002")
def test_a_quote_resolves_to_its_span_in_the_document_named_by_its_file_name():
    resolved = resolve_dataset(dataset(("lease.md", "A 5% penalty")), store())

    assert resolved["c1"] == [(Located(URI, Span(25, 37)),)]


@pytest.mark.spec("EVL-002")
def test_case_and_whitespace_differences_still_resolve_to_the_exact_source_span():
    resolved = resolve_dataset(dataset(("lease.md", "due on the 5th.  a 5%")), store())

    assert resolved["c1"] == [(Located(URI, Span(8, 29)),)]
    assert LEASE[8:29] == "due on the 5th.\n\nA 5%"


@pytest.mark.spec("EVL-002")
def test_a_quote_not_in_the_document_is_reported_with_the_closest_sentence():
    with pytest.raises(DatasetError) as error:
        resolve_dataset(dataset(("lease.md", "A 6% penalty applies after 10 days")), store())

    message = str(error.value)
    assert "case 'c1'" in message
    assert "not found in lease.md" in message
    assert "closest: 'A 5% penalty applies after 10 days.'" in message


@pytest.mark.spec("EVL-002")
def test_every_problem_is_reported_at_once():
    with pytest.raises(DatasetError) as error:
        resolve_dataset(dataset(("unknown.md", "Rent"), ("lease.md", "Parking")), store())

    message = str(error.value)
    assert "no indexed document matches 'unknown.md'" in message
    assert "'Parking' not found in lease.md" in message


@pytest.mark.spec("EVL-002", "EVL-001")
def test_a_quote_repeated_in_a_document_resolves_to_every_occurrence():
    """Real pages repeat sentences across variants ('furnished' and 'unfurnished' tabs):
    a hit on any occurrence is a hit on the quote."""
    documents = InMemoryDocumentStore()
    text = "Unfurnished: return within 1 month.\n\nFurnished: return within 1 month."
    documents.save(StoredDocument(URI, "r1", text))

    resolved = resolve_dataset(dataset(("lease.md", "return within 1 month")), documents)

    assert resolved["c1"] == [(Located(URI, Span(13, 34)), Located(URI, Span(48, 69)))]


@pytest.mark.spec("EVL-001", "EVL-002")
def test_alternatives_resolve_into_one_quote_with_every_occurrence():
    documents = store()
    other = "file:///home/me/docs/rules.md"
    documents.save(StoredDocument(other, "r2", "Rules. Rent is due on the 5th."))
    case = {
        "id": "c1",
        "question": "?",
        "relevant": [
            {
                "source": "lease.md",
                "quote": "Rent is due on the 5th",
                "or": [{"source": "rules.md", "quote": "Rent is due on the 5th"}],
            }
        ],
    }

    resolved = resolve_dataset(parse_dataset([json.dumps(case)]), documents)

    assert resolved["c1"] == [(Located(URI, Span(0, 22)), Located(other, Span(7, 29)))]
