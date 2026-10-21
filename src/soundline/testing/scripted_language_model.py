import json
from collections import deque
from collections.abc import Mapping

from soundline.application.ports import GenerationRequest


class ScriptedLanguageModel:
    """Fake language model: returns pre-programmed outputs, records every request.

    A mapping is returned as JSON (well-behaved structured output); a string is returned
    verbatim, to script malformed or chatty outputs.
    """

    def __init__(self, *responses: Mapping[str, object] | str) -> None:
        self._responses = deque(responses)
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> str:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError(f"no scripted response left for request: {request.prompt!r}")
        response = self._responses.popleft()
        return response if isinstance(response, str) else json.dumps(response)
