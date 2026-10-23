import pytest

from soundline.adapters.parsers.pypdf_pages import PypdfPages
from soundline.domain.errors import UnreadableDocumentError
from soundline.domain.pdf import parse_pdf_pages
from soundline.testing.pdf import make_pdf

LEASE = [
    ["Bail d'habitation", "", "Le loyer est payable", "le 5 de chaque mois."],
    [],
    ["Le dépôt de garantie est rendu", "dans un délai de 1 mois."],
]


@pytest.mark.spec("ING-025")
def test_the_text_layer_is_read_page_by_page_in_reading_order():
    pages = PypdfPages().pages(make_pdf(LEASE))

    assert parse_pdf_pages(pages).text == (  # golden reading-order text
        "Bail d'habitation\n\n"
        "Le loyer est payable le 5 de chaque mois.\n\n"
        "Le dépôt de garantie est rendu dans un délai de 1 mois."
    )
    assert pages[1].strip() == ""
    assert parse_pdf_pages(pages).pages[-1][0] == 3


@pytest.mark.spec("ING-026")
def test_a_file_that_is_not_a_readable_pdf_is_reported():
    with pytest.raises(UnreadableDocumentError):
        PypdfPages().pages(b"%PDF-1.4 not really")
