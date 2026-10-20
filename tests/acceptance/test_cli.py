import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from soundline.interfaces.cli import app

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
    assert "reindex" in result.output


@pytest.mark.spec("STO-004")
def test_inspect_manifest_shows_how_the_index_was_built(run: Run, docs: Path):
    run("ingest", str(docs))

    result = run("inspect", "manifest", "--json")

    manifest = json.loads(result.stdout)
    assert manifest["embedder"] == {"model_id": "hashing:256", "dimension": 256}


@pytest.mark.spec("ING-011")
def test_sync_deletes_vanished_files(run: Run, docs: Path):
    run("ingest", str(docs))
    (docs / "rules.md").unlink()

    result = run("sync", str(docs), "--json")

    statuses = {Path(r["source"]).name: r["status"] for r in json.loads(result.stdout)["results"]}
    assert statuses == {"lease.md": "unchanged", "rules.md": "deleted"}
