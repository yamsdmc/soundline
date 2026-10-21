import json
from typing import Any

import anthropic
import httpx2
import pytest

from soundline.adapters.llms.anthropic import AnthropicLanguageModel
from soundline.application.ports import GenerationRequest
from soundline.domain.errors import ConfigurationError, GenerationError, ProviderUnavailableError
from soundline.domain.usage import TokenUsage

REQUEST = GenerationRequest(system="Answer from evidence.", prompt="<evidence>...</evidence>")
ANSWER = '{"claims": [], "insufficient_evidence": "nothing relevant"}'


def message(
    text: str, stop_reason: str = "end_turn", usage: dict[str, int] | None = None
) -> dict[str, object]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": usage or {"input_tokens": 10, "output_tokens": 5},
    }


def model_answering(
    status: int, body: dict[str, object], seen: list[dict[str, object]] | None = None
) -> AnthropicLanguageModel:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(json.loads(request.content))
        return httpx2.Response(status, json=body)

    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicLanguageModel("claude-sonnet-5-5", client=client)


def error(kind: str) -> dict[str, object]:
    return {"type": "error", "error": {"type": kind, "message": kind}}


@pytest.mark.spec("GEN-012")
def test_the_request_asks_for_schema_constrained_json_without_sampling_parameters():
    seen: list[dict[str, object]] = []

    text = model_answering(200, message(ANSWER), seen).generate(REQUEST).text

    body: Any = seen[0]  # the JSON request body, checked field by field below
    assert text == ANSWER
    assert body["model"] == "claude-sonnet-5-5"
    assert body["system"] == "Answer from evidence."
    assert body["messages"] == [{"role": "user", "content": "<evidence>...</evidence>"}]
    output_format = body["output_config"]["format"]
    assert output_format["type"] == "json_schema"
    assert set(output_format["schema"]["required"]) == {"claims", "insufficient_evidence"}
    assert "temperature" not in body  # rejected by current models
    assert "tool_choice" not in body  # forced tool use is rejected too


@pytest.mark.spec("ARC-032")
@pytest.mark.parametrize(
    ("status", "kind"),
    [(429, "rate_limit_error"), (529, "overloaded_error"), (500, "api_error")],
)
def test_retryable_failures_are_provider_unavailable(status: int, kind: str):
    with pytest.raises(ProviderUnavailableError):
        model_answering(status, error(kind)).generate(REQUEST)


@pytest.mark.spec("ARC-032")
@pytest.mark.parametrize(
    ("status", "kind"),
    [(401, "authentication_error"), (403, "permission_error"), (404, "not_found_error")],
)
def test_configuration_failures_say_how_to_fix_them(status: int, kind: str):
    with pytest.raises(ConfigurationError, match=r"ANTHROPIC_API_KEY|model"):
        model_answering(status, error(kind)).generate(REQUEST)


def test_a_refusal_is_a_generation_error_not_an_answer():
    with pytest.raises(GenerationError, match="declined"):
        model_answering(200, message("", stop_reason="refusal")).generate(REQUEST)


@pytest.mark.spec("GEN-071")
def test_a_truncated_output_is_returned_as_is_so_the_parser_rejects_it():
    truncated = model_answering(200, message('{"claims": [{"te', stop_reason="max_tokens"))

    assert truncated.generate(REQUEST).text == '{"claims": [{"te'


@pytest.mark.spec("GEN-070")
def test_the_generation_reports_token_usage_with_cache_reads_and_writes_apart():
    usage = {
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_input_tokens": 3000,
        "cache_creation_input_tokens": 400,
    }

    generation = model_answering(200, message(ANSWER, usage=usage)).generate(REQUEST)

    assert generation.usage == TokenUsage(input=100, output=20, cache_read=3000, cache_write=400)


def test_the_model_id_names_the_provider():
    assert model_answering(200, message(ANSWER)).model_id == "anthropic:claude-sonnet-5-5"
