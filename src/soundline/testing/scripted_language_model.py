import json
from collections import deque
from collections.abc import Mapping

from soundline.application.ports import Generation, GenerationRequest
from soundline.domain.usage import TokenUsage


class ScriptedLanguageModel:
    """Fake language model: returns pre-programmed outputs, records every request.

    A mapping is returned as JSON (well-behaved structured output); a string is returned
    verbatim, to script malformed or chatty outputs. Every response reports `usage`.
    """

    def __init__(
        self,
        *responses: Mapping[str, object] | str,
        usage: TokenUsage | None = None,
        model_id: str = "scripted:test",
    ) -> None:
        self._responses = deque(responses)
        self._usage = usage or TokenUsage()
        self.model_id = model_id
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> Generation:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError(f"no scripted response left for request: {request.prompt!r}")
        response = self._responses.popleft()
        text = response if isinstance(response, str) else json.dumps(response)
        return Generation(text, self._usage)
