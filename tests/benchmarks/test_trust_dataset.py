import html
import re
from pathlib import Path

import pytest

from soundline.domain.datasets import parse_dataset

ROOT = Path(__file__).parents[2]
TRUST = ROOT / "evals" / "trust-fr"
CORPORA = (ROOT / "evals" / "logement-fr" / "corpus", TRUST / "corpus")


def folded(text: str) -> str:
    return " ".join(text.casefold().replace("\u2019", "'").split())


def page_text(path: Path) -> str:
    return folded(html.unescape(re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8"))))


@pytest.mark.spec("EVL-092", "EVL-006")
def test_every_forbidden_phrase_is_planted_in_the_corpus_the_benchmark_ingests():
    dataset = parse_dataset((TRUST / "dataset.jsonl").read_text(encoding="utf-8").splitlines())
    pages = [page_text(path) for corpus in CORPORA for path in sorted(corpus.glob("*.html"))]

    injected = [case for case in dataset.cases if case.forbidden]

    # A case none of whose phrases any page contains measures nothing: no injection plants
    # them. Other phrases of a case may be rewordings the model could produce ("1 semaine").
    assert len(injected) == 6
    assert [
        case.id
        for case in injected
        if not any(folded(phrase) in page for phrase in case.forbidden for page in pages)
    ] == []


@pytest.mark.spec("EVL-092")
def test_each_synthetic_page_says_it_is_synthetic():
    for path in sorted((TRUST / "corpus").glob("*.html")):
        assert "SYNTHETIC TEST DOCUMENT" in path.read_text(encoding="utf-8"), path.name
