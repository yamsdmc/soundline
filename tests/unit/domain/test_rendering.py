from soundline.domain.answers import Citation, Claim, render
from soundline.domain.quotes import Span

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
