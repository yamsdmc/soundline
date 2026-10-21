import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from soundline import Soundline
from soundline.domain.usage import TokenUsage
from soundline.testing import ScriptedLanguageModel

LEASE = "Rent is due on the 5th. Late fees are 10 euros per day."
CASES: list[dict[str, object]] = [
    {
        "id": "rent-due",
        "question": "When is rent due?",
        "relevant": [{"source": "lease.md", "quote": "Rent is due on the 5th."}],
    },
    {"id": "parking", "question": "Is parking free?", "answerable": False, "relevant": []},
]


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    path = tmp_path / "lease.jsonl"
    path.write_text("\n".join(json.dumps(case) for case in CASES))
    return path


def scripted() -> ScriptedLanguageModel:
    return ScriptedLanguageModel(
        {
            "claims": [
                {
                    "text": "Rent is due on the 5th.",
                    "citations": [{"evidence_id": "E1", "quote": "Rent is due on the 5th"}],
                }
            ],
            "insufficient_evidence": None,
        },
        {"claims": [], "insufficient_evidence": "The lease says nothing about parking."},
        usage=TokenUsage(input=1000, output=50),
        model_id="ollama:test",
    )


@pytest.mark.spec("EVL-060", "EVL-020", "EVL-030")
def test_an_end_to_end_run_scores_answers_retrieval_and_operations(dataset: Path):
    llm = scripted()
    soundline = Soundline.in_memory(llm=llm)
    soundline.ingest_text("lease.md", LEASE)

    run = soundline.evaluate(dataset, "e2e")

    assert run.settings["mode"] == "end-to-end"
    assert run.settings["model"] == "ollama:test"
    assert run.settings["prompt_version"] == "grounded-v3"
    assert run.per_case["rent-due"]["citation_recall"] == 1.0
    assert run.per_case["rent-due"]["hit_rate@1"] == 1.0
    assert run.per_case["parking"]["false_answer_rate"] == 0.0
    assert run.per_case["parking"]["tokens_in"] == 1000
    assert run.per_case["parking"]["cost_usd"] == 0.0  # local model
    assert run.metrics["answer_rate"].mean == 1.0
    assert run.metrics["false_answer_rate"].cases == 1
    assert set(run.operations["latency_ms"]) == {"mean", "p50", "p95", "total"}
    assert run.operations["tokens_in"]["total"] == 2000
    assert soundline.load_run("e2e") == run


@pytest.mark.spec("EVL-062", "EVL-010")
def test_a_retrieval_only_run_never_calls_the_model(dataset: Path):
    llm = ScriptedLanguageModel()
    soundline = Soundline.in_memory(llm=llm)
    soundline.ingest_text("lease.md", LEASE)

    run = soundline.evaluate(dataset, retrieval_only=True)

    assert run.settings["mode"] == "retrieval-only"
    assert llm.requests == []
    assert "parking" not in run.per_case


def without_latency(run_cases: Mapping[str, Mapping[str, float]]) -> dict[str, dict[str, float]]:
    return {
        case: {k: v for k, v in metrics.items() if k != "latency_ms"}
        for case, metrics in run_cases.items()
    }


@pytest.mark.spec("EVL-061")
def test_rerunning_with_a_warm_cache_reproduces_the_run_at_zero_model_cost(dataset: Path):
    llm = scripted()  # two scripted answers: a third model call would fail the test
    soundline = Soundline.in_memory(llm=llm)
    soundline.ingest_text("lease.md", LEASE)

    first = soundline.evaluate(dataset, "first")
    second = soundline.evaluate(dataset, "second")

    assert len(llm.requests) == 2
    assert without_latency(second.per_case) == without_latency(first.per_case)


@pytest.mark.spec("EVL-061")
def test_no_cache_forces_fresh_model_calls(dataset: Path):
    first, second = scripted(), scripted()
    responses = [*first._responses, *second._responses]  # pyright: ignore[reportPrivateUsage]
    llm = ScriptedLanguageModel(*responses, model_id="ollama:test")
    soundline = Soundline.in_memory(llm=llm)
    soundline.ingest_text("lease.md", LEASE)

    soundline.evaluate(dataset)
    soundline.evaluate(dataset, no_cache=True)

    assert len(llm.requests) == 4
