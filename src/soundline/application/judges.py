"""LLM judges for evaluation (EVL-040 to EVL-044). Judges measure; they never change an
answer. A judge is a versioned prompt plus a model, and its calls are cached like any other."""

from dataclasses import dataclass

from soundline.application.model_output import InvalidOutputError, parse_json_object
from soundline.application.ports import LanguageModel
from soundline.application.prompts import (
    CORRECTNESS_PROMPT,
    FAITHFULNESS_PROMPT,
    PromptTemplate,
    correctness_request,
    faithfulness_request,
)
from soundline.domain.answers import Claim
from soundline.domain.usage import TokenUsage


@dataclass(frozen=True)
class Judgment:
    entailed: bool
    rationale: str


class FaithfulnessJudge:
    """Is a claim entailed by its cited quotes, read on their own (EVL-041)?"""

    def __init__(self, llm: LanguageModel, prompt: PromptTemplate = FAITHFULNESS_PROMPT) -> None:
        self._llm = llm
        self._prompt = prompt
        self.usage = TokenUsage()
        """Tokens spent by this judge so far."""

    @property
    def version(self) -> str:
        return self._prompt.version

    @property
    def model_id(self) -> str:
        return self._llm.model_id

    def judge(self, claim: Claim) -> Judgment | None:
        """None when the verdict cannot be read: no judgment rather than a guess."""
        if not claim.citations:  # nothing cited can entail it (GEN-080 shows such claims)
            return Judgment(False, "no citation")
        generation = self._llm.generate(faithfulness_request(self._prompt, claim))
        self.usage += generation.usage
        try:
            output, _ = parse_json_object(generation.text)
        except InvalidOutputError:
            return None
        entailed, rationale = output.get("entailed"), output.get("rationale")
        if not isinstance(entailed, bool) or not isinstance(rationale, str):
            return None
        return Judgment(entailed, rationale)


@dataclass(frozen=True)
class CorrectnessJudgment:
    score: float
    """1 correct, 0.5 partial, 0 incorrect (EVL-045)."""
    rationale: str


_SCORES = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}


class CorrectnessJudge:
    """Does an answer agree with the reference answer (EVL-045)?"""

    def __init__(self, llm: LanguageModel, prompt: PromptTemplate = CORRECTNESS_PROMPT) -> None:
        self._llm = llm
        self._prompt = prompt
        self.usage = TokenUsage()
        """Tokens spent by this judge so far."""

    @property
    def version(self) -> str:
        return self._prompt.version

    @property
    def model_id(self) -> str:
        return self._llm.model_id

    def judge(self, question: str, reference: str, answer: str) -> CorrectnessJudgment | None:
        """None when the verdict cannot be read: no judgment rather than a guess."""
        request = correctness_request(self._prompt, question, reference, answer)
        generation = self._llm.generate(request)
        self.usage += generation.usage
        try:
            output, _ = parse_json_object(generation.text)
        except InvalidOutputError:
            return None
        verdict, rationale = output.get("verdict"), output.get("rationale")
        if verdict not in _SCORES or not isinstance(rationale, str):
            return None
        return CorrectnessJudgment(_SCORES[str(verdict)], rationale)
