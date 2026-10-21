import json

import pytest

from soundline.application.evaluate import DatasetFile, EvalSettings, Generator, run_eval
from soundline.domain.answers import AbstentionReason, Answer, AnswerStatus
from soundline.domain.usage import StageUsage, TokenUsage, Usage
from soundline.testing.in_memory_document_store import InMemoryDocumentStore

CASE: dict[str, object] = {
    "id": "parking",
    "question": "Is parking free?",
    "answerable": False,
    "relevant": [],
}


def cached_answer(question: str) -> Answer:
    stage = StageUsage("generation", "ollama:m", TokenUsage(), 0.0, latency_ms=500.0, cached=True)
    return Answer(
        AnswerStatus.ABSTAINED,
        abstention_reason=AbstentionReason.MODEL_INSUFFICIENT_EVIDENCE,
        usage=Usage((stage,)),
    )


@pytest.mark.spec("EVL-030", "EVL-061")
def test_latency_adds_back_the_original_time_of_cached_model_calls():
    readings = iter([1.000, 1.010])
    documents = InMemoryDocumentStore()

    run = run_eval(
        "r",
        DatasetFile("d.jsonl", json.dumps(CASE)),
        _Index(documents),  # type: ignore[arg-type]
        lambda text, k: [],
        EvalSettings(),
        generator=Generator(cached_answer, {"model": "ollama:m"}),
        clock=lambda: next(readings),
    )

    assert run.per_case["parking"]["latency_ms"] == pytest.approx(510.0)
    assert any("1 model call" in warning for warning in run.warnings)


class _Index:
    def __init__(self, documents: InMemoryDocumentStore) -> None:
        self.documents = documents
        self.manifest = _NoManifest()


class _NoManifest:
    def load(self) -> None:
        return None
