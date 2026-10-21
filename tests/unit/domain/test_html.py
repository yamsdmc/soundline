from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundline.domain.html import parse_html


def kinds_and_texts(raw: str) -> list[tuple[str, str]]:
    document = parse_html(raw)
    return [(e.kind, document.text[e.span.start : e.span.end]) for e in document.elements]


@pytest.mark.spec("ING-022")
def test_headings_paragraphs_and_list_items_become_elements():
    raw = """<html><body>
      <h1>Lease</h1>
      <h2>Payment</h2>
      <p>Rent is   due on the <strong>5th</strong>.</p>
      <ul><li>Pets allowed.</li><li>No smoking.</li></ul>
    </body></html>"""

    assert kinds_and_texts(raw) == [
        ("heading", "Lease"),
        ("heading", "Payment"),
        ("paragraph", "Rent is due on the 5th."),
        ("list_item", "Pets allowed."),
        ("list_item", "No smoking."),
    ]
    assert [e.level for e in parse_html(raw).elements[:2]] == [1, 2]


@pytest.mark.spec("ING-023")
def test_scripts_styles_and_navigation_are_not_content():
    raw = """<nav><a href="/">Home</a> | <a href="/rent">Rent</a></nav>
      <script>var rent = "secret";</script><style>p { color: red }</style>
      <p>Rent is due.</p>
      <footer>Rent policy © 2024</footer>"""

    assert kinds_and_texts(raw) == [("paragraph", "Rent is due.")]


@pytest.mark.spec("ING-024")
def test_a_table_becomes_one_markdown_table_element():
    raw = """<table>
      <tr><th>Month</th><th>Rent</th></tr>
      <tr><td>March</td><td>900 €</td></tr>
    </table>"""

    assert kinds_and_texts(raw) == [("table", "| Month | Rent |\n|---|---|\n| March | 900 € |")]


@pytest.mark.spec("ING-020", "ING-022")
def test_preformatted_code_keeps_its_whitespace():
    raw = "<p>Example:</p><pre><code>def due(day):\n    return  day == 5</code></pre>"

    assert kinds_and_texts(raw) == [
        ("paragraph", "Example:"),
        ("code", "def due(day):\n    return  day == 5"),
    ]


def test_entities_are_decoded():
    assert kinds_and_texts("<p>Rent &amp; fees: 5&nbsp;%</p>") == [
        ("paragraph", "Rent & fees: 5 %")
    ]


@pytest.mark.spec("ING-021")
def test_every_element_maps_back_to_where_its_text_starts_in_the_html():
    raw = "<h1>Lease</h1>\n<p>Rent is due.</p>"
    document = parse_html(raw)

    starts = [document.original_offset(e.span.start) for e in document.elements]

    assert [raw[offset : offset + 4] for offset in starts] == ["Leas", "Rent"]


html_blocks = st.sampled_from(
    [
        "<h1>Title</h1>",
        "<h2>Section</h2>",
        "<p>Plain   paragraph <em>with</em> markup.</p>",
        "<ul><li>one</li><li>two</li></ul>",
        "<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>",
        "<pre>  code   kept\nline</pre>",
        "<script>ignored()</script>",
        "<div>loose text</div>",
        "<p>Rent &amp; fees</p>",
    ]
)


@given(st.lists(html_blocks, max_size=8), st.sampled_from(["", "\n", "\n  "]))
def test_elements_are_ordered_disjoint_spans_of_the_document_text(parts: list[str], gap: str):
    document = parse_html(gap.join(parts))
    spans = [e.span for e in document.elements]

    assert all(0 <= s.start < s.end <= len(document.text) for s in spans)
    assert all(a.end <= b.start for a, b in pairwise(spans))
    assert "ignored" not in document.text


@pytest.mark.spec("ING-023")
@pytest.mark.parametrize(
    "noise",
    [
        '<div role="alert"><p>Link sent!</p></div>',
        '<form action="#"><p>Was this page useful?</p><button>Yes</button></form>',
        '<div aria-hidden="true"><p>Decorative</p></div>',
        "<div hidden><p>Hidden</p></div>",
        '<div class="sp-notation sp-no-print"><p>Rate this page</p></div>',
        '<div role="dialog"><div><p>Cookies?</p></div></div>',
    ],
    ids=["alert", "form", "aria-hidden", "hidden", "no-print", "nested-dialog"],
)
def test_interface_chrome_is_not_content(noise: str):
    raw = f"<p>Rent is due.</p>{noise}<p>Pets are allowed.</p>"

    assert kinds_and_texts(raw) == [
        ("paragraph", "Rent is due."),
        ("paragraph", "Pets are allowed."),
    ]


def test_content_resumes_after_a_skipped_element_with_nested_divs_and_void_tags():
    raw = (
        '<div class="page"><div role="status"><div><img src="x.png"><br>Saved</div></div>'
        "<p>Rent is due.</p></div><p>Pets are allowed.</p>"
    )

    assert [text for _, text in kinds_and_texts(raw)] == ["Rent is due.", "Pets are allowed."]
