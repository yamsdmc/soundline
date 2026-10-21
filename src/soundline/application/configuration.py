"""The configuration (docs/spec/09-configuration.md): defaults, then `soundline.toml`, then
environment variables, then explicit arguments, which callers apply last (CFG-001).

Only settings Soundline acts on are accepted: an unknown key is an error, which catches typos
(CFG-003), and a secret is refused, since configuration files get committed (CFG-004).
"""

import difflib
import json
import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self, cast

from soundline.domain.errors import ConfigurationError
from soundline.domain.usage import Price


def _text(key: str, value: object) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(f"'{key}' must be a string, got {value!r}")
    return value


def _positive(key: str, value: object) -> int:
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"'{key}' must be an integer, got {value!r}")
    if value < 1:
        raise ConfigurationError(f"'{key}' must be at least 1, got {value}")
    return value


_SETTINGS: dict[str, tuple[object, Callable[[str, object], object]]] = {
    "store.path": (".soundline", _text),
    "embedding.model": ("fastembed:intfloat/multilingual-e5-large", _text),  # CFG-023
    "generation.model": (None, _text),
    "generation.prompt": (None, _text),
    "generation.instructions": ("", _text),  # GEN-016
    "generation.history_budget_tokens": (1500, _positive),  # GEN-062
    "retrieval.k": (5, _positive),
    "evaluation.judge_model": (None, _text),
}
"""key: (default, validator)."""

_OLDER_NAMES = {
    "SOUNDLINE_HOME": "store.path",
    "SOUNDLINE_EMBEDDER": "embedding.model",
    "SOUNDLINE_LLM": "generation.model",
    "SOUNDLINE_PROMPT": "generation.prompt",
}
_SECRET_KEY = re.compile(r"api_?key|secret|token|password", re.IGNORECASE)
_SECRET_VALUE = re.compile(r"^(sk-|sk_|xox[bp]-|ghp_|AKIA)")


@dataclass(frozen=True)
class Configuration:
    values: Mapping[str, object]
    sources: Mapping[str, str]
    prices: Mapping[str, Price]

    @classmethod
    def load(cls, file: tuple[str, str] | None, env: Mapping[str, str]) -> Self:
        """`file` is (label, TOML text); `env` the environment."""
        values = {key: default for key, (default, _) in _SETTINGS.items()}
        sources = dict.fromkeys(_SETTINGS, "default")
        prices: dict[str, Price] = {}
        if file is not None:
            label, text = file
            data = _parse(label, text)
            prices = _prices(data.pop("pricing", {}))  # GEN-070
            for key, value in _flatten(data, "").items():
                values[key] = _checked(key, value)
                sources[key] = label
        for variable, key in _environment(env).items():
            try:
                values[key] = _SETTINGS[key][1](key, env[variable])
            except ConfigurationError as error:
                raise ConfigurationError(f"{variable}: {error}") from error
            sources[key] = variable
        return cls(values, sources, prices)

    def get(self, key: str) -> Any:
        return self.values[key]

    def source(self, key: str) -> str:
        return self.sources[key]

    def describe(self) -> str:
        """Each value with where it comes from, as TOML-like lines (CFG-005)."""
        lines = [
            f"{key} = {json.dumps(value, ensure_ascii=False)}  # {self.sources[key]}"
            for key, value in self.values.items()
            if value is not None
        ]
        lines += [
            f'pricing."{model}" = {{ input = {p.input}, output = {p.output} }}'
            for model, p in self.prices.items()
        ]
        return "\n".join(lines)


def find_configuration_file(directory: Path, env: Mapping[str, str]) -> tuple[str, str] | None:
    """`SOUNDLINE_CONFIG`, then `soundline.toml`, then `[tool.soundline]` in `pyproject.toml`
    (CFG-002). Returns (label, TOML text)."""
    named = env.get("SOUNDLINE_CONFIG")
    if named:
        path = Path(named)
        if not path.is_file():
            raise ConfigurationError(f"configuration file not found: {named} (SOUNDLINE_CONFIG)")
        return named, path.read_text(encoding="utf-8")
    own = directory / "soundline.toml"
    if own.is_file():
        return str(own), own.read_text(encoding="utf-8")
    pyproject = directory / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        section = cast("dict[str, Any]", data.get("tool", {})).get("soundline")
        if isinstance(section, dict):
            return str(pyproject), _to_toml(cast("dict[str, Any]", section))
    return None


def _parse(label: str, text: str) -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(f"{label} is not valid TOML: {error}") from error


def _flatten(data: Mapping[str, Any], prefix: str) -> dict[str, object]:
    flat: dict[str, object] = {}
    for name, value in data.items():
        key = f"{prefix}{name}"
        if not prefix and not isinstance(value, dict):
            raise ConfigurationError(f"'{key}' must be a table, such as [{key}]")
        if isinstance(value, dict) and prefix:
            raise ConfigurationError(f"unknown key '{key}'{_hint(key)}")
        if isinstance(value, dict):
            flat.update(_flatten(cast("dict[str, Any]", value), f"{key}."))
        else:
            flat[key] = value
    return flat


def _checked(key: str, value: object) -> object:
    if _SECRET_KEY.search(key.rsplit(".", 1)[-1]) or (
        isinstance(value, str) and _SECRET_VALUE.match(value)
    ):
        raise ConfigurationError(
            f"'{key}' looks like a secret: secrets are never read from the configuration"
            " file; set them in an environment variable (CFG-004)"
        )
    if key not in _SETTINGS:
        raise ConfigurationError(f"unknown key '{key}'{_hint(key)}")
    return _SETTINGS[key][1](key, value)


def _hint(key: str) -> str:
    close = difflib.get_close_matches(key, _SETTINGS, n=1)
    return f"; did you mean '{close[0]}'?" if close else ""


def _environment(env: Mapping[str, str]) -> dict[str, str]:
    """Variable -> key. The documented form wins over an older name for the same key."""
    found = {variable: key for variable, key in _OLDER_NAMES.items() if variable in env}
    for variable in env:
        if variable.startswith("SOUNDLINE_") and "__" in variable:
            section, _, name = variable.removeprefix("SOUNDLINE_").partition("__")
            key = f"{section.lower()}.{name.lower()}"
            if key not in _SETTINGS:
                raise ConfigurationError(f"{variable}: unknown key '{key}'{_hint(key)}")
            found = {v: k for v, k in found.items() if k != key} | {variable: key}
    return found


def _prices(table: object) -> dict[str, Price]:
    if not isinstance(table, dict):
        raise ConfigurationError("'pricing' must be a table of models")
    prices: dict[str, Price] = {}
    for model, entry in cast("dict[str, object]", table).items():
        fields = cast("dict[str, object]", entry) if isinstance(entry, dict) else {}
        if not {"input", "output"} <= fields.keys():
            raise ConfigurationError(f"'pricing.{model}' needs input and output prices")
        try:
            prices[model] = Price(
                **{name: float(cast("float", value)) for name, value in fields.items()}
            )
        except (TypeError, ValueError) as error:
            raise ConfigurationError(f"'pricing.{model}': {error}") from error
    return prices


def _to_toml(section: Mapping[str, Any]) -> str:
    """`[tool.soundline]` as a file of its own."""
    lines: list[str] = []
    for name, table in section.items():
        lines.append(f"[{name}]")
        for key, value in cast("dict[str, object]", table).items():
            lines.append(f"{json.dumps(key)} = {_toml_value(value)}")
    return "\n".join(lines)


def _toml_value(value: object) -> str:
    if isinstance(value, dict):
        items = cast("dict[str, object]", value).items()
        return "{ " + ", ".join(f"{json.dumps(k)} = {_toml_value(v)}" for k, v in items) + " }"
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False)
