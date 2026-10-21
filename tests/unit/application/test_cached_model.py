import pytest

from soundline.application.answer_format import ANSWER_FORMAT, CONDENSE_FORMAT
from soundline.application.cached_model import CachedLanguageModel
from soundline.application.ports import GenerationRequest
from soundline.domain.usage import TokenUsage
from soundline.testing import InMemoryGenerationCache, ScriptedLanguageModel

REQUEST = GenerationRequest("system", "prompt", ANSWER_FORMAT)


@pytest.mark.spec("EVL-061")
def test_an_identical_request_is_answered_from_the_cache_with_its_original_usage():
    inner = ScriptedLanguageModel("first", usage=TokenUsage(input=10, output=2))
    model = CachedLanguageModel(inner, InMemoryGenerationCache())

    first = model.generate(REQUEST)
    second = model.generate(REQUEST)

    assert (second.text, second.cached) == (first.text, True)
    assert second.usage == TokenUsage(input=10, output=2)  # identical results
    assert len(inner.requests) == 1  # at zero model cost


@pytest.mark.spec("EVL-061")
@pytest.mark.parametrize(
    "other",
    [
        GenerationRequest("other system", "prompt", ANSWER_FORMAT),
        GenerationRequest("system", "other prompt", ANSWER_FORMAT),
        GenerationRequest("system", "prompt", CONDENSE_FORMAT),
    ],
)
def test_any_change_in_the_request_misses_the_cache(other: GenerationRequest):
    inner = ScriptedLanguageModel("first", "second")
    model = CachedLanguageModel(inner, InMemoryGenerationCache())

    model.generate(REQUEST)

    assert model.generate(other).text == "second"


@pytest.mark.spec("EVL-061")
def test_two_models_never_share_cached_outputs():
    cache = InMemoryGenerationCache()
    CachedLanguageModel(ScriptedLanguageModel("a", model_id="ollama:a"), cache).generate(REQUEST)

    other = CachedLanguageModel(ScriptedLanguageModel("b", model_id="ollama:b"), cache)

    assert other.model_id == "ollama:b"
    assert other.generate(REQUEST).text == "b"


class Clock:
    def __init__(self, *readings: float) -> None:
        self._readings = list(readings)

    def __call__(self) -> float:
        return self._readings.pop(0)


@pytest.mark.spec("EVL-061", "EVL-030")
def test_a_cached_output_keeps_the_latency_of_the_original_call():
    model = CachedLanguageModel(
        ScriptedLanguageModel("first"), InMemoryGenerationCache(), clock=Clock(10.0, 12.5)
    )

    fresh = model.generate(REQUEST)
    cached = model.generate(REQUEST)

    assert (fresh.latency_ms, fresh.cached) == (2500.0, False)
    assert (cached.latency_ms, cached.cached) == (2500.0, True)
