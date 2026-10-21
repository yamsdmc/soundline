from pathlib import Path

import pytest

from soundline.application.prompts import DEFAULT_PROMPT, PromptTemplate
from soundline.domain.errors import ConfigurationError


def write_prompt(directory: Path, user: str) -> Path:
    directory.mkdir()
    (directory / "system.txt").write_text("Answer from the evidence only.\n")
    (directory / "user.txt").write_text(user)
    return directory


@pytest.mark.spec("GEN-014")
def test_the_packaged_prompt_is_versioned():
    assert DEFAULT_PROMPT.version == "grounded-v4"


@pytest.mark.spec("GEN-014")
def test_a_prompt_directory_overrides_the_packaged_one_and_names_its_version(tmp_path: Path):
    directory = write_prompt(
        tmp_path / "terse-v2", "$history$evidence\nQ: $question\n$language_instruction\n"
    )

    prompt = PromptTemplate.from_directory(directory)

    assert prompt.version == "terse-v2"
    assert prompt.system == "Answer from the evidence only."


@pytest.mark.spec("GEN-014")
@pytest.mark.parametrize("missing", ["$history", "$evidence", "$question", "$language_instruction"])
def test_a_prompt_without_a_required_placeholder_is_rejected(tmp_path: Path, missing: str):
    placeholders = ["$history", "$evidence", "$question", "$language_instruction"]
    user = "\n".join(p for p in placeholders if p != missing)

    with pytest.raises(ConfigurationError, match=missing.removeprefix("$")):
        PromptTemplate.from_directory(write_prompt(tmp_path / "broken", user))
