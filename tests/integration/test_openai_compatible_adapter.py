import json
from typing import Any

import httpx2
import openai
import pytest

from soundline.adapters.llms.openai_compatible import OpenAICompatibleLanguageModel
from soundline.application.ports import GenerationRequest
from soundline.domain.errors import ConfigurationError, GenerationError, ProviderUnavailableError
from soundline.domain.usage import TokenUsage

REQUEST = GenerationRequest(system="Answer from evidence.", prompt="<evidence>...</evidence>")
ANSWER = '{"claims": [], "insufficient_evidence": "nothing relevant"}'


def completion(
    content: str | None, finish_reason: str = "stop", usage: dict[str, object] | None = None
) -> dict[str, object]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "llama3.2",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def model_answering(
    status: int, body: dict[str, object], seen: list[Any] | None = None, **options: Any
) -> OpenAICompatibleLanguageModel:
    return model_replying([(status, body)], seen, **options)


def model_replying(
    replies: list[tuple[int, dict[str, object]]], seen: list[Any] | None = None, **options: Any
) -> OpenAICompatibleLanguageModel:
    """Replies in order; the last one repeats."""
    pending = list(replies)

    def handler(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(json.loads(request.content))
        status, body = pending.pop(0) if len(pending) > 1 else pending[0]
        return httpx2.Response(status, json=body)

    client = openai.OpenAI(
        api_key="test-key",
        base_url="http://localhost:11434/v1",
        max_retries=0,
        http_client=openai.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return OpenAICompatibleLanguageModel("llama3.2", client=client, **options)


@pytest.mark.spec("GEN-012", "CFG-011")
def test_the_request_asks_for_the_answer_schema_as_strict_json():
    seen: list[Any] = []

    text = model_answering(200, completion(ANSWER), seen).generate(REQUEST).text

    body = seen[0]
    assert text == ANSWER
    assert body["messages"] == [
        {"role": "system", "content": "Answer from evidence."},
        {"role": "user", "content": "<evidence>...</evidence>"},
    ]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert "temperature" not in body  # only sent when configured


def test_a_temperature_is_sent_only_when_configured():
    seen: list[Any] = []

    model_answering(200, completion(ANSWER), seen, temperature=0.0).generate(REQUEST)

    assert seen[0]["temperature"] == 0.0


@pytest.mark.spec("GEN-023")
def test_servers_without_json_schema_support_can_use_plain_json_mode():
    seen: list[Any] = []

    model_answering(200, completion(ANSWER), seen, json_mode="object").generate(REQUEST)

    assert seen[0]["response_format"] == {"type": "json_object"}


@pytest.mark.spec("ARC-032")
@pytest.mark.parametrize("status", [429, 500, 503])
def test_retryable_failures_are_provider_unavailable(status: int):
    with pytest.raises(ProviderUnavailableError):
        model_answering(status, {"error": {"message": "busy"}}).generate(REQUEST)


@pytest.mark.spec("ARC-032")
@pytest.mark.parametrize("status", [401, 403, 404])
def test_configuration_failures_say_how_to_fix_them(status: int):
    with pytest.raises(ConfigurationError, match=r"api key|model"):
        model_answering(status, {"error": {"message": "nope"}}).generate(REQUEST)


def test_a_server_that_cannot_be_reached_is_unavailable_with_a_hint():
    def unreachable(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused")

    client = openai.OpenAI(
        api_key="x",
        base_url="http://localhost:11434/v1",
        max_retries=0,
        http_client=openai.DefaultHttpxClient(transport=httpx2.MockTransport(unreachable)),
    )

    with pytest.raises(ProviderUnavailableError, match="localhost:11434"):
        OpenAICompatibleLanguageModel("llama3.2", client=client).generate(REQUEST)


def test_an_empty_or_refused_message_is_a_generation_error():
    with pytest.raises(GenerationError):
        model_answering(200, completion(None)).generate(REQUEST)


@pytest.mark.spec("GEN-071")
def test_a_truncated_output_is_returned_as_is_so_the_parser_rejects_it():
    assert (
        model_answering(200, completion('{"claims": [', "length")).generate(REQUEST).text
        == '{"claims": ['
    )


UNSUPPORTED: tuple[int, dict[str, object]] = (
    501,
    {"error": {"message": "structured output is unavailable"}},
)


@pytest.mark.spec("GEN-012", "GEN-023")
def test_a_server_without_structured_output_falls_back_to_json_asked_in_the_prompt(
    caplog: pytest.LogCaptureFixture,
):
    seen: list[Any] = []
    model = model_replying([UNSUPPORTED, (200, completion(ANSWER))], seen)

    first, second = model.generate(REQUEST).text, model.generate(REQUEST).text

    assert first == second == ANSWER
    assert "response_format" in seen[0]
    assert ["response_format" in body for body in seen[1:]] == [False, False]
    assert len(caplog.records) == 1  # one warning, then remembered


@pytest.mark.spec("ARC-032")
def test_a_server_that_implements_nothing_we_need_is_a_configuration_error():
    with pytest.raises(ConfigurationError, match="501"):
        model_replying([UNSUPPORTED], json_mode="prompt").generate(REQUEST)


def test_a_reasoning_effort_is_sent_only_when_configured():
    seen: list[Any] = []

    model_answering(200, completion(ANSWER), seen).generate(REQUEST)
    model_answering(200, completion(ANSWER), seen, reasoning_effort="none").generate(REQUEST)

    assert "reasoning_effort" not in seen[0]
    assert seen[1]["reasoning_effort"] == "none"


@pytest.mark.spec("GEN-070")
def test_the_generation_reports_token_usage_with_cached_prompt_tokens_apart():
    usage: dict[str, object] = {
        "prompt_tokens": 1000,
        "completion_tokens": 50,
        "total_tokens": 1050,
        "prompt_tokens_details": {"cached_tokens": 800},
    }

    generation = model_answering(200, completion(ANSWER, usage=usage)).generate(REQUEST)

    assert generation.usage == TokenUsage(input=200, output=50, cache_read=800)


def test_a_server_that_reports_no_usage_counts_zero_tokens():
    body = completion(ANSWER)
    del body["usage"]

    assert model_answering(200, body).generate(REQUEST).usage == TokenUsage()


def test_the_model_id_names_the_provider():
    assert model_answering(200, completion(ANSWER)).model_id == "openai:llama3.2"
    assert model_answering(200, completion(ANSWER), provider="ollama").model_id == "ollama:llama3.2"
