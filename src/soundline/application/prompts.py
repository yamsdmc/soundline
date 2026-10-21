"""Versioned prompt templates, shipped as files in the package (GEN-014).

A template is a directory holding `system.txt` and `user.txt`; the directory name is the
version recorded on every answer. A released version is never edited: changing a prompt
means a new directory, so eval runs stay comparable.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from string import Template
from typing import Self

from soundline.application.ports import GenerationRequest
from soundline.domain.chunks import Chunk
from soundline.domain.errors import ConfigurationError
from soundline.domain.languages import detect_language, language_name

_PLACEHOLDERS = ("evidence", "question", "language_instruction")


@dataclass(frozen=True)
class PromptTemplate:
    version: str
    system: str
    user: Template
    """`$evidence`, `$question` and `$language_instruction` are rendered by the code."""

    @classmethod
    def packaged(cls, version: str) -> Self:
        return cls._load(version, resources.files("soundline") / "prompts" / version)

    @classmethod
    def from_directory(cls, directory: str | Path) -> Self:
        """A user-supplied template; its directory name is its version."""
        return cls._load(Path(directory).name, Path(directory))

    @classmethod
    def _load(cls, version: str, directory: Traversable) -> Self:
        user = Template(_text(directory, "user.txt"))
        missing = [name for name in _PLACEHOLDERS if name not in user.get_identifiers()]
        if missing:
            raise ConfigurationError(
                f"prompt {version!r}: user.txt must contain "
                + ", ".join(f"${name}" for name in missing)
            )
        return cls(version, _text(directory, "system.txt"), user)

    def render(self, question: str, evidence: Mapping[str, Chunk]) -> GenerationRequest:
        blocks = "\n".join(
            f'<evidence id="{evidence_id}" source="{chunk.source}">\n'
            f"{_escaped(chunk.text)}\n</evidence>"
            for evidence_id, chunk in evidence.items()
        )
        user = self.user.substitute(
            evidence=blocks, question=question, language_instruction=_language(question)
        )
        return GenerationRequest(self.system, user)


def _language(question: str) -> str:
    """Claims follow the question's language; quotes stay as written (GEN-015)."""
    code = detect_language(question)
    target = (
        f"{language_name(code)}, the language of the question"
        if code
        else ("the language of the question")
    )
    return (
        f"Write each claim in {target}, even when the evidence is in another language."
        " Quotes stay verbatim, in the language of the evidence."
    )


def _text(directory: Traversable, name: str) -> str:
    try:
        return directory.joinpath(name).read_text(encoding="utf-8").removesuffix("\n")
    except FileNotFoundError as error:
        raise ConfigurationError(f"prompt template {name} not found in {directory}") from error


def _escaped(text: str) -> str:
    """Evidence can never open or close an evidence block (SEC-001)."""
    return text.replace("</evidence", "&lt;/evidence").replace("<evidence", "&lt;evidence")


DEFAULT_PROMPT = PromptTemplate.packaged("grounded-v2")
