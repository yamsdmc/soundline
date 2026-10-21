import pytest

from soundline.adapters.llms.anthropic import AnthropicLanguageModel
from soundline.adapters.llms.openai_compatible import OpenAICompatibleLanguageModel
from soundline.api import llm_from_spec
from soundline.domain.errors import ConfigurationError


@pytest.mark.spec("CFG-010", "CFG-013")
def test_ollama_models_run_locally_through_the_openai_compatible_adapter(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    llm = llm_from_spec("ollama:llama3.2")

    assert isinstance(llm, OpenAICompatibleLanguageModel)
    assert str(llm._client.base_url).startswith("http://localhost:11434/v1")  # pyright: ignore[reportPrivateUsage]
    # Thinking models answer in seconds instead of minutes; the code verifies the answer anyway.
    assert llm._reasoning_effort == "none"  # pyright: ignore[reportPrivateUsage]
    assert llm.model_id == "ollama:llama3.2"  # free in the price table (GEN-070)


@pytest.mark.spec("CFG-010")
def test_providers_are_selected_by_their_prefix(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    assert isinstance(llm_from_spec("openai:gpt-5"), OpenAICompatibleLanguageModel)
    assert isinstance(llm_from_spec("anthropic:claude-sonnet-5-5"), AnthropicLanguageModel)


def test_an_unknown_provider_lists_the_supported_ones():
    with pytest.raises(ConfigurationError, match=r"anthropic:.*openai:.*ollama:"):
        llm_from_spec("mystery:model")
