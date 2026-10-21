"""Reading JSON from a model's output, strictly first, then leniently (GEN-023)."""

import json
import re
from collections.abc import Mapping
from typing import cast

_FENCED = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


class InvalidOutputError(Exception):
    """The model's output does not follow the expected format; the message says why."""


def parse_json_object(raw: str) -> tuple[Mapping[str, object], bool]:
    """Strict JSON first; then lenient: JSON in a Markdown fence or amid prose (GEN-023).
    The flag says whether leniency was needed."""
    lenient = False
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        lenient = True
        data = _lenient_json(raw)
    if not isinstance(data, Mapping):
        raise InvalidOutputError("the output must be a JSON object")
    return cast("Mapping[str, object]", data), lenient


def _lenient_json(raw: str) -> object:
    fenced = _FENCED.search(raw)
    candidate = fenced.group(1) if fenced else raw[raw.find("{") : raw.rfind("}") + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as error:
        raise InvalidOutputError(f"no JSON object found ({error.msg})") from error
