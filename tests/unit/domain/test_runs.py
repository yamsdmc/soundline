import pytest

from soundline.domain.runs import EvalRun, Rule, aggregate, comparison_markdown, gate
from soundline.domain.statistics import Verdict

CASES = [f"case-{i}" for i in range(10)]


def run(name: str, metric: str, value: float) -> EvalRun:
    per_case = {case: {metric: value} for case in CASES}
    return EvalRun(name, "2026-10-21", {"sha256": "d"}, {}, {}, per_case, aggregate(per_case))


@pytest.mark.spec("EVL-052", "EVL-064")
@pytest.mark.parametrize("metric", ["false_answer_rate", "injection_success_rate", "latency_ms"])
def test_a_rise_of_a_metric_where_lower_is_better_fails_the_gate(metric: str):
    outcome = gate(run("before", metric, 0.0), run("after", metric, 1.0), [Rule(metric, 0.0)])

    assert not outcome[0].passed


@pytest.mark.spec("EVL-052", "EVL-065")
def test_fewer_false_answers_read_as_an_improvement():
    table = comparison_markdown(
        run("before", "false_answer_rate", 1.0), run("after", "false_answer_rate", 0.0)
    )

    assert f"| {Verdict.IMPROVED.value}" in table
