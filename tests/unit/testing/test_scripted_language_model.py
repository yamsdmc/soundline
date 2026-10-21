import json

import pytest

from soundline.application.ports import GenerationRequest
from soundline.testing import ScriptedLanguageModel


def request(prompt: str) -> GenerationRequest:
    return GenerationRequest(system="Answer from evidence.", prompt=prompt)


def test_scripted_responses_are_returned_in_order_and_requests_recorded():
    model = ScriptedLanguageModel({"claims": []}, "```json\n{}\n``` chatty")

    first = model.generate(request("first"))
    second = model.generate(request("second"))

    assert json.loads(first) == {"claims": []}  # mappings come back as JSON text
    assert second == "```json\n{}\n``` chatty"  # strings come back verbatim
    assert [r.prompt for r in model.requests] == ["first", "second"]


def test_calling_the_model_beyond_its_script_fails_loudly():
    model = ScriptedLanguageModel()

    with pytest.raises(AssertionError, match="no scripted response left"):
        model.generate(request("unexpected"))
