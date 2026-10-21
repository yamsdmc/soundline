import json

import pytest

from soundline.domain.calibration import Label, agreement, parse_labels
from soundline.domain.datasets import DatasetError


@pytest.mark.spec("EVL-043")
def test_agreement_reports_accuracy_and_cohens_kappa():
    human = [True, True, False, False]
    judge = [True, False, False, False]

    result = agreement(list(zip(human, judge, strict=True)))

    assert result.accuracy == 0.75
    assert result.kappa == pytest.approx(0.5)  # po 0.75, pe 0.5
    assert (result.true_accepts, result.false_rejects) == (1, 1)
    assert (result.true_rejects, result.false_accepts) == (2, 0)


@pytest.mark.spec("EVL-043")
def test_kappa_is_zero_without_disagreement_room_rather_than_undefined():
    result = agreement([(True, True), (True, True)])

    assert result.accuracy == 1.0
    assert result.kappa == 0.0  # pe = 1: chance explains everything


def label_line(**fields: object) -> str:
    base: dict[str, object] = {
        "id": "c1/0",
        "claim": "Rent is due on the 5th.",
        "quotes": [{"source": "lease.md", "section": ["Rent"], "quote": "Rent is due on the 5th"}],
        "entailed": True,
        "reviewed": True,
    }
    return json.dumps(base | fields)


@pytest.mark.spec("EVL-043")
def test_labels_are_parsed_with_their_quotes_and_review_status():
    (label,) = parse_labels([label_line(reviewed=False)])

    assert label == Label(
        "c1/0",
        "Rent is due on the 5th.",
        (("lease.md", ("Rent",), "Rent is due on the 5th"),),
        entailed=True,
        reviewed=False,
    )


@pytest.mark.spec("EVL-043")
@pytest.mark.parametrize(
    "fields", [{"entailed": "yes"}, {"claim": ""}, {"quotes": []}, {"id": None}]
)
def test_malformed_labels_are_rejected_with_their_line(fields: dict[str, object]):
    with pytest.raises(DatasetError, match="line 1"):
        parse_labels([label_line(**fields)])
