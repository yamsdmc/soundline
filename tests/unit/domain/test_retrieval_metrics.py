import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundline.domain.evaluation import Located, retrieval_metrics
from soundline.domain.quotes import Span
from soundline.domain.runs import aggregate


def at(start: int, end: int, source: str = "lease.md") -> Located:
    return Located(source, Span(start, end))


QUOTE_A = at(100, 120)  # 20 characters
QUOTE_B = at(300, 340)


@pytest.mark.spec("EVL-001")
@pytest.mark.parametrize(
    ("hit", "relevant"),
    [
        (at(90, 130), True),  # contains the quote
        (at(110, 200), True),  # covers 10/20: "at least 50%" (EVL-001) includes exactly half
        (at(111, 200), False),  # covers 9/20
        (at(100, 120, source="other.md"), False),  # same span, other document
    ],
    ids=["contains", "exactly-half", "less-than-half", "other-source"],
)
def test_a_hit_is_relevant_when_it_covers_at_least_half_of_a_quote(hit: Located, relevant: bool):
    metrics = retrieval_metrics([QUOTE_A], [hit], ks=(1,))

    assert metrics["hit_rate@1"] == (1.0 if relevant else 0.0)


@pytest.mark.spec("EVL-011")
def test_worked_example_with_two_quotes_and_one_miss():
    hits = [at(0, 50), at(95, 125), at(500, 520), at(290, 350)]

    metrics = retrieval_metrics([QUOTE_A, QUOTE_B], hits, ks=(1, 3, 5))

    assert metrics["hit_rate@1"] == 0.0
    assert metrics["recall@1"] == 0.0
    assert metrics["recall@3"] == 0.5
    assert metrics["recall@5"] == 1.0
    assert metrics["precision@3"] == pytest.approx(1 / 3)
    assert metrics["mrr"] == 0.5
    ideal = 1 + 1 / math.log2(3)
    assert metrics["ndcg@5"] == pytest.approx((1 / math.log2(3) + 1 / math.log2(5)) / ideal)


@pytest.mark.spec("EVL-011")
def test_two_hits_on_the_same_quote_count_once():
    hits = [at(95, 125), at(98, 122)]

    metrics = retrieval_metrics([QUOTE_A, QUOTE_B], hits, ks=(2,))

    assert metrics["recall@2"] == 0.5
    assert metrics["ndcg@2"] == pytest.approx(1 / (1 + 1 / math.log2(3)))


def test_no_hits_scores_zero_and_perfect_hits_score_one():
    assert set(retrieval_metrics([QUOTE_A], [], ks=(5,)).values()) == {0.0}
    assert set(retrieval_metrics([QUOTE_A], [at(100, 120)], ks=(1,)).values()) == {1.0}


positions = st.integers(0, 50).map(lambda start: at(start * 10, start * 10 + 15))


@pytest.mark.spec("INV-EVL-1", "INV-EVL-2")
@given(st.lists(positions, min_size=1, max_size=4), st.lists(positions, max_size=10))
def test_metrics_are_bounded_and_recall_grows_with_k(quotes: list[Located], hits: list[Located]):
    metrics = retrieval_metrics(quotes, hits, ks=(1, 3, 5, 10))

    assert all(0.0 <= value <= 1.0 for value in metrics.values())
    recalls = [metrics[f"recall@{k}"] for k in (1, 3, 5, 10)]
    assert recalls == sorted(recalls)


def test_aggregated_metrics_are_listed_in_natural_order():
    per_case = {"c": retrieval_metrics([QUOTE_A], [QUOTE_A], ks=(10, 3))}

    assert list(aggregate(per_case))[:4] == ["hit_rate@3", "hit_rate@10", "mrr", "ndcg@3"]
