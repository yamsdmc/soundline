import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from soundline.interfaces.cli import app
from soundline.testing import ScriptedLanguageModel

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


def abstaining_model() -> ScriptedLanguageModel:
    answer: dict[str, object] = {"claims": [], "insufficient_evidence": "not in the lease"}
    return ScriptedLanguageModel(*[answer] * len(TOPICS))


@pytest.mark.spec("EVL-060", "EVL-030", "EVL-053")
def test_with_a_language_model_eval_run_is_end_to_end_and_reports_operations(
    tmp_path: Path, corpus: Path, dataset: Path, monkeypatch: pytest.MonkeyPatch
):
    run = runner_for(tmp_path / "home", monkeypatch)
    run("ingest", str(corpus))
    monkeypatch.setenv("SOUNDLINE_LLM", "scripted:test")
    model = abstaining_model()

    def scripted_llm(spec: str) -> ScriptedLanguageModel:
        return model

    monkeypatch.setattr("soundline.interfaces.cli.llm_from_spec", scripted_llm)

    result = run("eval", "run", str(dataset))

    assert result.exit_code == 0, result.output
    assert "end-to-end" in result.stdout
    assert "answer_rate" in result.stdout
    assert "n=12" in result.stdout
    assert "latency_ms" in result.stdout
    assert len(model.requests) == 12


@pytest.mark.spec("EVL-062")
def test_retrieval_only_skips_the_configured_language_model(
    tmp_path: Path, corpus: Path, dataset: Path, monkeypatch: pytest.MonkeyPatch
):
    run = runner_for(tmp_path / "home", monkeypatch)
    run("ingest", str(corpus))
    monkeypatch.setenv("SOUNDLINE_LLM", "scripted:test")
    model = ScriptedLanguageModel()

    def scripted_llm(spec: str) -> ScriptedLanguageModel:
        return model

    monkeypatch.setattr("soundline.interfaces.cli.llm_from_spec", scripted_llm)

    result = run("eval", "run", str(dataset), "--retrieval-only")

    assert result.exit_code == 0, result.output
    assert "retrieval-only" in result.stdout
    assert model.requests == []


@pytest.mark.spec("EVL-021")
def test_a_judge_model_is_enabled_explicitly_on_the_command_line(
    tmp_path: Path, corpus: Path, dataset: Path, monkeypatch: pytest.MonkeyPatch
):
    run = runner_for(tmp_path / "home", monkeypatch)
    run("ingest", str(corpus))
    monkeypatch.setenv("SOUNDLINE_LLM", "scripted:generator")
    models = {"scripted:generator": abstaining_model(), "scripted:judge": ScriptedLanguageModel()}

    def scripted_llm(spec: str) -> ScriptedLanguageModel:
        return models[spec]

    monkeypatch.setattr("soundline.interfaces.cli.llm_from_spec", scripted_llm)

    result = run("eval", "run", str(dataset), "--judge", "scripted:judge", "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["settings"]["judge"]["version"] == "faithfulness-v2"


@pytest.mark.spec("EVL-042", "EVL-043")
def test_the_report_names_the_judge_its_calibration_and_the_warnings(
    tmp_path: Path, corpus: Path, dataset: Path, monkeypatch: pytest.MonkeyPatch
):
    run = runner_for(tmp_path / "home", monkeypatch)
    run("ingest", str(corpus))
    monkeypatch.setenv("SOUNDLINE_LLM", "scripted:same")
    models = {"scripted:same": abstaining_model()}

    def scripted_llm(spec: str) -> ScriptedLanguageModel:
        return models.get(spec) or ScriptedLanguageModel(model_id="scripted:test")

    monkeypatch.setattr("soundline.interfaces.cli.llm_from_spec", scripted_llm)

    result = run("eval", "run", str(dataset), "--judge", "scripted:same")

    assert "judge scripted:test (faithfulness-v2, uncalibrated)" in result.stdout
    assert "warning: the judge is the same model" in result.stdout


def answering_model() -> ScriptedLanguageModel:
    answers: list[dict[str, object]] = [
        {
            "claims": [
                {"text": sentence, "citations": [{"evidence_id": "E1", "quote": sentence[:-1]}]}
            ],
            "insufficient_evidence": None,
        }
        for _, sentence in TOPICS
    ]
    return ScriptedLanguageModel(*answers, model_id="scripted:generator")


@pytest.mark.spec("EVL-043")
def test_labels_exported_from_a_judged_run_calibrate_the_judge_for_later_runs(
    tmp_path: Path, corpus: Path, dataset: Path, monkeypatch: pytest.MonkeyPatch
):
    run = runner_for(tmp_path / "home", monkeypatch)
    run("ingest", str(corpus))
    monkeypatch.setenv("SOUNDLINE_LLM", "scripted:generator")
    verdict: dict[str, object] = {"rationale": "states it", "entailed": True}
    models = {
        "scripted:generator": answering_model(),
        "scripted:judge": ScriptedLanguageModel(*[verdict] * 50, model_id="scripted:judge"),
    }

    def scripted_llm(spec: str) -> ScriptedLanguageModel:
        return models[spec]

    monkeypatch.setattr("soundline.interfaces.cli.llm_from_spec", scripted_llm)
    run("eval", "run", str(dataset), "--name", "judged", "--judge", "scripted:judge")
    labels = tmp_path / "labels.jsonl"

    exported = run("eval", "labels", "judged", "--output", str(labels))
    calibrated = run("eval", "calibrate", str(labels), "--judge", "scripted:judge")
    later = run("eval", "run", str(dataset), "--judge", "scripted:judge")

    assert exported.exit_code == 0, exported.output
    assert len(labels.read_text().splitlines()) == len(TOPICS)
    assert calibrated.exit_code == 0, calibrated.output
    assert "accuracy 1.000" in calibrated.stdout
    assert f"{len(TOPICS)} labels not reviewed" in calibrated.stdout
    assert "calibrated: kappa" in later.stdout
