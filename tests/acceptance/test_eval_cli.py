import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from soundline.interfaces.cli import app

type Run = Callable[..., Result]

TOPICS = [
    ("rent", "Rent is due on the fifth day of each month."),
    ("deposit", "The security deposit equals two months of rent."),
    ("pets", "Cats and small dogs are welcome in the flat."),
    ("noise", "Quiet hours start at ten in the evening."),
    ("keys", "Lost keys are replaced by the agency for a fee."),
    ("heating", "Central heating runs from October to April."),
    ("parking", "Each tenant gets one parking space in the basement."),
    ("trash", "Recycling bins are collected every Tuesday morning."),
    ("repairs", "Urgent repairs must be reported within two days."),
    ("garden", "The shared garden closes at sunset every day."),
    ("laundry", "The laundry room opens from eight to eight."),
    ("visits", "The landlord announces visits one week in advance."),
]


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    folder = tmp_path / "corpus"
    folder.mkdir()
    for name, sentence in TOPICS:
        (folder / f"{name}.md").write_text(f"# {name.title()}\n\n{sentence}")
    return folder


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    path = tmp_path / "lease.jsonl"
    cases = [
        {
            "id": name,
            "question": sentence.split()[1] + " " + sentence.split()[-1].rstrip("."),
            "relevant": [{"source": f"{name}.md", "quote": sentence}],
        }
        for name, sentence in TOPICS
    ]
    path.write_text("\n".join(json.dumps(case) for case in cases))
    return path


def runner_for(home: Path, monkeypatch: pytest.MonkeyPatch) -> Run:
    monkeypatch.setenv("SOUNDLINE_HOME", str(home))
    monkeypatch.setenv("SOUNDLINE_EMBEDDER", "hashing:256")
    runner = CliRunner()

    def invoke(*args: str) -> Result:
        return runner.invoke(app, list(args))

    return invoke


@pytest.mark.spec("EVL-060", "EVL-062", "EVL-065", "EVL-050")
def test_eval_run_stores_a_reproducible_run_with_intervals(
    tmp_path: Path, corpus: Path, dataset: Path, monkeypatch: pytest.MonkeyPatch
):
    run = runner_for(tmp_path / "home", monkeypatch)
    run("ingest", str(corpus))

    result = run("eval", "run", str(dataset), "--name", "baseline", "--json")

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["name"] == "baseline"
    assert report["cases"] == 12
    recall = report["metrics"]["recall@5"]
    assert recall["low"] <= recall["mean"] <= recall["high"]
    assert len(report["dataset"]["sha256"]) == 64
    assert report["index"]["fingerprint"]
    assert (tmp_path / "home" / "evals" / "runs" / "baseline.json").is_file()


@pytest.mark.spec("EVL-063", "EVL-064", "INV-EVL-3")
def test_a_run_compared_with_itself_passes_the_gate(
    tmp_path: Path, corpus: Path, dataset: Path, monkeypatch: pytest.MonkeyPatch
):
    run = runner_for(tmp_path / "home", monkeypatch)
    run("ingest", str(corpus))
    run("eval", "run", str(dataset), "--name", "a")
    run("eval", "run", str(dataset), "--name", "b")
    rules = tmp_path / "gates.toml"
    rules.write_text('[[rule]]\nmetric = "recall@5"\nmax_regression = 0.02\n')

    compare = run("eval", "compare", "a", "b", "--format", "md")
    gate = run("eval", "gate", "b", "--baseline", "a", "--rules", str(rules))

    assert compare.exit_code == 0
    assert "| recall@5 |" in compare.stdout
    assert "no significant change" in compare.stdout
    assert gate.exit_code == 0, gate.output


@pytest.mark.spec("EVL-052", "EVL-064")
def test_the_gate_fails_on_a_significant_regression(
    tmp_path: Path, corpus: Path, dataset: Path, monkeypatch: pytest.MonkeyPatch
):
    good = runner_for(tmp_path / "good", monkeypatch)
    good("ingest", str(corpus))
    good("eval", "run", str(dataset), "--name", "main")
    baseline = tmp_path / "good" / "evals" / "runs" / "main.json"

    half = tmp_path / "half"
    half.mkdir()
    for name, _ in TOPICS[:6]:
        (half / f"{name}.md").write_bytes((corpus / f"{name}.md").read_bytes())
    worse = runner_for(tmp_path / "worse", monkeypatch)
    worse("ingest", str(half))
    rules = tmp_path / "gates.toml"
    rules.write_text('[[rule]]\nmetric = "recall@5"\nmax_regression = 0.02\n')

    worse("eval", "run", str(dataset), "--name", "pr", "--allow-missing-sources")
    gate = worse("eval", "gate", "pr", "--baseline", str(baseline), "--rules", str(rules))

    assert gate.exit_code == 1
    assert "recall@5" in gate.output
    assert "regressed" in gate.output


@pytest.mark.spec("EVL-002", "CLI-001")
def test_an_invalid_dataset_is_a_usage_error(
    tmp_path: Path, corpus: Path, monkeypatch: pytest.MonkeyPatch
):
    run = runner_for(tmp_path / "home", monkeypatch)
    run("ingest", str(corpus))
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        json.dumps(
            {
                "id": "x",
                "question": "?",
                "relevant": [{"source": "rent.md", "quote": "Rent is due on the 6th"}],
            }
        )
    )

    result = run("eval", "run", str(bad))

    assert result.exit_code == 2
    assert "closest" in result.output
