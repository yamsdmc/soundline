import json
from typing import Any

import httpx2
import openai
import pytest

from soundline.adapters.llms.openai_compatible import OpenAICompatibleLanguageModel
from soundline.application.ports import GenerationRequest
from soundline.domain.errors import ConfigurationError, GenerationError, ProviderUnavailableError

REQUEST = GenerationRequest(system="Answer from evidence.", prompt="<evidence>...</evidence>")
ANSWER = '{"claims": [], "insufficient_evidence": "nothing relevant"}'


def completion(content: str | None, finish_reason: str = "stop") -> dict[str, object]:
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
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def model_answering(
    status: int, body: dict[str, object], seen: list[Any] | None = None, **options: Any
) -> OpenAICompatibleLanguageModel:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(json.loads(request.content))
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

    text = model_answering(200, completion(ANSWER), seen).generate(REQUEST)

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
        model_answering(200, completion('{"claims": [', "length")).generate(REQUEST)
        == '{"claims": ['
    )
