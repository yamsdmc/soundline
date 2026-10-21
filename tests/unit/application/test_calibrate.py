import pytest

from soundline.application.calibrate import calibrate, labels_from_run
from soundline.application.judges import FaithfulnessJudge
from soundline.domain.calibration import Label
from soundline.domain.runs import EvalRun
from soundline.testing import ScriptedLanguageModel

CLAIM = {
    "text": "Rent is due on the 5th.",
    "citations": [
        {
            "source": "file:///docs/lease.md",
            "quote": "Rent is due on the 5th",
            "span": [0, 22],
            "section_path": ["Lease", "Rent"],
            "approximate": False,
        }
    ],
}


def run_with(answers: dict[str, dict[str, object]]) -> EvalRun:
    return EvalRun("r", "now", {}, {}, {}, {}, {}, answers=answers)


@pytest.mark.spec("EVL-043")
def test_labels_are_exported_from_a_run_with_the_judge_verdict_as_an_unreviewed_suggestion():
    run = run_with(
        {
            "rent": {
                "claims": [CLAIM],
                "judgments": [{"claim": CLAIM["text"], "entailed": False, "rationale": "r"}],
            },
            "parking": {"claims": []},
        }
    )

    labels = labels_from_run(run)

    assert labels == [
        {
            "id": "rent/0",
            "claim": "Rent is due on the 5th.",
            "quotes": [
                {
                    "source": "file:///docs/lease.md",
                    "section": ["Lease", "Rent"],
                    "quote": "Rent is due on the 5th",
                }
            ],
            "entailed": False,
            "reviewed": False,
        }
    ]


def label(label_id: str, entailed: bool, reviewed: bool = True) -> Label:
    quotes = (("lease.md", ("Rent",), "Rent is due on the 5th"),)
    return Label(label_id, "Rent is due on the 5th.", quotes, entailed, reviewed)


@pytest.mark.spec("EVL-043")
def test_calibration_compares_the_judge_with_the_labels_and_lists_disagreements():
    judge = ScriptedLanguageModel(
        {"rationale": "states it", "entailed": True},
        {"rationale": "states it", "entailed": True},
        model_id="ollama:judge",
    )

    report = calibrate(
        [label("a", True), label("b", False, reviewed=False)], FaithfulnessJudge(judge)
    )

    assert (report.agreement.cases, report.agreement.false_accepts) == (2, 1)
    assert [(d.label.id, d.judgment.rationale) for d in report.disagreements] == [
        ("b", "states it")
    ]
    assert report.unreviewed == 1
    assert (report.judge_model, report.judge_version) == ("ollama:judge", "faithfulness-v3")


@pytest.mark.spec("EVL-043")
def test_an_unreadable_verdict_is_reported_and_left_out_of_the_agreement():
    judge = ScriptedLanguageModel("???", {"rationale": "ok", "entailed": True})

    report = calibrate([label("a", True), label("b", True)], FaithfulnessJudge(judge))

    assert report.agreement.cases == 1
    assert report.unreadable == 1
