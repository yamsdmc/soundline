import re
from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundline.domain.chunking import chunk_document
from soundline.domain.documents import ParsedDocument
from soundline.domain.markdown import parse_markdown


def words(text: str) -> int:
    return len(text.split())


def chunk_texts(raw: str, max_tokens: int) -> list[str]:
    document = parse_markdown(raw)
    return [
        document.text[c.span.start : c.span.end]
        for c in chunk_document(document, max_tokens=max_tokens, count_tokens=words)
    ]


@pytest.mark.spec("ING-040")
def test_a_short_document_is_one_chunk():
    assert chunk_texts("Rent is due on the 5th.", max_tokens=50) == ["Rent is due on the 5th."]


@pytest.mark.spec("ING-042")
def test_small_neighbouring_elements_of_a_section_are_merged_up_to_the_limit():
    raw = "Rent is due.\n\nPets are allowed.\n\nKeys are returned at the end."

    assert chunk_texts(raw, max_tokens=7) == [
        "Rent is due.\n\nPets are allowed.",
        "Keys are returned at the end.",
    ]


@pytest.mark.spec("ING-043", "ING-047")
def test_chunks_never_cross_a_section_and_carry_their_section_path():
    raw = (
        "# Lease\n\n## Payment\n\nRent is due.\n\n### Late fees\n\n5% penalty."
        "\n\n## Pets\n\nAllowed."
    )
    document = parse_markdown(raw)

    chunks = chunk_document(document, max_tokens=100, count_tokens=words)

    assert [(document.text[c.span.start : c.span.end], c.section_path) for c in chunks] == [
        ("Lease", ("Lease",)),
        ("Payment\n\nRent is due.\n\nLate fees\n\n5% penalty.", ("Lease", "Payment")),
        ("Pets\n\nAllowed.", ("Lease", "Pets")),
    ]


@pytest.mark.spec("ING-041")
def test_a_long_paragraph_is_split_at_sentence_boundaries():
    raw = "Rent is due on the 5th. Late payments cost a fee. Pets are allowed."

    assert chunk_texts(raw, max_tokens=7) == [
        "Rent is due on the 5th.",
        "Late payments cost a fee.",
        "Pets are allowed.",
    ]


@pytest.mark.spec("ING-041")
def test_a_sentence_longer_than_the_limit_is_split_between_words():
    assert chunk_texts("one two three four five six seven", max_tokens=3) == [
        "one two three",
        "four five six",
        "seven",
    ]


@pytest.mark.spec("ING-044")
def test_a_table_that_fits_stays_whole_and_a_larger_one_is_split_between_rows():
    table = "| Month | Rent |\n|---|---|\n| March | 900 |\n| April | 950 |"

    assert chunk_texts(table, max_tokens=20) == [table]
    assert chunk_texts(table, max_tokens=10) == [
        "| Month | Rent |\n|---|---|",
        "| March | 900 |\n| April | 950 |",
    ]


@pytest.mark.spec("ING-045")
def test_a_code_block_that_fits_stays_whole_and_a_larger_one_is_split_between_lines():
    code = "```\ndef due(day):\n    return day == 5\n```"

    assert chunk_texts(code, max_tokens=10) == ["def due(day):\n    return day == 5"]
    assert chunk_texts(code, max_tokens=4) == ["def due(day):", "    return day == 5"]


paragraph = st.lists(
    st.sampled_from(["Rent is due.", "Pets  are allowed!", "A", "Fees apply?", "x" * 3]),
    min_size=1,
    max_size=6,
).map(" ".join)
block = st.one_of(
    paragraph,
    st.sampled_from(["# Lease", "## Payment", "### Fees", "- item one", "| a | b |\n| 1 | 2 |"]),
    st.sampled_from(["```\n  code   line\nsecond line\n```"]),
)
documents = st.lists(block, min_size=1, max_size=8).map("\n\n".join).map(parse_markdown)


def chunked(document: ParsedDocument, max_tokens: int) -> list[str]:
    return [
        document.text[c.span.start : c.span.end]
        for c in chunk_document(document, max_tokens=max_tokens, count_tokens=words)
    ]


@pytest.mark.spec("INV-ING-4")
@given(documents, st.integers(1, 12))
def test_every_chunk_fits_the_limit(document: ParsedDocument, max_tokens: int):
    assert all(words(text) <= max_tokens for text in chunked(document, max_tokens))


@pytest.mark.spec("INV-ING-2")
@given(documents, st.integers(1, 12))
def test_chunks_cover_every_non_whitespace_character(document: ParsedDocument, max_tokens: int):
    covered = [False] * len(document.text)
    for c in chunk_document(document, max_tokens=max_tokens, count_tokens=words):
        covered[c.span.start : c.span.end] = [True] * (c.span.end - c.span.start)

    assert all(covered[i] for i, char in enumerate(document.text) if not char.isspace())


@pytest.mark.spec("INV-ING-3", "INV-ING-5")
@given(documents, st.integers(1, 12))
def test_chunks_are_ordered_non_empty_and_deterministic(document: ParsedDocument, max_tokens: int):
    first = chunk_document(document, max_tokens=max_tokens, count_tokens=words)
    spans = [c.span for c in first]

    assert all(s.start < s.end for s in spans)
    assert all(a.end <= b.start for a, b in pairwise(spans))
    assert first == chunk_document(document, max_tokens=max_tokens, count_tokens=words)


@given(documents, st.integers(1, 12))
def test_no_chunk_starts_or_ends_inside_a_word(document: ParsedDocument, max_tokens: int):
    text = document.text
    for c in chunk_document(document, max_tokens=max_tokens, count_tokens=words):
        assert c.span.start == 0 or not re.match(r"\w\w", text[c.span.start - 1 : c.span.start + 1])
        assert c.span.end == len(text) or not re.match(
            r"\w\w", text[c.span.end - 1 : c.span.end + 1]
        )


def four_chars_per_token(text: str) -> int:
    return -(-len(text) // 4)


@pytest.mark.spec("ING-041")
def test_a_single_word_longer_than_the_limit_is_cut_as_a_last_resort():
    url = "https://example.com/" + "a" * 60
    document = parse_markdown(f"See {url} now.")

    chunks = chunk_document(document, max_tokens=5, count_tokens=four_chars_per_token)

    texts = [document.text[c.span.start : c.span.end] for c in chunks]
    assert all(four_chars_per_token(text) <= 5 for text in texts)
    assert "".join(texts).replace(" ", "") == f"See{url}now."


@pytest.mark.spec("INV-ING-4")
@given(documents, st.integers(1, 6))
def test_every_chunk_fits_the_limit_whatever_the_tokenizer(
    document: ParsedDocument, max_tokens: int
):
    for c in chunk_document(document, max_tokens=max_tokens, count_tokens=four_chars_per_token):
        assert four_chars_per_token(document.text[c.span.start : c.span.end]) <= max_tokens
