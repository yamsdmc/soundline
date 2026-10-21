"""Judge calibration (EVL-043): how often does a judge agree with people?"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from soundline.application.judges import FaithfulnessJudge, Judgment
from soundline.domain.answers import Citation, Claim
from soundline.domain.calibration import Agreement, Label, agreement
from soundline.domain.quotes import Span
from soundline.domain.runs import EvalRun


@dataclass(frozen=True)
class Disagreement:
    label: Label
    judgment: Judgment


@dataclass(frozen=True)
class CalibrationReport:
    judge_model: str
    judge_version: str
    agreement: Agreement
    disagreements: list[Disagreement]
    unreviewed: int
    """Labels still holding an unchecked suggestion: the report is provisional."""
    unreadable: int


def calibrate(labels: Sequence[Label], judge: FaithfulnessJudge) -> CalibrationReport:
    pairs: list[tuple[bool, bool]] = []
    disagreements: list[Disagreement] = []
    unreadable = 0
    for label in labels:
        judgment = judge.judge(_claim(label))
        if judgment is None:
            unreadable += 1
            continue
        pairs.append((label.entailed, judgment.entailed))
        if judgment.entailed != label.entailed:
            disagreements.append(Disagreement(label, judgment))
    return CalibrationReport(
        judge.model_id,
        judge.version,
        agreement(pairs),
        disagreements,
        sum(not label.reviewed for label in labels),
        unreadable,
    )


def labels_from_run(run: EvalRun) -> list[dict[str, object]]:
    """Every judged or judgeable claim of an end-to-end run, as labels to review. The run's
    judge verdict, when there is one, is the suggestion; `reviewed` stays false until a
    person checks it."""
    labels: list[dict[str, object]] = []
    for case_id, answer in run.answers.items():
        verdicts = {
            str(v["claim"]): bool(v["entailed"])
            for v in cast("list[Mapping[str, object]]", answer.get("judgments", []))
        }
        for number, claim in enumerate(cast("list[Mapping[str, object]]", answer["claims"])):
            text = str(claim["text"])
            citations = cast("list[Mapping[str, object]]", claim["citations"])
            labels.append(
                {
                    "id": f"{case_id}/{number}",
                    "claim": text,
                    "quotes": [
                        {
                            "source": c["source"],
                            "section": c["section_path"],
                            "quote": c["quote"],
                        }
                        for c in citations
                    ],
                    "entailed": verdicts.get(text, True),
                    "reviewed": False,
                }
            )
    return labels


def _claim(label: Label) -> Claim:
    citations = tuple(
        Citation(source, quote, Span(0, len(quote)), section_path=section)
        for source, section, quote in label.quotes
    )
    return Claim(label.claim, citations)
