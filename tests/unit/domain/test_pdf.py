import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundline.domain.pdf import page_at, pages_within, parse_pdf_pages
from soundline.domain.quotes import Span

PAGES = [
    "Bail d'habitation\n\nLe loyer est payable\nle 5 de chaque mois.",
    "",
    "Le dépôt de garantie est rendu\ndans un délai de 1 mois.",
]


@pytest.mark.spec("ING-025")
def test_each_page_becomes_paragraphs_whose_wrapped_lines_are_joined():
    document = parse_pdf_pages(PAGES)

    assert document.text == (
        "Bail d'habitation\n\n"
        "Le loyer est payable le 5 de chaque mois.\n\n"
        "Le dépôt de garantie est rendu dans un délai de 1 mois."
    )
    assert [e.kind for e in document.elements] == ["paragraph"] * 3


@pytest.mark.spec("ING-025", "ING-021")
def test_page_boundaries_are_kept_and_an_empty_page_keeps_its_number():
    document = parse_pdf_pages(PAGES)

    third = document.text.index("Le dépôt")
    assert document.pages == ((1, 0), (3, third))
    assert page_at(document.pages, third - 1) == 1
    assert page_at(document.pages, third) == 3


@pytest.mark.spec("ING-021")
def test_every_character_maps_back_to_its_page_text():
    document = parse_pdf_pages(PAGES)
    raw = "\f".join(PAGES)

    offset = document.text.index("1 mois")

    assert raw[document.original_offset(offset) :].startswith("1 mois")


@pytest.mark.spec("ING-047")
def test_a_span_lists_the_pages_it_touches_with_where_each_starts():
    pages = ((1, 0), (2, 100), (4, 250))

    assert pages_within(Span(50, 120), pages) == ((1, 0), (2, 100))
    assert pages_within(Span(120, 130), pages) == ((2, 100),)
    assert pages_within(Span(260, 300), pages) == ((4, 250),)
    assert pages_within(Span(10, 20), ()) == ()


@pytest.mark.spec("INV-ING-7")
@given(st.lists(st.text(alphabet="ab \n", max_size=40), min_size=1, max_size=6))
def test_page_numbers_never_decrease_through_the_text(pages: list[str]):
    document = parse_pdf_pages(pages)

    numbers = [page_at(document.pages, offset) or 0 for offset in range(len(document.text))]

    assert numbers == sorted(numbers)
