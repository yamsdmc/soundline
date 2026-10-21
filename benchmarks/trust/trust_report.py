"""The trust benchmark report (EVL-092): one table, every metric with its interval.

Usage: uv run python benchmarks/trust/trust_report.py --home H --dataset D \
    --naive-answers A --model M --judge J --output results.md
"""

import argparse
import json
import platform
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from naive_scoring import naive_run

from soundline.adapters.evals.json_files import JsonGenerationCache, JsonRunStore
from soundline.api import llm_from_spec
from soundline.application.cached_model import CachedLanguageModel
from soundline.application.evaluate import DatasetFile
from soundline.application.judges import FaithfulnessJudge
from soundline.domain.runs import EvalRun, comparison_markdown

METRICS = (
    "false_answer_rate",
    "injection_success_rate",
    "unflagged_injection_rate",
    "answer_rate",
    "faithfulness",
    "shown_citation_validity",
    "shown_support_rate",
    "citation_validity",
    "citation_recall",
    "abstention_precision",
    "conflict_rate",
)
OPERATIONS = ("latency_ms", "tokens_in", "tokens_out")


def trust_table(runs: Mapping[str, EvalRun], metrics: Sequence[str]) -> str:
    """Mean [95% CI] n=cases per system; n/a where a metric does not apply (EVL-053)."""
    lines = [f"| Metric | {' | '.join(runs)} |", f"|---{'|---' * len(runs)}|"]
    for metric in metrics:
        cells: list[str] = []
        for run in runs.values():
            estimate = run.metrics.get(metric)
            cells.append(
                f"{estimate.mean:.2f} [{estimate.low:.2f}, {estimate.high:.2f}] n={estimate.cases}"
                if estimate
                else "n/a"
            )
        lines.append(f"| `{metric}` | {' | '.join(cells)} |")
    return "\n".join(lines)


def operations_table(runs: Mapping[str, EvalRun]) -> str:
    lines = [f"| Per question (p50 / p95) | {' | '.join(runs)} |", f"|---{'|---' * len(runs)}|"]
    for metric in OPERATIONS:
        cells = [
            f"{run.operations[metric]['p50']:,.0f} / {run.operations[metric]['p95']:,.0f}"
            if metric in run.operations
            else "n/a"
            for run in runs.values()
        ]
        lines.append(f"| `{metric}` | {' | '.join(cells)} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    for option in ("--home", "--dataset", "--naive-answers", "--output"):
        parser.add_argument(option, type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--judge", required=True)
    args = parser.parse_args()

    store = JsonRunStore(args.home / "evals" / "runs")
    cache = JsonGenerationCache(args.home / "cache" / "generations")
    judge = FaithfulnessJudge(CachedLanguageModel(llm_from_spec(args.judge), cache))
    lines = args.naive_answers.read_text(encoding="utf-8").splitlines()
    records = {record["id"]: record for record in map(json.loads, lines)}
    verified = store.load("soundline-verified")
    dataset = DatasetFile(str(args.dataset), args.dataset.read_text(encoding="utf-8"))
    naive = naive_run(
        "naive-langchain",
        dataset,
        records,
        {"model": f"ollama:{args.model}", "judge": verified.settings.get("judge")},
        judge,
    )
    store.save(naive)
    runs = {
        "Naive RAG (LangChain)": naive,
        "Soundline, verification off": store.load("soundline-unverified"),
        "Soundline": verified,
    }
    judged = verified.settings.get("judge")
    report = [
        "# Trust benchmark results",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d} on {platform.machine()} ({platform.system()}),"
        f" model `ollama:{args.model}`, judge {json.dumps(judged)},"
        f" dataset `{args.dataset}` ({verified.dataset.get('cases')} cases,"
        f" sha256 `{str(verified.dataset.get('sha256'))[:12]}`).",
        "",
        trust_table(runs, METRICS),
        "",
        operations_table(runs),
        "",
        "## Paired comparisons",
        "",
        comparison_markdown(runs["Soundline, verification off"], verified),
        "",
        comparison_markdown(naive, verified),
        "",
    ]
    args.output.write_text("\n".join(report), encoding="utf-8")
    print(args.output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
