import pytest
from hypothesis import given
from hypothesis import strategies as st

from soundline.domain.conversation import Turn, conservative_token_count, pack_history


def words(text: str) -> int:
    return len(text.split())


@pytest.mark.spec("GEN-062")
def test_history_keeps_the_newest_turns_that_fit_in_chronological_order():
    turns = [Turn("q1 q1", "a1"), Turn("q2", "a2 a2"), Turn("q3", "a3")]

    packed = pack_history(turns, budget=5, count_tokens=words)

    assert packed.turns == (Turn("q2", "a2 a2"), Turn("q3", "a3"))
    assert packed.dropped == 1


@pytest.mark.spec("GEN-062")
def test_once_a_turn_does_not_fit_older_turns_are_dropped_even_if_smaller():
    turns = [Turn("a", "b"), Turn("long " * 10, "x"), Turn("q", "a")]

    packed = pack_history(turns, budget=4, count_tokens=words)

    assert packed.turns == (Turn("q", "a"),)
    assert packed.dropped == 2


@pytest.mark.spec("GEN-062")
@given(
    st.lists(st.tuples(st.text(max_size=40), st.text(max_size=40)), max_size=8),
    st.integers(min_value=0, max_value=60),
)
def test_packed_history_fits_the_budget_and_is_a_suffix_of_whole_turns(
    pairs: list[tuple[str, str]], budget: int
):
    turns = [Turn(q, a) for q, a in pairs]

    packed = pack_history(turns, budget)

    used = sum(
        conservative_token_count(t.question) + conservative_token_count(t.answer)
        for t in packed.turns
    )
    assert used <= budget
    assert list(packed.turns) == turns[len(turns) - len(packed.turns) :]
    assert packed.dropped == len(turns) - len(packed.turns)


@pytest.mark.spec("GEN-064")
@pytest.mark.parametrize(
    ("text", "at_least"),
    [
        ("Le propriétaire doit rendre le dépôt de garantie", 12),  # o200k: about 10 tokens
        ("賃貸借契約の更新", 8),  # CJK: about one token per character
        ("def f(x): return x**2", 8),
    ],
)
def test_the_conservative_estimate_over_counts_french_cjk_and_code(text: str, at_least: int):
    assert conservative_token_count(text) >= at_least
