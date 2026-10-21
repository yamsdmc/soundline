from pathlib import Path

import pytest

from soundline.adapters.evals.json_files import JsonGenerationCache
from soundline.application.ports import Generation
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
