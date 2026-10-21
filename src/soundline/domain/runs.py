"""Evaluation runs, comparisons, gates and reports (EVL-060 to EVL-066)."""

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, cast

from soundline.domain.errors import SoundlineError
from soundline.domain.statistics import Comparison, Estimate, Verdict, compare_paired


class RunMismatchError(SoundlineError):
    code = "run_mismatch"


@dataclass(frozen=True)
class EvalRun:
    name: str
    created_at: str
    dataset: Mapping[str, object]
    """path, sha256 of its content, number of cases (EVL-060)."""
    index: Mapping[str, object]
    """fingerprint and components of the pipeline that built the index."""
    settings: Mapping[str, object]
    per_case: Mapping[str, Mapping[str, float]]
    metrics: Mapping[str, Estimate]
    warnings: list[str] = field(default_factory=list[str])

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["cases"] = len(self.per_case)
        data["metrics"] = {name: asdict(estimate) for name, estimate in self.metrics.items()}
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvalRun":
        return cls(
            name=data["name"],
            created_at=data["created_at"],
            dataset=data["dataset"],
            index=data["index"],
            settings=data["settings"],
            per_case=data["per_case"],
            metrics={name: Estimate(**value) for name, value in data["metrics"].items()},
            warnings=list(data.get("warnings", [])),
        )


def aggregate(per_case: Mapping[str, Mapping[str, float]]) -> dict[str, Estimate]:
    from soundline.domain.statistics import bootstrap_mean  # noqa: PLC0415

    names = sorted({name for metrics in per_case.values() for name in metrics}, key=_natural)
    return {name: bootstrap_mean({c: m[name] for c, m in per_case.items()}) for name in names}


def compare_runs(baseline: EvalRun, run: EvalRun, tolerance: float = 0.0) -> dict[str, Comparison]:
    """Per-metric paired comparison; runs on different datasets cannot be compared (EVL-066)."""
    if baseline.dataset.get("sha256") != run.dataset.get("sha256"):
        raise RunMismatchError(
            f"runs {baseline.name!r} and {run.name!r} used different datasets"
            " (content hashes differ); evaluate both on the same dataset"
        )
    return {
        name: compare_paired(
            {c: m[name] for c, m in baseline.per_case.items() if name in m},
            {c: m[name] for c, m in run.per_case.items() if name in m},
            tolerance,
        )
        for name in baseline.metrics
        if name in run.metrics
    }


@dataclass(frozen=True)
class Rule:
    metric: str
    max_regression: float | None = None
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True)
class RuleOutcome:
    rule: Rule
    passed: bool
    explanation: str


def parse_rules(toml_text: str) -> list[Rule]:
    data = tomllib.loads(toml_text)
    rules = cast("list[Mapping[str, Any]]", data.get("rule", []))
    if not rules:
        raise RunMismatchError("the rules file declares no [[rule]]")
    return [
        Rule(
            metric=str(rule["metric"]),
            max_regression=rule.get("max_regression"),
            min_value=rule.get("min_value"),
            max_value=rule.get("max_value"),
        )
        for rule in rules
    ]


def gate(baseline: EvalRun, run: EvalRun, rules: Sequence[Rule]) -> list[RuleOutcome]:
    """EVL-064. A regression fails only when the whole interval of the difference is beyond
    the rule's tolerance (EVL-052); absolute bounds apply to the run's mean."""
    outcomes: list[RuleOutcome] = []
    for rule in rules:
        if rule.metric not in run.metrics:
            outcomes.append(RuleOutcome(rule, False, f"{rule.metric}: not in run {run.name!r}"))
            continue
        mean = run.metrics[rule.metric].mean
        problems: list[str] = []
        if rule.max_regression is not None:
            comparison = compare_runs(baseline, run, rule.max_regression)[rule.metric]
            if comparison.verdict is Verdict.REGRESSED:
                problems.append(f"regressed by {_difference(comparison)}")
        if rule.min_value is not None and mean < rule.min_value:
            problems.append(f"{mean:.3f} is below the minimum {rule.min_value}")
        if rule.max_value is not None and mean > rule.max_value:
            problems.append(f"{mean:.3f} is above the maximum {rule.max_value}")
        explanation = "; ".join(problems) or f"ok ({mean:.3f})"
        outcomes.append(RuleOutcome(rule, not problems, f"{rule.metric}: {explanation}"))
    return outcomes


def comparison_markdown(baseline: EvalRun, run: EvalRun, tolerance: float = 0.0) -> str:
    """A table ready for a pull request comment (EVL-065)."""
    lines = [
        f"Comparison of `{run.name}` against `{baseline.name}` "
        f"({run.dataset.get('cases')} cases, 95% bootstrap intervals, tolerance {tolerance})",
        "",
        "| metric | baseline | run | difference [95% CI] | verdict |",
        "|---|---|---|---|---|",
    ]
    comparisons = compare_runs(baseline, run, tolerance)
    for name in sorted(comparisons, key=_natural):
        comparison = comparisons[name]
        flag = " ⚠️ too few cases" if comparison.too_few_cases else ""
        lines.append(
            f"| {name} | {baseline.metrics[name].mean:.3f} | {run.metrics[name].mean:.3f} "
            f"| {_difference(comparison)} | {comparison.verdict.value}{flag} |"
        )
    return "\n".join(lines)


def _difference(comparison: Comparison) -> str:
    d = comparison.difference
    return f"{d.mean:+.3f} [{d.low:+.3f}, {d.high:+.3f}]"


def _natural(metric: str) -> tuple[str, int]:
    """recall@3 before recall@10."""
    name, _, k = metric.partition("@")
    return name, int(k) if k.isdigit() else 0
