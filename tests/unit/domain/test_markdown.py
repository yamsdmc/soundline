from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundline.domain.markdown import parse_markdown


def kinds_and_texts(raw: str) -> list[tuple[str, str]]:
    document = parse_markdown(raw)
    return [(e.kind, document.text[e.span.start : e.span.end]) for e in document.elements]


@pytest.mark.spec("ING-022")
def test_blank_lines_separate_paragraphs():
    assert kinds_and_texts("Rent is due.\nOn the 5th.\n\nPets  are allowed.") == [
        ("paragraph", "Rent is due.\nOn the 5th."),
        ("paragraph", "Pets are allowed."),
    ]


@pytest.mark.spec("ING-022")
def test_headings_carry_their_level_and_their_title_as_text():
    document = parse_markdown("# Lease\n\n## 3. Payment\n\nRent is due.")

    assert [(e.kind, e.level) for e in document.elements] == [
        ("heading", 1),
        ("heading", 2),
        ("paragraph", 0),
    ]
    assert document.text.split("\n\n")[:2] == ["Lease", "3. Payment"]


@pytest.mark.spec("ING-020", "ING-022")
def test_fenced_code_is_kept_verbatim_including_indentation():
    raw = "Example:\n\n```python\ndef due(day):\n    return  day == 5\n```\n"

    assert kinds_and_texts(raw) == [
        ("paragraph", "Example:"),
        ("code", "def due(day):\n    return  day == 5"),
    ]


@pytest.mark.spec("ING-022", "ING-024")
def test_a_table_is_one_element_with_one_line_per_row():
    raw = "| Month |  Rent |\n|---|---|\n| March | 900 |\n"

    assert kinds_and_texts(raw) == [("table", "| Month | Rent |\n|---|---|\n| March | 900 |")]


@pytest.mark.spec("ING-022")
def test_each_list_item_is_an_element():
    assert kinds_and_texts("- Rent is due.\n- Pets  are allowed.\n1. Keys returned.") == [
        ("list_item", "- Rent is due."),
        ("list_item", "- Pets are allowed."),
        ("list_item", "1. Keys returned."),
    ]


@pytest.mark.spec("ING-021")
def test_every_element_maps_back_to_where_it_starts_in_the_original():
    raw = "# Lease\r\n\r\nRent  is due.\r\n\r\n```\r\n  x = 1\r\n```"
    document = parse_markdown(raw)

    starts = [raw[document.original_offset(e.span.start)] for e in document.elements]

    assert starts == ["L", "R", " "]


blocks = st.sampled_from(
    [
        "# Title",
        "## Section",
        "Plain  paragraph\nwith two lines.",
        "- item one",
        "1. item two",
        "| a | b |\n|---|---|\n| 1 | 2 |",
        "```\n  code  kept\n```",
        "Trailing spaces   ",
    ]
)


@given(st.lists(blocks, max_size=8), st.sampled_from(["\n\n", "\r\n\r\n", "\n\n\n"]))
def test_elements_are_ordered_disjoint_spans_of_the_document_text(parts: list[str], gap: str):
    document = parse_markdown(gap.join(parts))
    spans = [e.span for e in document.elements]
    prose = [e.span for e in document.elements if e.kind != "code"]  # code keeps its indentation

    assert all(0 <= s.start < s.end <= len(document.text) for s in spans)
    assert all(a.end <= b.start for a, b in pairwise(spans))
    assert all(not document.text[s.start : s.end].startswith((" ", "\n")) for s in prose)
