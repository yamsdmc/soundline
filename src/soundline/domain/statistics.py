"""Confidence intervals and paired comparisons for evaluation runs (EVL-050 to EVL-053).

Scores are keyed by case ID and processed in ID order, so results never depend on the
order cases were run in (INV-EVL-4).
"""

import math
import random
from collections.abc import Mapping
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


def compare_paired(
    before: Mapping[str, float],
    after: Mapping[str, float],
    tolerance: float,
    resamples: int = 2000,
    seed: int = 42,
) -> Comparison:
    """Per-case differences on the cases both runs share (EVL-051). A verdict needs the whole
    interval of the difference beyond the tolerance (EVL-052)."""
    shared = before.keys() & after.keys()
    difference = bootstrap_mean({c: after[c] - before[c] for c in shared}, resamples, seed)
    if difference.high < -tolerance:
        verdict = Verdict.REGRESSED
    elif difference.low > tolerance:
        verdict = Verdict.IMPROVED
    else:
        verdict = Verdict.NO_SIGNIFICANT_CHANGE
    baseline = bootstrap_mean({c: before[c] for c in shared}, resamples, seed)
    too_few = (baseline.high - baseline.low) / 2 > tolerance
    return Comparison(difference, verdict, too_few)
