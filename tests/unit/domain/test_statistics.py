import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundline.domain.statistics import Verdict, bootstrap_mean, compare_paired

SCORES = {f"case-{i}": value for i, value in enumerate([1, 0, 1, 1, 0, 1, 1, 1, 0, 1])}


@pytest.mark.spec("EVL-050")
def test_the_interval_contains_the_mean_and_is_reproducible_with_its_seed():
    first = bootstrap_mean(SCORES, seed=7)

    assert first.mean == pytest.approx(0.7)
    assert first.low <= first.mean <= first.high
    assert first == bootstrap_mean(SCORES, seed=7)
    assert first.cases == 10


@pytest.mark.spec("EVL-050")
def test_identical_scores_have_a_zero_width_interval():
    estimate = bootstrap_mean(dict.fromkeys(("a", "b", "c"), 0.5))

    assert (estimate.low, estimate.mean, estimate.high) == (0.5, 0.5, 0.5)


@pytest.mark.spec("EVL-051", "EVL-052")
def test_a_run_compared_with_itself_shows_no_significant_change():  # INV-EVL-3
    comparison = compare_paired(SCORES, SCORES, tolerance=0.02)

    assert comparison.difference.mean == 0.0
    assert comparison.verdict is Verdict.NO_SIGNIFICANT_CHANGE


@pytest.mark.spec("EVL-052")
@pytest.mark.parametrize(
    ("before", "after", "verdict"),
    [
        (SCORES, dict.fromkeys(SCORES, 0.0), Verdict.REGRESSED),  # 0.7 -> 0.0
        (dict.fromkeys(SCORES, 0.0), SCORES, Verdict.IMPROVED),  # 0.0 -> 0.7
        (SCORES, dict.fromkeys(SCORES, 1.0), Verdict.NO_SIGNIFICANT_CHANGE),  # 3 of 10 cases
        (SCORES, SCORES | {"case-1": 1}, Verdict.NO_SIGNIFICANT_CHANGE),  # one case flips
    ],
    ids=["clear-regression", "clear-improvement", "too-few-cases-to-tell", "one-case-flip"],
)
def test_only_changes_beyond_tolerance_with_confidence_get_a_verdict(
    before: dict[str, float], after: dict[str, float], verdict: Verdict
):
    """0.7 -> 1.0 improves only 3 of 10 cases: the interval of the difference still includes
    zero, so no improvement can honestly be claimed with this many cases."""
    assert compare_paired(before, after, tolerance=0.02).verdict is verdict


@pytest.mark.spec("EVL-051")
def test_only_cases_present_in_both_runs_are_compared():
    comparison = compare_paired({"a": 1.0, "b": 0.0}, {"b": 0.0, "c": 1.0}, tolerance=0.0)

    assert comparison.difference.cases == 1


@pytest.mark.spec("EVL-053")
def test_a_dataset_too_small_for_the_tolerance_is_flagged():
    assert compare_paired(SCORES, SCORES, tolerance=0.02).too_few_cases
    many = {f"c{i}": 1.0 for i in range(500)}
    assert not compare_paired(many, many, tolerance=0.02).too_few_cases


@given(st.dictionaries(st.text(min_size=1, max_size=4), st.floats(0, 1), min_size=1, max_size=30))
def test_results_do_not_depend_on_case_order(scores: dict[str, float]):  # INV-EVL-4
    reversed_order = dict(reversed(list(scores.items())))

    assert bootstrap_mean(scores, resamples=200) == bootstrap_mean(reversed_order, resamples=200)
