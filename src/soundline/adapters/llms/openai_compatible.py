"""Any OpenAI-compatible chat server: OpenAI, Ollama, vLLM, LM Studio (install
`soundline[openai]`, CFG-011)."""

from typing import Literal

import openai
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.completion_create_params import ResponseFormat

from soundline.application.answer_format import ANSWER_SCHEMA
from soundline.application.ports import GenerationRequest
from soundline.domain.errors import ConfigurationError, GenerationError, ProviderUnavailableError


class OpenAICompatibleLanguageModel:
    """Schema-constrained JSON by default; `json_mode="object"` for servers or small local
    models without JSON-schema support (the lenient parser covers the rest, GEN-023)."""

    def __init__(
        self,
        model: str,
        client: openai.OpenAI | None = None,
        *,
        json_mode: Literal["schema", "object"] = "schema",
        temperature: float | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self._model = model
        self._client = client or openai.OpenAI()  # OPENAI_API_KEY, OPENAI_BASE_URL
        self._json_mode = json_mode
        self._temperature = temperature
        self._max_tokens = max_tokens

    def generate(self, request: GenerationRequest) -> str:
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
            raise ProviderUnavailableError(f"the model server is unavailable: {error}") from error
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
        return content

    def _response_format(self) -> ResponseFormat:
        if self._json_mode == "object":
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            "json_schema": {"name": "grounded_answer", "schema": ANSWER_SCHEMA, "strict": True},
        }
