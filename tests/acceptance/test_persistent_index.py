from pathlib import Path

import pytest

from soundline import IndexMismatchError, IngestionStatus, Soundline
from soundline.application.ports import Vector
from soundline.domain.chunking import ChunkingSettings
from soundline.testing import HashingEmbedder, ScriptedLanguageModel


def open_index(
    home: Path, embedder: HashingEmbedder | None = None, max_tokens: int = 384
) -> Soundline:
    return Soundline.open(
        home,
        llm=ScriptedLanguageModel(),
        embedder=embedder or HashingEmbedder(),
        chunking=ChunkingSettings(max_tokens=max_tokens),
    )


@pytest.mark.spec("ING-007", "STO-040")
def test_an_index_survives_closing_and_reopening(tmp_path: Path):
    with open_index(tmp_path) as soundline:
        soundline.ingest_text("lease.md", "Rent is due on the 5th.")

    with open_index(tmp_path) as reopened:
        assert [hit.source for hit in reopened.search("rent")] == ["lease.md"]
        status = reopened.ingest_text("lease.md", "Rent is due on the 5th.")
        assert status is IngestionStatus.UNCHANGED


@pytest.mark.spec("STO-001", "STO-010", "STO-012")
@pytest.mark.parametrize(
    "changed",
    [
        {"embedder": HashingEmbedder(dimension=128)},
        {"embedder": HashingEmbedder(synonyms={"pay": "payable"})},
        {"max_tokens": 128},
    ],
    ids=["embedder-dimension", "embedder-model", "chunking"],
)
def test_an_index_refuses_a_pipeline_it_was_not_built_with(
    tmp_path: Path, changed: dict[str, object]
):
    with open_index(tmp_path) as soundline:
        soundline.ingest_text("lease.md", "Rent is due on the 5th.")

    with open_index(tmp_path, **changed) as mismatched:  # pyright: ignore[reportArgumentType]
        with pytest.raises(IndexMismatchError, match="rebuild the index"):
            mismatched.ingest_text("rules.md", "No smoking.")
        with pytest.raises(IndexMismatchError):
            mismatched.search("rent")


@pytest.mark.spec("STO-002")
def test_query_time_settings_are_not_part_of_the_pipeline(tmp_path: Path):
    with open_index(tmp_path) as soundline:
        soundline.ingest_text("lease.md", "Rent is due on the 5th.")

    with open_index(tmp_path) as reopened:
        assert len(reopened.search("rent", k=1)) == 1


class FailingAfterFirstVector(HashingEmbedder):
    """Returns a malformed vector for the second text, so that writing it fails midway."""

    def embed_documents(self, texts: list[str]) -> list[Vector]:  # type: ignore[override]
        vectors = super().embed_documents(texts)
        return [vectors[0], *[vector[:-1] for vector in vectors[1:]]]


@pytest.mark.spec("STO-020", "STO-021", "ING-082")
def test_a_failure_while_replacing_a_document_leaves_the_previous_revision_intact(
    tmp_path: Path,
):
    with open_index(tmp_path, max_tokens=4) as soundline:
        soundline.ingest_text("lease.md", "Rent is due on the 5th.")

    two_chunks = "Rent is due on the 10th.\n\nPets are allowed in the garden."
    with (
        open_index(tmp_path, FailingAfterFirstVector(), max_tokens=4) as failing,
        pytest.raises(ValueError, match="dimension"),
    ):
        failing.ingest_text("lease.md", two_chunks)

    with open_index(tmp_path, max_tokens=4) as reopened:
        assert reopened.document_text("lease.md") == "Rent is due on the 5th."
        assert {hit.text for hit in reopened.search("rent due")} == {"Rent is due on", "the 5th."}
