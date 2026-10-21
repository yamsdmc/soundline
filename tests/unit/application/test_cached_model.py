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

    assert first == second
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
