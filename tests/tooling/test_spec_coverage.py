from pathlib import Path

import pytest

from spec_coverage import (
    coverage_report,
    defined_behaviors,
    main,
    optional_behaviors,
    referenced_behaviors,
)


def test_a_bold_behavior_id_in_a_spec_line_is_a_defined_behavior():
    markdown = "- **ING-007** Re-ingesting a source whose bytes are unchanged MUST be a no-op."

    assert set(defined_behaviors(markdown)) == {"ING-007"}


def test_ids_merely_referenced_in_prose_are_not_definitions():
    markdown = (
        "- **RET-020** Dense retrieval MUST embed the query (see STO-012).\n"
        "- **RET-021** Similarity is cosine similarity.\n"
    )

    assert set(defined_behaviors(markdown)) == {"RET-020", "RET-021"}


def test_a_behavior_stated_only_with_may_is_optional():
    markdown = (
        "- **RET-033** An alternative fusion MAY be selected by configuration.\n"
        "- **RET-034** If one retriever fails, search MUST continue in degraded mode.\n"
    )

    assert optional_behaviors(markdown) == {"RET-033"}


def test_behaviors_referenced_by_spec_markers_are_collected_from_test_source():
    source = (
        "import pytest\n"
        "\n"
        '@pytest.mark.spec("ING-007", "ING-008")\n'
        "def test_reingesting_is_a_noop(): ...\n"
        "\n"
        'pytestmark = pytest.mark.spec("RET-001")\n'
    )

    assert referenced_behaviors(source) == {"ING-007", "ING-008", "RET-001"}


def test_ids_in_other_strings_of_a_test_are_not_references():
    source = (
        "import pytest\n"
        "\n"
        "def test_something():\n"
        '    assert error.code == "GEN-030"\n'
        '    pytest.mark.skip("ING-001")\n'
    )

    assert referenced_behaviors(source) == set()


SPEC = (
    "- **ING-001** Given a file path, Soundline MUST ingest that file.\n"
    "- **ING-002** Given a directory, Soundline MUST ingest all supported files.\n"
    "- **ING-003** Include and exclude glob patterns MAY be given.\n"
)


def test_report_separates_covered_uncovered_and_optional_behaviors():
    tests = ['@pytest.mark.spec("ING-001")\ndef test_x(): ...\n']

    report = coverage_report([SPEC], tests)

    assert report.covered == {"ING-001"}
    assert report.uncovered == {"ING-002"}
    assert report.optional_uncovered == {"ING-003"}
    assert report.unknown == set()


def test_report_flags_references_to_behaviors_that_do_not_exist():
    tests = ['@pytest.mark.spec("ING-001", "ING-999")\ndef test_x(): ...\n']

    report = coverage_report([SPEC], tests)

    assert report.unknown == {"ING-999"}


def test_cli_fails_only_when_a_test_references_an_unknown_behavior(tmp_path: Path):
    spec_dir, tests_dir = tmp_path / "spec", tmp_path / "tests"
    spec_dir.mkdir()
    tests_dir.mkdir()
    (spec_dir / "03-ingestion.md").write_text(SPEC)
    test_file = tests_dir / "test_ingestion.py"

    test_file.write_text('@pytest.mark.spec("ING-001")\ndef test_x(): ...\n')
    assert main([str(spec_dir), str(tests_dir)]) == 0

    test_file.write_text('@pytest.mark.spec("ING-999")\ndef test_x(): ...\n')
    assert main([str(spec_dir), str(tests_dir)]) == 1


def test_cli_reads_spec_markers_from_every_given_test_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    spec_dir, tests_dir, contracts_dir = tmp_path / "spec", tmp_path / "tests", tmp_path / "lib"
    for directory in (spec_dir, tests_dir, contracts_dir):
        directory.mkdir()
    (spec_dir / "03-ingestion.md").write_text(SPEC)
    (contracts_dir / "contracts.py").write_text('@pytest.mark.spec("ING-002")\ndef test_y(): ...\n')

    main([str(spec_dir), str(tests_dir), str(contracts_dir)])

    assert "covered:  1/2" in capsys.readouterr().out


def test_invariants_are_definitions_too():
    markdown = "- **INV-EVL-3** Comparing a run with itself yields zero differences."

    assert set(defined_behaviors(markdown)) == {"INV-EVL-3"}


def test_an_invariant_with_a_label_is_still_a_definition():
    markdown = "- **INV-ING-1 (span fidelity)** For every chunk c of document d: ..."

    assert set(defined_behaviors(markdown)) == {"INV-ING-1"}
