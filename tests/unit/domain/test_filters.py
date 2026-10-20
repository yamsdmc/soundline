import pytest

from soundline.domain.filters import F, Filter, InvalidFilterError, matches, parse_filter

CONTRACT_2024 = {"type": "contract", "year": 2024, "tags": ["rent", "lease"], "signed": True}


@pytest.mark.spec("RET-040")
@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        (F.eq("type", "contract"), True),
        (F.eq("type", "invoice"), False),
        (F.ne("type", "invoice"), True),
        (F.in_("type", ["contract", "invoice"]), True),
        (F.nin("type", ["contract", "invoice"]), False),
        (F.gt("year", 2023), True),
        (F.gte("year", 2024), True),
        (F.lt("year", 2024), False),
        (F.lte("year", 2024), True),
        (F.exists("signed"), True),
        (F.exists("expired"), False),
        (F.eq("tags", "rent"), True),  # a list value matches when it contains the operand
        (F.eq("type", "contract") & F.gte("year", 2023), True),
        (F.eq("type", "invoice") | F.gte("year", 2023), True),
        (~F.eq("type", "contract"), False),
    ],
    ids=repr,
)
def test_each_operator_and_combinator_selects_as_specified(condition: Filter, expected: bool):
    assert matches(condition, CONTRACT_2024) is expected


@pytest.mark.spec("RET-043")
@pytest.mark.parametrize(
    "condition",
    [F.eq("unknown", "x"), F.in_("unknown", ["x"]), F.exists("unknown"), F.gt("unknown", 1)],
    ids=repr,
)
def test_conditions_on_an_unknown_key_match_nothing(condition: Filter):
    assert matches(condition, CONTRACT_2024) is False


@pytest.mark.spec("RET-043")
def test_comparing_values_of_different_types_matches_nothing_instead_of_raising():
    assert matches(F.gt("type", 2023), CONTRACT_2024) is False


@pytest.mark.spec("RET-044")
def test_the_canonical_json_form_parses_to_the_same_filter_as_the_builder():
    canonical = {"and": [{"eq": ["type", "contract"]}, {"not": {"lt": ["year", 2023]}}]}

    assert parse_filter(canonical) == F.eq("type", "contract") & ~F.lt("year", 2023)


@pytest.mark.spec("RET-043", "RET-044")
@pytest.mark.parametrize(
    "malformed",
    [
        {"eq": ["type"]},
        {"gt": ["year", [2023]]},
        {"in": ["type", "contract"]},
        {"like": ["type", "con%"]},
        {"and": {"eq": ["type", "contract"]}},
        {"eq": ["type", "contract"], "ne": ["year", 1]},
    ],
    ids=repr,
)
def test_a_malformed_filter_is_rejected_with_a_clear_error(malformed: object):
    with pytest.raises(InvalidFilterError):
        parse_filter(malformed)
