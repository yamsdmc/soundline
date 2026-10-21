import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from soundline.interfaces.cli import app
from soundline.testing import ScriptedLanguageModel

type Run = Callable[..., Result]


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Run:
    monkeypatch.setenv("SOUNDLINE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SOUNDLINE_EMBEDDER", "hashing:256")  # offline and deterministic
    runner = CliRunner()

    def invoke(*args: str) -> Result:
        return runner.invoke(app, list(args))

    return invoke


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "lease.md").write_text("# Lease\n\n## Payment\n\nRent is due on the 5th.")
    (folder / "rules.md").write_text("Pets are allowed.")
    return folder


@pytest.mark.spec("CLI-002", "RET-004")
def test_search_json_prints_exactly_one_json_document(run: Run, docs: Path):
    assert run("ingest", str(docs)).exit_code == 0

    result = run("search", "rent due", "--json", "-k", "1")

    assert result.exit_code == 0
    hits = json.loads(result.stdout)["hits"]
    assert len(hits) == 1
    assert hits[0]["source"].endswith("lease.md")
    assert hits[0]["section_path"] == ["Lease", "Payment"]
    assert set(hits[0]["ranks"]) == {"lexical", "dense"}


@pytest.mark.spec("ING-081", "CLI-002")
def test_ingest_json_reports_every_source(run: Run, docs: Path):
    result = run("ingest", str(docs), "--json")

    report = json.loads(result.stdout)
    assert sorted(r["status"] for r in report["results"]) == ["added", "added"]


@pytest.mark.spec("CLI-001")
def test_a_partial_ingestion_exits_with_code_5(run: Run, docs: Path):
    (docs / "broken.txt").write_bytes(b"\xff\xfe")

    result = run("ingest", str(docs))

    assert result.exit_code == 5
    assert "not_utf8" in result.stdout


@pytest.mark.spec("CLI-001", "RET-043")
def test_a_malformed_filter_is_a_usage_error(run: Run, docs: Path):
    run("ingest", str(docs))

    result = run("search", "rent", "--filter", '{"like": ["type", "x"]}')

    assert result.exit_code == 2
    assert "invalid_filter" in result.output


@pytest.mark.spec("CLI-001", "STO-010")
def test_a_pipeline_mismatch_is_a_configuration_error(
    run: Run, docs: Path, monkeypatch: pytest.MonkeyPatch
):
    run("ingest", str(docs))
    monkeypatch.setenv("SOUNDLINE_EMBEDDER", "hashing:128")

    result = run("search", "rent")

    assert result.exit_code == 3
    assert "rebuild the index" in result.output


@pytest.mark.spec("STO-004")
def test_inspect_manifest_shows_how_the_index_was_built(run: Run, docs: Path):
    run("ingest", str(docs))

    result = run("inspect", "manifest", "--json")

    manifest = json.loads(result.stdout)
    assert manifest["embedder"] == {
        "model_id": "hashing:256",
        "dimension": 256,
        "max_input_tokens": 8192,
    }


@pytest.mark.spec("ING-011")
def test_sync_deletes_vanished_files(run: Run, docs: Path):
    run("ingest", str(docs))
    (docs / "rules.md").unlink()

    result = run("sync", str(docs), "--json")

    statuses = {Path(r["source"]).name: r["status"] for r in json.loads(result.stdout)["results"]}
    assert statuses == {"lease.md": "unchanged", "rules.md": "deleted"}


@pytest.mark.spec("CLI-005", "ARC-014")
def test_doctor_checks_each_component_with_a_real_call(run: Run, docs: Path):
    run("ingest", str(docs))

    result = run("doctor", "--json")

    assert result.exit_code == 0
    checks = {check["name"]: check for check in json.loads(result.stdout)["checks"]}
    assert set(checks) >= {"sqlite", "embedder", "index"}
    assert all(check["ok"] for check in checks.values())
    assert "sqlite-vec v" in checks["sqlite"]["detail"]
    assert "2 documents" in checks["index"]["detail"]


@pytest.mark.spec("CLI-005", "STO-010")
def test_doctor_reports_an_incompatible_index_with_the_fix(
    run: Run, docs: Path, monkeypatch: pytest.MonkeyPatch
):
    run("ingest", str(docs))
    monkeypatch.setenv("SOUNDLINE_EMBEDDER", "hashing:128")

    result = run("doctor")

    assert result.exit_code == 3
    assert "rebuild the index" in result.output


def test_init_creates_the_home_and_says_what_to_do_next(run: Run, tmp_path: Path):
    result = run("init")

    assert result.exit_code == 0
    assert (tmp_path / "home").is_dir()
    assert "soundline ingest" in result.output
    assert run("init").exit_code == 0  # idempotent


@pytest.mark.spec("ING-080", "CLI-001")
def test_ingesting_a_path_that_does_not_exist_is_reported_and_fails(run: Run, tmp_path: Path):
    result = run("ingest", str(tmp_path / "typo"))

    assert result.exit_code == 5
    assert "not_found" in result.stdout


@pytest.mark.spec("CLI-001")
def test_evaluating_a_dataset_that_does_not_exist_is_a_clean_usage_error(run: Run, tmp_path: Path):
    result = run("eval", "run", str(tmp_path / "missing.jsonl"))

    assert result.exit_code == 2
    assert "Traceback" not in result.output
    assert "missing.jsonl" in result.output


@pytest.mark.spec("CLI-004")
def test_asking_without_a_language_model_explains_how_to_configure_one(run: Run, docs: Path):
    run("ingest", str(docs))

    result = run("ask", "When is rent due?")

    assert result.exit_code == 3
    assert "SOUNDLINE_LLM" in result.output


@pytest.mark.spec("GEN-042", "GEN-034")
def test_ask_prints_the_answer_its_citations_and_what_was_dropped(
    run: Run, docs: Path, monkeypatch: pytest.MonkeyPatch
):
    scripted = ScriptedLanguageModel(
        {
            "claims": [
                {
                    "text": "Rent is due on the 5th.",
                    "citations": [{"evidence_id": "E1", "quote": "Rent is due on the 5th"}],
                },
                {
                    "text": "Parking is free.",
                    "citations": [{"evidence_id": "E1", "quote": "Parking is free"}],
                },
            ]
        }
    )
    monkeypatch.setenv("SOUNDLINE_LLM", "scripted:test")

    def scripted_llm(spec: str) -> ScriptedLanguageModel:
        return scripted

    monkeypatch.setattr("soundline.interfaces.cli.llm_from_spec", scripted_llm)
    run("ingest", str(docs))

    result = run("ask", "rent due 5th")

    assert result.exit_code == 0, result.output
    assert "Rent is due on the 5th [1]." in result.stdout
    assert '[1] lease.md, Lease > Payment: "Rent is due on the 5th"' in result.stdout
    assert "partial" in result.stdout
    assert "Parking is free." in result.stdout


@pytest.mark.spec("OBS-004")
def test_search_explain_shows_each_step_with_its_duration(run: Run, docs: Path):
    run("ingest", str(docs))

    result = run("search", "rent", "--explain")

    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    tree = lines[
        lines.index(next(line for line in lines if line.startswith("soundline.search ["))) :
    ]
    assert [line.split(" [")[0] for line in tree[:5]] == [
        "soundline.search",
        "├─ embed query",
        "├─ lexical",
        "├─ dense",
        "└─ fuse",
    ]
    assert "hits=" in tree[2]


@pytest.mark.spec("GEN-014")
def test_ask_uses_the_prompt_directory_named_by_soundline_prompt(
    run: Run, docs: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    prompt = tmp_path / "house-v1"
    prompt.mkdir()
    (prompt / "system.txt").write_text("House rules.")
    (prompt / "user.txt").write_text("$evidence\n$question\n$language_instruction")
    scripted = ScriptedLanguageModel({"claims": [], "insufficient_evidence": "unclear"})
    monkeypatch.setenv("SOUNDLINE_LLM", "scripted:test")
    monkeypatch.setenv("SOUNDLINE_PROMPT", str(prompt))

    def scripted_llm(spec: str) -> ScriptedLanguageModel:
        return scripted

    monkeypatch.setattr("soundline.interfaces.cli.llm_from_spec", scripted_llm)
    run("ingest", str(docs))

    result = run("ask", "rent due 5th")

    assert result.exit_code == 0, result.output
    assert scripted.requests[0].system == "House rules."


@pytest.mark.spec("GEN-014", "API-003")
def test_an_invalid_prompt_directory_is_a_configuration_error(
    run: Run, docs: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("SOUNDLINE_LLM", "scripted:test")
    monkeypatch.setenv("SOUNDLINE_PROMPT", str(tmp_path / "missing"))

    def scripted_llm(spec: str) -> ScriptedLanguageModel:
        return ScriptedLanguageModel()

    monkeypatch.setattr("soundline.interfaces.cli.llm_from_spec", scripted_llm)

    result = run("ask", "rent due 5th")

    assert result.exit_code == 3
    assert "prompt template" in result.stderr
