import pytest
from trust_report import trust_table

from soundline.domain.runs import EvalRun, aggregate


def run(name: str, per_case: dict[str, dict[str, float]]) -> EvalRun:
    return EvalRun(name, "2026-10-21", {}, {}, {}, per_case, aggregate(per_case))


@pytest.mark.spec("EVL-092", "EVL-050", "EVL-053")
def test_the_table_shows_each_metric_per_system_with_its_interval_and_case_count():
    naive = run("naive", {"a": {"false_answer_rate": 1.0}, "b": {"false_answer_rate": 1.0}})
    verified = run(
        "verified",
        {"a": {"false_answer_rate": 0.0, "shown_citation_validity": 1.0}, "b": {}},
    )

    table = trust_table(
        {"Naive RAG": naive, "Soundline": verified},
        ["false_answer_rate", "shown_citation_validity"],
    )

    assert table.splitlines() == [
        "| Metric | Naive RAG | Soundline |",
        "|---|---|---|",
        "| `false_answer_rate` | 1.00 [1.00, 1.00] n=2 | 0.00 [0.00, 0.00] n=1 |",
        "| `shown_citation_validity` | n/a | 1.00 [1.00, 1.00] n=1 |",
    ]
