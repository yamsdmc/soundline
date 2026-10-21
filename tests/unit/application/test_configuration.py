from pathlib import Path

import pytest

from soundline.application.configuration import Configuration, find_configuration_file
from soundline.domain.errors import ConfigurationError
from soundline.domain.usage import Price

FILE = """
[store]
path = "data/index"

[generation]
model = "ollama:qwen3.5:9b"
instructions = "Réponds en deux phrases."

[retrieval]
k = 8

[pricing]
"anthropic:claude-sonnet-5-5" = { input = 3.0, output = 15.0 }
"""


@pytest.mark.spec("CFG-001", "CFG-020")
def test_without_a_file_the_defaults_apply():
    config = Configuration.load(None, {})

    assert config.get("store.path") == ".soundline"
    assert config.get("embedding.model") == "fastembed:intfloat/multilingual-e5-large"
    assert config.get("generation.model") is None
    assert config.get("retrieval.k") == 5
    assert config.source("retrieval.k") == "default"


@pytest.mark.spec("CFG-001")
def test_the_environment_overrides_the_file_which_overrides_the_defaults():
    env = {"SOUNDLINE_RETRIEVAL__K": "12", "SOUNDLINE_LLM": "anthropic:claude-haiku-5-5"}

    config = Configuration.load(("soundline.toml", FILE), env)

    assert config.get("store.path") == "data/index"
    assert config.source("store.path") == "soundline.toml"
    assert config.get("retrieval.k") == 12
    assert config.source("retrieval.k") == "SOUNDLINE_RETRIEVAL__K"
    assert config.get("generation.model") == "anthropic:claude-haiku-5-5"  # the older name
    assert config.get("generation.instructions") == "Réponds en deux phrases."
    assert config.prices == {"anthropic:claude-sonnet-5-5": Price(3.0, 15.0)}


@pytest.mark.spec("CFG-003")
@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            '[generaton]\nmodel = "x"',
            "unknown key 'generaton.model'; did you mean 'generation.model'?",
        ),
        ("[retrieval]\nk = 'eight'", "'retrieval.k' must be an integer, got 'eight'"),
        ("[retrieval]\nk = 0", "'retrieval.k' must be at least 1, got 0"),
        ('[pricing]\n"m" = { input = 1.0 }', "'pricing.m' needs input and output prices"),
        ("generation = 3", "'generation' must be a table"),
    ],
)
def test_an_invalid_file_is_rejected_with_the_key_path_and_what_was_expected(
    text: str, message: str
):
    with pytest.raises(ConfigurationError, match=message.replace("?", r"\?")):
        Configuration.load(("soundline.toml", text), {})


@pytest.mark.spec("CFG-003")
def test_an_invalid_environment_value_names_the_variable():
    with pytest.raises(ConfigurationError, match="SOUNDLINE_RETRIEVAL__K"):
        Configuration.load(None, {"SOUNDLINE_RETRIEVAL__K": "many"})


@pytest.mark.spec("CFG-004")
@pytest.mark.parametrize(
    "text",
    [
        '[generation]\napi_key = "abc"',
        '[generation]\nmodel = "sk-or-v1-0123456789abcdef"',
    ],
)
def test_a_secret_in_the_file_is_rejected_with_guidance(text: str):
    with pytest.raises(ConfigurationError, match="environment variable"):
        Configuration.load(("soundline.toml", text), {})


@pytest.mark.spec("CFG-005")
def test_the_effective_configuration_lists_each_value_with_its_source():
    config = Configuration.load(("soundline.toml", FILE), {"SOUNDLINE_RETRIEVAL__K": "12"})

    lines = config.describe().splitlines()

    assert "retrieval.k = 12  # SOUNDLINE_RETRIEVAL__K" in lines
    assert 'generation.model = "ollama:qwen3.5:9b"  # soundline.toml' in lines
    assert 'embedding.model = "fastembed:intfloat/multilingual-e5-large"  # default' in lines


@pytest.mark.spec("CFG-002")
def test_the_file_is_found_by_variable_then_in_the_directory_then_in_pyproject(tmp_path: Path):
    assert find_configuration_file(tmp_path, {}) is None

    (tmp_path / "pyproject.toml").write_text(
        "[tool.soundline.retrieval]\nk = 7\n", encoding="utf-8"
    )
    label, text = find_configuration_file(tmp_path, {}) or ("", "")
    assert label.endswith("pyproject.toml")
    assert Configuration.load((label, text), {}).get("retrieval.k") == 7

    (tmp_path / "soundline.toml").write_text("[retrieval]\nk = 6\n", encoding="utf-8")
    label, _ = find_configuration_file(tmp_path, {}) or ("", "")
    assert label.endswith("soundline.toml")

    other = tmp_path / "other.toml"
    other.write_text("[retrieval]\nk = 4\n", encoding="utf-8")
    label, _ = find_configuration_file(tmp_path, {"SOUNDLINE_CONFIG": str(other)}) or ("", "")
    assert label == str(other)


@pytest.mark.spec("CFG-002")
def test_a_configuration_file_named_but_missing_is_an_error(tmp_path: Path):
    with pytest.raises(ConfigurationError, match="not found"):
        find_configuration_file(tmp_path, {"SOUNDLINE_CONFIG": str(tmp_path / "nope.toml")})
