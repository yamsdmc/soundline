import re

import pytest

from soundline.domain.answers import Answer, AnswerStatus, Citation, Claim, render
from soundline.domain.quotes import Span
from soundline.interfaces.viewer import render_viewer

TEXT = "Intro. Rent is due on the 5th. <script>alert(1)</script> Pets are allowed. Outro."
RENT = Citation("lease.md", "Rent is due on the 5th", Span(7, 29), section_path=("Lease", "Rent"))
PETS = Citation("lease.md", "Pets are allowed", Span(58, 74), approximate=True)


def answer() -> Answer:
    claims = (Claim("Rent is due on the 5th.", (RENT,)), Claim("Pets are allowed.", (PETS,)))
    text, citations = render(claims)
    return Answer(
        AnswerStatus.PARTIAL,
        text=text,
        citations=citations,
        claims=claims,
        dropped_claims=["Parking is free."],
    )


def view() -> str:
    return render_viewer("When is rent due?", answer(), {"lease.md": TEXT}.__getitem__)


@pytest.mark.spec("CLI-007")
def test_each_claim_is_linked_to_its_highlighted_citation_in_context():
    html = view()

    assert html.count('class="claim"') == 2
    assert "<mark>Rent is due on the 5th</mark>" in html
    assert "Lease &rsaquo; Rent" in html
    assert "Intro." in html  # surrounding text


@pytest.mark.spec("CLI-007", "GEN-038", "GEN-033")
def test_approximate_citations_and_dropped_claims_are_visibly_marked():
    html = view()

    assert "approximate" in html
    assert "Parking is free." in html
    assert "removed" in html


@pytest.mark.spec("CLI-007", "SEC-001")
def test_document_text_is_escaped_and_the_page_needs_no_network():
    html = view()

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert not re.search(r'(src|href)="https?:', html)


@pytest.mark.spec("CLI-007")
def test_an_abstention_says_why():
    abstained = Answer(AnswerStatus.ABSTAINED, abstention_message="nothing about parking")

    no_documents: dict[str, str] = {}

    html = render_viewer("Is parking free?", abstained, no_documents.__getitem__)

    assert "nothing about parking" in html


@pytest.mark.spec("CLI-007", "GEN-095")
def test_a_claim_is_shown_with_its_conditions():
    claim = Claim("Rent is due on the 5th.", (RENT,), conditions=("Furnished",))
    text, citations = render([claim])
    answered = Answer(AnswerStatus.ANSWERED, text=text, citations=citations, claims=(claim,))

    html = render_viewer("When?", answered, {"lease.md": TEXT}.__getitem__)

    assert "Rent is due on the 5th (Furnished)." in html
