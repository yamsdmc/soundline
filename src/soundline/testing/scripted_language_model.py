from collections import deque
from collections.abc import Mapping

from soundline.application.ports import GenerationRequest


class ScriptedLanguageModel:
    """Fake language model: returns pre-programmed structured outputs, records every request."""

    def __init__(self, *responses: Mapping[str, object]) -> None:
        self._responses = deque(responses)
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> Mapping[str, object]:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError(f"no scripted response left for request: {request.prompt!r}")
        return self._responses.popleft()
