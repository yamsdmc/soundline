import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from soundline.domain.quotes import Span, locate_quote


def test_a_quote_found_verbatim_is_located_at_its_exact_span():
    text = "Rent is due on the 5th. Pets are allowed."

    assert locate_quote("Pets are allowed", text) == Span(24, 40)


def test_a_quote_absent_from_the_text_is_not_located():
    assert locate_quote("Parking is free", "Rent is due on the 5th.") is None


def test_an_empty_or_blank_quote_proves_nothing_and_is_not_located():
    assert locate_quote("", "Rent is due on the 5th.") is None
    assert locate_quote("   ", "Rent is due   on the 5th.") is None


@pytest.mark.spec("INV-GEN-1")
@given(text=st.text(), data=st.data())
def test_a_located_span_always_points_at_the_quote_in_the_text(text: str, data: st.DataObject):
    start = data.draw(st.integers(0, len(text)))
    end = data.draw(st.integers(start, len(text)))
    quote = text[start:end]
    assume(quote.strip())

    span = locate_quote(quote, text)

    assert span is not None
    assert text[span.start : span.end] == quote
