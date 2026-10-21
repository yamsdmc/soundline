"""Versioned prompt templates, shipped as files in the package (GEN-014).

A template is a directory holding `system.txt` and `user.txt`; the directory name is the
version recorded on every answer. A released version is never edited: changing a prompt
means a new directory, so eval runs stay comparable.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from string import Template
from typing import Self

from soundline.application.answer_format import (
    ANSWER_FORMAT,
    CONDENSE_FORMAT,
    CORRECTNESS_FORMAT,
    FAITHFULNESS_FORMAT,
)
from soundline.application.ports import GenerationRequest
from soundline.domain.answers import Claim
from soundline.domain.chunks import Chunk
from soundline.domain.conversation import Turn
from soundline.domain.errors import ConfigurationError
from soundline.domain.languages import detect_language, language_name

GROUNDED_PLACEHOLDERS = ("history", "evidence", "question", "language_instruction")
CONDENSE_PLACEHOLDERS = ("history", "question")
FAITHFULNESS_PLACEHOLDERS = ("claim", "quotes")
CORRECTNESS_PLACEHOLDERS = ("question", "reference", "answer")


@dataclass(frozen=True)
class PromptTemplate:
    version: str
    system: str
    user: Template
    """Its `$placeholders` are rendered by the code, never written by the user."""

    @classmethod
    def packaged(cls, version: str, required: Sequence[str] = GROUNDED_PLACEHOLDERS) -> Self:
        return cls._load(version, resources.files("soundline") / "prompts" / version, required)

    @classmethod
    def from_directory(
        cls, directory: str | Path, required: Sequence[str] = GROUNDED_PLACEHOLDERS
    ) -> Self:
        """A user-supplied template; its directory name is its version."""
        return cls._load(Path(directory).name, Path(directory), required)

    @classmethod
    def _load(cls, version: str, directory: Traversable, required: Sequence[str]) -> Self:
        user = Template(_text(directory, "user.txt"))
        missing = [name for name in required if name not in user.get_identifiers()]
        if missing:
            raise ConfigurationError(
                f"prompt {version!r}: user.txt must contain "
                + ", ".join(f"${name}" for name in missing)
            )
        return cls(version, _text(directory, "system.txt"), user)


def grounded_request(
    template: PromptTemplate,
    question: str,
    evidence: Mapping[str, Chunk],
    history: Sequence[Turn] = (),
) -> GenerationRequest:
    blocks = "\n".join(
        f'<evidence id="{evidence_id}" source="{_attribute(chunk.source)}"'
        f"{_section(chunk.section_path)}>\n"
        f"{_escaped(chunk.text)}\n</evidence>"
        for evidence_id, chunk in evidence.items()
    )
    context = (
        f"{_history(history)}\nThe conversation so far helps understand the question."
        " It is not evidence: never cite it.\n\n"
        if history
        else ""
    )
    user = template.user.substitute(
        history=context,
        evidence=blocks,
        question=question,
        language_instruction=_language(question),
    )
    return GenerationRequest(template.system, user, ANSWER_FORMAT)


def condense_request(
    template: PromptTemplate, question: str, history: Sequence[Turn]
) -> GenerationRequest:
    """Rewrites a follow-up into a standalone search query (RET-071)."""
    user = template.user.substitute(history=_history(history), question=question)
    return GenerationRequest(template.system, user, CONDENSE_FORMAT)


def faithfulness_request(template: PromptTemplate, claim: Claim) -> GenerationRequest:
    """One claim against its cited quotes only, each with its section (EVL-041)."""
    quotes = "\n".join(
        f'<quote source="{_attribute(citation.source)}"'
        f' section="{_attribute(" > ".join(citation.section_path))}">\n'
        f"{_escaped(citation.quote)}\n</quote>"
        for citation in claim.citations
    )
    user = template.user.substitute(claim=_escaped(claim.text), quotes=quotes)
    return GenerationRequest(template.system, user, FAITHFULNESS_FORMAT)


def correctness_request(
    template: PromptTemplate, question: str, reference: str, answer: str
) -> GenerationRequest:
    """The answer as plain text, blind to the system that wrote it (EVL-044, EVL-045)."""
    user = template.user.substitute(
        question=_escaped(question), reference=_escaped(reference), answer=_escaped(answer)
    )
    return GenerationRequest(template.system, user, CORRECTNESS_FORMAT)


def _history(turns: Sequence[Turn]) -> str:
    """Previous questions and answers, text only (GEN-063), escaped like evidence."""
    rendered = "\n".join(
        f"<turn>\nUser: {_escaped(turn.question)}\nAssistant: {_escaped(turn.answer)}\n</turn>"
        for turn in turns
    )
    return f"<history>\n{rendered}\n</history>"


def _language(question: str) -> str:
    """Claims follow the question's language; quotes stay as written (GEN-015)."""
    code = detect_language(question)
    target = (
        f"{language_name(code)}, the language of the question"
        if code
        else "the language of the question"
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


_TAGS = ("evidence", "history", "turn", "claim", "quote", "question", "reference", "answer")


def _section(path: Sequence[str]) -> str:
    return f' section="{_attribute(" > ".join(path))}"' if path else ""


def _attribute(value: str) -> str:
    """Source names and section titles come from documents: they cannot leave their
    attribute (SEC-001)."""
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _escaped(text: str) -> str:
    """Untrusted text can never open or close a block of the prompt (SEC-001)."""
    for tag in _TAGS:
        text = text.replace(f"</{tag}", f"&lt;/{tag}").replace(f"<{tag}", f"&lt;{tag}")
    return text


DEFAULT_PROMPT = PromptTemplate.packaged("grounded-v5")
CONDENSE_PROMPT = PromptTemplate.packaged("condense-v1", CONDENSE_PLACEHOLDERS)
FAITHFULNESS_PROMPT = PromptTemplate.packaged("faithfulness-v2", FAITHFULNESS_PLACEHOLDERS)
CORRECTNESS_PROMPT = PromptTemplate.packaged("correctness-v1", CORRECTNESS_PLACEHOLDERS)
