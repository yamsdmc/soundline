from collections.abc import Sequence

import pytest

from soundline import IngestionStatus, Soundline
from soundline.application.ports import Vector
from soundline.testing import HashingEmbedder, ScriptedLanguageModel


class CountingEmbedder(HashingEmbedder):
    def __init__(self) -> None:
        super().__init__()
        self.embedded_texts = 0

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        self.embedded_texts += len(texts)
        return super().embed_documents(texts)


@pytest.fixture
def embedder() -> CountingEmbedder:
    return CountingEmbedder()


@pytest.fixture
def soundline(embedder: CountingEmbedder) -> Soundline:
    return Soundline.in_memory(llm=ScriptedLanguageModel(), embedder=embedder)


@pytest.mark.spec("ING-007")
def test_reingesting_an_unchanged_document_is_a_noop(
    soundline: Soundline, embedder: CountingEmbedder
):
    assert soundline.ingest_text("lease.md", "Rent is due on the 5th.") is IngestionStatus.ADDED
    embedded_after_first_ingestion = embedder.embedded_texts

    status = soundline.ingest_text("lease.md", "Rent is due on the 5th.")

    assert status is IngestionStatus.UNCHANGED
    assert embedder.embedded_texts == embedded_after_first_ingestion
    assert len(soundline.search("rent")) == 1


@pytest.mark.spec("ING-009")
def test_reingesting_a_changed_document_replaces_all_of_its_chunks(soundline: Soundline):
    soundline.ingest_text("lease.md", "Rent is due on the 5th.")

    status = soundline.ingest_text("lease.md", "Rent is due on the 10th.")

    assert status is IngestionStatus.UPDATED
    assert [hit.text for hit in soundline.search("rent due")] == ["Rent is due on the 10th."]
    assert soundline.document_text("lease.md") == "Rent is due on the 10th."


@pytest.mark.spec("ING-008", "ING-009")
def test_documents_from_other_sources_are_left_untouched(soundline: Soundline):
    soundline.ingest_text("lease.md", "Rent is due on the 5th.")
    soundline.ingest_text("rules.md", "Rent payments go to the agency.")

    soundline.ingest_text("lease.md", "Rent is due on the 10th.")

    assert sorted(hit.source for hit in soundline.search("rent")) == ["lease.md", "rules.md"]
