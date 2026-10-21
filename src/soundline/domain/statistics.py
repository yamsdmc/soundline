"""Confidence intervals and paired comparisons for evaluation runs (EVL-050 to EVL-053).

Scores are keyed by case ID and processed in ID order, so results never depend on the
order cases were run in (INV-EVL-4).
"""

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Estimate:
    mean: float
    low: float
    high: float
    cases: int


class Verdict(Enum):
    IMPROVED = "improved"
    REGRESSED = "regressed"
    NO_SIGNIFICANT_CHANGE = "no significant change"


@dataclass(frozen=True)
class Comparison:
    difference: Estimate
    """after - before, per case, with a bootstrap interval."""
    verdict: Verdict
    too_few_cases: bool
    """The baseline's own interval is wider than the tolerance: a change of that size cannot
    be told apart from noise with this dataset (EVL-053)."""


def bootstrap_mean(
    scores: Mapping[str, float],
    resamples: int = 2000,
    seed: int = 42,
    confidence: float = 0.95,
) -> Estimate:
    """Mean with a percentile bootstrap interval over cases (EVL-050)."""
    values = [scores[case] for case in sorted(scores)]
    if not values:
        return Estimate(0.0, 0.0, 0.0, 0)
    rng = random.Random(seed)
    n = len(values)
    means = sorted(math.fsum(rng.choices(values, k=n)) / n for _ in range(resamples))
    tail = (1 - confidence) / 2
    low = means[math.floor(tail * (resamples - 1))]
    high = means[math.ceil((1 - tail) * (resamples - 1))]
    return Estimate(math.fsum(values) / n, low, high, n)


def compare_paired(  # noqa: PLR0913  # keyword-only options
    before: Mapping[str, float],
    after: Mapping[str, float],
    tolerance: float,
    resamples: int = 2000,
    seed: int = 42,
    *,
    lower_is_better: bool = False,
) -> Comparison:
    """Per-case differences on the cases both runs share (EVL-051). A verdict needs the whole
    interval of the difference beyond the tolerance (EVL-052)."""
    shared = before.keys() & after.keys()
    difference = bootstrap_mean({c: after[c] - before[c] for c in shared}, resamples, seed)
    worse, better = (difference.low > tolerance, difference.high < -tolerance)
    if not lower_is_better:
        worse, better = better, worse
    if worse:
        verdict = Verdict.REGRESSED
    elif better:
        verdict = Verdict.IMPROVED
    else:
        verdict = Verdict.NO_SIGNIFICANT_CHANGE
    baseline = bootstrap_mean({c: before[c] for c in shared}, resamples, seed)
    too_few = (baseline.high - baseline.low) / 2 > tolerance
    return Comparison(difference, verdict, too_few)


def describe(values: Sequence[float]) -> dict[str, float]:
    """Mean, median, 95th percentile (linear interpolation) and total, for operational
    metrics such as latency and cost (EVL-030)."""
    if not values:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "total": 0.0}
    ordered = sorted(values)
    total = math.fsum(ordered)
    return {
        "mean": total / len(ordered),
        "p50": _percentile(ordered, 0.5),
        "p95": _percentile(ordered, 0.95),
        "total": total,
    }


def _percentile(ordered: Sequence[float], fraction: float) -> float:
    position = fraction * (len(ordered) - 1)
    below = math.floor(position)
    above = min(below + 1, len(ordered) - 1)
    return ordered[below] + (ordered[above] - ordered[below]) * (position - below)
