from pathlib import Path

import pytest

from soundline import IngestionStatus, Soundline
from soundline.testing import ScriptedLanguageModel


@pytest.fixture
def soundline() -> Soundline:
    return Soundline.in_memory(llm=ScriptedLanguageModel())


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    (tmp_path / "lease.md").write_text("# Lease\n\nRent is due on the 5th.")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "rules.txt").write_text("Rent goes to the agency.")
    (tmp_path / "photo.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / ".secret.md").write_text("Rent password is hunter2.")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD.md").write_text("Rent ref.")
    return tmp_path


def statuses(report: object) -> dict[str, IngestionStatus]:
    return {Path(r.source).name: r.status for r in report.results}  # type: ignore[attr-defined]


@pytest.mark.spec("ING-001", "ING-002", "ING-004", "ING-080")
def test_a_directory_is_ingested_recursively_and_unsupported_files_are_reported(
    soundline: Soundline, docs: Path
):
    report = soundline.ingest([docs])

    assert statuses(report) == {
        "lease.md": IngestionStatus.ADDED,
        "rules.txt": IngestionStatus.ADDED,
        "photo.png": IngestionStatus.SKIPPED,
    }
    assert sorted(Path(hit.source).name for hit in soundline.search("rent")) == [
        "lease.md",
        "rules.txt",
    ]


@pytest.mark.spec("ING-007")
def test_ingesting_the_same_directory_again_changes_nothing(soundline: Soundline, docs: Path):
    soundline.ingest([docs])

    report = soundline.ingest([docs])

    assert set(statuses(report).values()) == {IngestionStatus.UNCHANGED, IngestionStatus.SKIPPED}


@pytest.mark.spec("ING-030", "ING-080")
def test_a_file_that_cannot_be_read_fails_alone(soundline: Soundline, docs: Path):
    (docs / "broken.txt").write_bytes(b"Rent \xff\xfe is due")

    report = soundline.ingest([docs])

    broken = next(r for r in report.results if r.source.endswith("broken.txt"))
    assert broken.status is IngestionStatus.FAILED
    assert broken.reason == "not_utf8"
    assert statuses(report)["lease.md"] is IngestionStatus.ADDED


@pytest.mark.spec("ING-011")
def test_sync_deletes_documents_whose_files_disappeared_and_ingest_never_does(
    soundline: Soundline, docs: Path
):
    soundline.ingest([docs])
    (docs / "notes" / "rules.txt").unlink()

    soundline.ingest([docs])
    assert any(hit.source.endswith("rules.txt") for hit in soundline.search("agency"))

    report = soundline.sync([docs])

    assert statuses(report)["rules.txt"] is IngestionStatus.DELETED
    assert all(not hit.source.endswith("rules.txt") for hit in soundline.search("agency"))


@pytest.mark.spec("ING-011")
def test_sync_only_deletes_documents_under_the_synced_directories(soundline: Soundline, docs: Path):
    soundline.ingest_text("manual-note", "Rent memo typed by hand.")
    soundline.ingest([docs])

    soundline.sync([docs / "notes"])

    assert soundline.document_text("manual-note") == "Rent memo typed by hand."
    assert any(hit.source.endswith("lease.md") for hit in soundline.search("rent"))


@pytest.mark.spec("ING-006")
def test_symbolic_links_are_not_followed(
    soundline: Soundline, docs: Path, tmp_path_factory: pytest.TempPathFactory
):
    outside = tmp_path_factory.mktemp("outside")
    (outside / "private.md").write_text("Rent of the neighbours.")
    (docs / "link").symlink_to(outside, target_is_directory=True)

    report = soundline.ingest([docs])

    assert "private.md" not in statuses(report)
