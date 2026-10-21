"""Versioned prompt templates, shipped as files in the package (GEN-014)."""

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from string import Template
from typing import Self

from soundline.application.ports import GenerationRequest
from soundline.domain.chunks import Chunk


@dataclass(frozen=True)
class PromptTemplate:
    version: str
    system: str
    user: Template
    """`$evidence` and `$question` are substituted; evidence is rendered by the code."""

    @classmethod
    def packaged(cls, version: str) -> Self:
        directory = resources.files("soundline") / "prompts" / version
        return cls(
            version,
            _text(directory.joinpath("system.txt").read_text(encoding="utf-8")),
            Template(_text(directory.joinpath("user.txt").read_text(encoding="utf-8"))),
        )

    def render(self, question: str, evidence: Mapping[str, Chunk]) -> GenerationRequest:
        blocks = "\n".join(
            f'<evidence id="{evidence_id}" source="{chunk.source}">\n'
            f"{_escaped(chunk.text)}\n</evidence>"
            for evidence_id, chunk in evidence.items()
        )
        return GenerationRequest(
            self.system, self.user.substitute(evidence=blocks, question=question)
        )


def _text(content: str) -> str:
    return content.removesuffix("\n")


def _escaped(text: str) -> str:
    """Evidence can never open or close an evidence block (SEC-001)."""
    return text.replace("</evidence", "&lt;/evidence").replace("<evidence", "&lt;evidence")


DEFAULT_PROMPT = PromptTemplate.packaged("grounded-v1")
