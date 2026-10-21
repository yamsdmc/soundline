import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from soundline.domain.verification import Method, verify_quote

EVIDENCE = (
    "Le loyer mensuel est de 1 250 euros, charges comprises. Au-delà de 10 jours de retard, "
    "une pénalité de 5,5 % du loyer mensuel est appliquée. Le dépôt de garantie est "
    "restitué dans un délai d'un mois après la remise des clés."
)


@pytest.mark.spec("GEN-030")
def test_an_exact_quote_is_verified_at_its_span():
    result = verify_quote("Le loyer mensuel est de 1 250 euros", EVIDENCE)

    assert result.method is Method.EXACT
    assert not result.approximate
    assert EVIDENCE[result.span.start : result.span.end] == "Le loyer mensuel est de 1 250 euros"


@pytest.mark.spec("GEN-030")
def test_case_whitespace_and_typographic_quotes_are_normalized():
    result = verify_quote(
        "le dépôt  de garantie est   RESTITUÉ dans un délai d\u2019un mois", EVIDENCE
    )

    assert result.method is Method.NORMALIZED
    assert result.quote == "Le dépôt de garantie est restitué dans un délai d'un mois"


@pytest.mark.spec("GEN-030", "GEN-038")
def test_a_typo_in_a_word_is_verified_approximately_and_shows_the_source_text():
    result = verify_quote("Le dépôt de garantie est restitué dans un délais d'un mois", EVIDENCE)

    assert result.method is Method.FUZZY
    assert result.approximate
    assert result.quote == "Le dépôt de garantie est restitué dans un délai d'un mois"


@pytest.mark.spec("GEN-037")
def test_a_changed_number_fails_however_similar_the_quote():
    """'5,5 %' became '6,5 %': similarity is ~0.97, the meaning is inverted."""
    result = verify_quote("une pénalité de 6,5 % du loyer mensuel est appliquée", EVIDENCE)

    assert result.method is Method.FAILED
    assert result.reason == "critical_token_mismatch"


@pytest.mark.spec("GEN-037")
def test_numbers_match_across_decimal_separators_and_spacing():
    result = verify_quote("une pénalité de 5.5% du loyer mensuel", EVIDENCE)

    assert result.method in (Method.NORMALIZED, Method.FUZZY)
    assert result.quote == "une pénalité de 5,5 % du loyer mensuel"


@pytest.mark.spec("GEN-037")
def test_identifiers_are_critical_tokens():
    evidence = "Invoice INV-2024-0043 includes the late payment penalty from March."

    result = verify_quote("Invoice INV-2024-0042 includes the late payment penalty", evidence)

    assert result.method is Method.FAILED
    assert result.reason == "critical_token_mismatch"


@pytest.mark.spec("GEN-038")
def test_short_quotes_are_never_matched_fuzzily():
    assert verify_quote("Le loyr mensuel", EVIDENCE).method is Method.FAILED


@pytest.mark.spec("GEN-030")
@pytest.mark.parametrize("quote", ["", "   ", "Parking is free for every tenant of the building"])
def test_blank_or_absent_quotes_fail(quote: str):
    result = verify_quote(quote, EVIDENCE)

    assert result.method is Method.FAILED
    assert result.reason in {"blank_quote", "not_found"}


@pytest.mark.spec("INV-GEN-1", "INV-GEN-5")
@given(st.data())
def test_a_verified_quote_is_always_the_source_text_at_its_span(data: st.DataObject):
    words = EVIDENCE.split(" ")
    start = data.draw(st.integers(0, len(words) - 4))
    length = data.draw(st.integers(4, min(12, len(words) - start)))
    quote = " ".join(words[start : start + length])
    mangled = data.draw(st.sampled_from([quote, quote.upper(), quote.replace(" ", "  ")]))
    assume(mangled.strip())

    result = verify_quote(mangled, EVIDENCE)

    assert result.method is not Method.FAILED
    assert EVIDENCE[result.span.start : result.span.end] == result.quote
