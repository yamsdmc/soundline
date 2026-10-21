"""Claude through the official Anthropic SDK (install `soundline[anthropic]`)."""

import anthropic

from soundline.application.ports import GenerationRequest
from soundline.domain.errors import ConfigurationError, GenerationError, ProviderUnavailableError

# The answer contract of docs/spec/05-generation.md as a strict JSON schema: both fields are
# always present, `insufficient_evidence` is null when the model answers.
ANSWER_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence_id": {"type": "string"},
                                "quote": {"type": "string"},
                            },
                            "required": ["evidence_id", "quote"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["text", "citations"],
                "additionalProperties": False,
            },
        },
        "insufficient_evidence": {"type": ["string", "null"]},
    },
    "required": ["claims", "insufficient_evidence"],
    "additionalProperties": False,
}


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

    def generate(self, request: GenerationRequest) -> str:
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
        return next((block.text for block in response.content if block.type == "text"), "")
