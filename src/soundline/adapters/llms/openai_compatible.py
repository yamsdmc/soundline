"""Any OpenAI-compatible chat server: OpenAI, Ollama, vLLM, LM Studio (install
`soundline[openai]`, CFG-011)."""

import logging
from typing import Literal

import openai
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.completion_create_params import ResponseFormat
from openai.types.shared import ReasoningEffort

from soundline.application.answer_format import ANSWER_SCHEMA
from soundline.application.ports import Generation, GenerationRequest
from soundline.domain.errors import ConfigurationError, GenerationError, ProviderUnavailableError
from soundline.domain.usage import TokenUsage

_log = logging.getLogger(__name__)
_NOT_IMPLEMENTED = 501
JsonMode = Literal["schema", "object", "prompt"]


class _StructuredOutputUnavailableError(Exception):
    """The server rejected `response_format` as not implemented."""


class OpenAICompatibleLanguageModel:
    """Schema-constrained JSON by default; `json_mode="object"` for servers or small local
    models without JSON-schema support, `"prompt"` for none at all: the format is then only
    asked in the prompt. The output is validated the same way in every mode (GEN-023)."""

    def __init__(  # noqa: PLR0913  # keyword-only options
        self,
        model: str,
        client: openai.OpenAI | None = None,
        *,
        json_mode: JsonMode = "schema",
        temperature: float | None = None,
        max_tokens: int = 4096,
        reasoning_effort: ReasoningEffort = None,
        provider: str = "openai",
    ) -> None:
        self._model = model
        self._client = client or openai.OpenAI()  # OPENAI_API_KEY, OPENAI_BASE_URL
        self._json_mode = json_mode
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._reasoning_effort: ReasoningEffort = reasoning_effort
        self._provider = provider

    @property
    def model_id(self) -> str:
        return f"{self._provider}:{self._model}"

    def generate(self, request: GenerationRequest) -> Generation:
        try:
            return self._generate(request)
        except _StructuredOutputUnavailableError as error:
            # Some servers cannot constrain output (e.g. Ollama without its grammar library):
            # ask for the format in the prompt only; validation is unchanged (GEN-012).
            _log.warning(
                "%s: structured output is unavailable (%s); asking for JSON in the prompt only",
                self._model,
                error,
            )
            self._json_mode = "prompt"
            return self._generate(request)

    def _generate(self, request: GenerationRequest) -> Generation:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.prompt},
        ]
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=messages,
                response_format=self._response_format(),
                temperature=openai.omit if self._temperature is None else self._temperature,
                reasoning_effort=(
                    openai.omit if self._reasoning_effort is None else self._reasoning_effort
                ),
            )
        except (openai.AuthenticationError, openai.PermissionDeniedError) as error:
            raise ConfigurationError(
                "the server rejected the api key; set OPENAI_API_KEY (or the provider's key)"
            ) from error
        except openai.NotFoundError as error:
            raise ConfigurationError(
                f"unknown model {self._model!r}; for Ollama, run `ollama pull {self._model}`"
            ) from error
        except (openai.RateLimitError, openai.InternalServerError) as error:
            if error.status_code != _NOT_IMPLEMENTED:
                raise ProviderUnavailableError(
                    f"the model server is unavailable: {error}"
                ) from error
            if self._json_mode != "prompt":
                raise _StructuredOutputUnavailableError(error.message) from error
            raise ConfigurationError(
                f"the server does not implement chat completions for {self._model!r} (501)"
            ) from error
        except openai.APIConnectionError as error:  # includes timeouts
            raise ProviderUnavailableError(
                f"cannot reach the model server at {self._client.base_url}"
                " (for Ollama, is `ollama serve` running?)"
            ) from error
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise GenerationError("the model returned no content (refusal or empty output)")
        # A truncated output (finish_reason "length") is returned as is: the parser rejects it
        # and the use case retries once (GEN-071, GEN-020).
        return Generation(content, _token_usage(response.usage))

    def _response_format(self) -> ResponseFormat | openai.Omit:
        if self._json_mode == "prompt":
            return openai.omit
        if self._json_mode == "object":
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            "json_schema": {"name": "grounded_answer", "schema": ANSWER_SCHEMA, "strict": True},
        }


def _token_usage(usage: CompletionUsage | None) -> TokenUsage:
    """`prompt_tokens` includes cached tokens; some servers report no usage at all."""
    if usage is None:
        return TokenUsage()
    details = usage.prompt_tokens_details
    cached = (details.cached_tokens or 0) if details else 0
    return TokenUsage(
        input=usage.prompt_tokens - cached, output=usage.completion_tokens, cache_read=cached
    )
