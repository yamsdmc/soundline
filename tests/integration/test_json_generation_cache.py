from pathlib import Path

import pytest

from soundline.adapters.evals.json_files import JsonGenerationCache, JsonRunStore
from soundline.application.ports import Generation
from soundline.domain.calibration import Calibration, agreement
from soundline.domain.usage import TokenUsage


@pytest.mark.spec("EVL-061")
def test_cached_generations_survive_the_process(tmp_path: Path):
    generation = Generation(
        '{"claims": []}', TokenUsage(input=5, output=1, cache_read=3), latency_ms=812.5
    )
    JsonGenerationCache(tmp_path).put("a" * 64, generation)

    reopened = JsonGenerationCache(tmp_path)

    assert reopened.get("a" * 64) == generation
    assert reopened.get("b" * 64) is None


@pytest.mark.spec("EVL-043")
def test_a_calibration_is_stored_per_judge_model_and_version(tmp_path: Path):
    store = JsonRunStore(tmp_path / "runs")
    calibration = Calibration(
        "anthropic:claude-opus-5-5", "faithfulness-v2", agreement([(True, True)]), 0, "now"
    )

    store.save_calibration(calibration)

    reopened = JsonRunStore(tmp_path / "runs")
    assert reopened.calibration("anthropic:claude-opus-5-5", "faithfulness-v2") == calibration
    assert reopened.calibration("anthropic:claude-opus-5-5", "faithfulness-v1") is None
