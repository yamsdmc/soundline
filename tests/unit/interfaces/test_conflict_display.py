import pytest

from soundline.domain.answers import (
    Answer,
    AnswerStatus,
    Citation,
    Claim,
    Conflict,
    answer_to_dict,
    render,
)
from soundline.domain.quotes import Span
from soundline.interfaces.answer_text import answer_text
from soundline.interfaces.viewer import render_viewer

OFFICIAL = Citation("official.html", "10 % of the rent", Span(15, 31))
BLOG = Citation("blog.html", "50 % of the rent", Span(15, 31))
DOCUMENTS = {
    "official.html": "The penalty is 10 % of the rent.",
    "blog.html": "The penalty is 50 % of the rent.",
}


def answer() -> Answer:
    claims = (
        Claim("Official: 10 %.", (OFFICIAL,)),
        Claim("A blog: 50 %.", (BLOG,)),
    )
    text, citations = render(claims)
    return Answer(
        AnswerStatus.ANSWERED,
        text=text,
        citations=citations,
        claims=claims,
        conflicts=(Conflict("the late penalty", (OFFICIAL, BLOG)),),
    )


@pytest.mark.spec("GEN-092")
def test_the_cli_says_which_citations_disagree_after_the_answer():
    lines = answer_text(answer()).splitlines()

    assert lines[0] == "Official: 10 % [1]. A blog: 50 % [2]."
    assert "Sources disagree on the late penalty: [1] [2]" in lines


@pytest.mark.spec("GEN-092")
def test_the_json_form_lists_each_conflict_with_its_citation_numbers():
    assert answer_to_dict(answer())["conflicts"] == [
        {"about": "the late penalty", "citations": [1, 2]}
    ]


@pytest.mark.spec("GEN-092", "CLI-007")
def test_the_viewer_marks_the_conflict():
    html = render_viewer("What is the penalty?", answer(), DOCUMENTS.__getitem__)

    assert 'class="conflict"' in html
    assert "Sources disagree on the late penalty" in html
