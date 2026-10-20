import pytest

from soundline import AnswerStatus, Soundline
from soundline.testing import ScriptedLanguageModel

LEASE = """# Lease agreement

## 1. Parties

The landlord is Ms. Martin. The tenant is Mr. Durand.

## 2. Payment

Rent is due on the 5th of each month. A 5% penalty applies after 10 days.

## 3. Pets

Dogs and cats are welcome in the garden.
"""


def soundline_with_lease(llm: ScriptedLanguageModel | None = None) -> Soundline:
    soundline = Soundline.in_memory(llm=llm or ScriptedLanguageModel(), max_tokens=24)
    soundline.ingest_text("lease.md", LEASE)
    return soundline


@pytest.mark.spec("ING-043", "ING-047", "RET-004")
def test_a_markdown_document_is_searched_section_by_section():
    hit = soundline_with_lease().search("penalty")[0]

    assert (
        hit.text
        == "2. Payment\n\nRent is due on the 5th of each month. A 5% penalty applies after 10 days."
    )
    assert hit.section_path == ("Lease agreement", "2. Payment")


@pytest.mark.spec("GEN-031")
def test_a_citation_from_a_later_chunk_is_resolved_to_its_span_in_the_whole_document():
    quote = "A 5% penalty applies after 10 days"
    llm = ScriptedLanguageModel(
        {
            "claims": [
                {
                    "text": "Late rent costs 5%.",
                    "citations": [{"evidence_id": "E1", "quote": quote}],
                }
            ]
        }
    )
    soundline = soundline_with_lease(llm)

    answer = soundline.ask("penalty after 10 days")  # unambiguous: ranking is not under test

    assert answer.status is AnswerStatus.ANSWERED
    citation = answer.citations[0]
    assert soundline.document_text("lease.md")[citation.span.start : citation.span.end] == quote
