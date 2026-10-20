import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundline.domain.normalization import normalize


@pytest.mark.spec("ING-020")
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Rent  is\tdue", "Rent is due"),
        ("Rent\r\nis due", "Rent\nis due"),
        ("Rent\n\n\n\nis due", "Rent\n\nis due"),
        ("  Rent is due \n", "Rent is due"),
        ("Rent \n is due", "Rent\nis due"),
        ("Café", "Café"),
    ],
    ids=["spaces-and-tabs", "crlf", "blank-lines", "edges", "around-newlines", "nfc"],
)
def test_text_is_normalized(raw: str, expected: str):
    assert normalize(raw).text == expected


@pytest.mark.spec("ING-021")
def test_each_normalized_character_maps_back_to_its_original_offset():
    raw = "Rent  is\r\ndue"

    normalized = normalize(raw)

    assert normalized.text == "Rent is\ndue"
    assert [raw[normalized.original_offset(i)] for i in (0, 5, 7, 8)] == ["R", "i", "\r", "d"]


@pytest.mark.spec("ING-021")
def test_the_end_of_the_text_maps_to_the_end_of_the_original():
    raw = "Rent is due   "

    assert normalize(raw).original_offset(len("Rent is due")) == len("Rent is due")


nasty_text = st.text(alphabet=st.sampled_from("ab é́\t\r\n "), max_size=40)


@given(nasty_text)
def test_normalization_is_idempotent(raw: str):
    once = normalize(raw).text

    assert normalize(once).text == once


@given(nasty_text)
def test_normalized_text_follows_every_rule(raw: str):
    text = normalize(raw).text

    assert text == unicodedata.normalize("NFC", text)
    for forbidden in ("\r", "\t", "  ", "\n\n\n", " \n", "\n "):
        assert forbidden not in text
    assert text == text.strip()


@given(nasty_text)
def test_original_offsets_are_monotonic_and_within_the_original(raw: str):
    normalized = normalize(raw)
    offsets = [normalized.original_offset(i) for i in range(len(normalized.text) + 1)]

    assert offsets == sorted(offsets)
    assert all(0 <= offset <= len(raw) for offset in offsets)
