"""Claude through the official Anthropic SDK (install `soundline[anthropic]`)."""

import anthropic

from soundline.application.answer_format import ANSWER_SCHEMA
from soundline.application.ports import Generation, GenerationRequest
from soundline.domain.errors import ConfigurationError, GenerationError, ProviderUnavailableError
from soundline.domain.usage import TokenUsage


class AnthropicLanguageModel:
    """Schema-constrained output via `output_config.format` (GEN-012). No sampling parameters
    and no forced tool choice: current models reject both."""

    def __init__(
        self,
        model: str,
        client: anthropic.Anthropic | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self._model = model
        self._client = client or anthropic.Anthropic()
        self._max_tokens = max_tokens

    @property
    def model_id(self) -> str:
        return f"anthropic:{self._model}"

    def generate(self, request: GenerationRequest) -> Generation:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": request.prompt}],
                output_config={"format": {"type": "json_schema", "schema": ANSWER_SCHEMA}},
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as error:
            raise ConfigurationError(
                "Anthropic rejected the credentials; set ANTHROPIC_API_KEY or run `ant auth login`"
            ) from error
        except anthropic.NotFoundError as error:
            raise ConfigurationError(
                f"unknown model {self._model!r}; check generation.model in the configuration"
            ) from error
        except (
            anthropic.RateLimitError,
            anthropic.OverloadedError,  # 529: not a subclass of InternalServerError
            anthropic.InternalServerError,
            anthropic.APIConnectionError,
        ) as error:  # retryable, after the SDK's own retries (ARC-032)
            raise ProviderUnavailableError(f"Anthropic is unavailable: {error}") from error
        if response.stop_reason == "refusal":
            raise GenerationError(f"the model declined to answer ({response.stop_details})")
        # A truncated output (stop_reason max_tokens) is returned as is: the parser rejects it
        # and the use case retries once (GEN-071, GEN-020).
        text = next((block.text for block in response.content if block.type == "text"), "")
        usage = response.usage  # input_tokens excludes cache reads and writes
        return Generation(
            text,
            TokenUsage(
                input=usage.input_tokens,
                output=usage.output_tokens,
                cache_read=usage.cache_read_input_tokens or 0,
                cache_write=usage.cache_creation_input_tokens or 0,
            ),
        )
