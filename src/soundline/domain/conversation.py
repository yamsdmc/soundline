"""Conversation history and its budget in the generation prompt (GEN-060 to GEN-064)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Turn:
    """A previous exchange: text only. Citations and evidence are not carried over (GEN-063)."""

    question: str
    answer: str


@dataclass(frozen=True)
class PackedHistory:
    turns: tuple[Turn, ...]
    """Chronological."""
    dropped: int
    """Older turns left out to fit the budget (GEN-062)."""


def conservative_token_count(text: str) -> int:
    """Over-counts on purpose (GEN-064): 2.5 ASCII characters per token, which also covers
    code and accented Latin text, and one token per other character, which covers CJK."""
    ascii_chars = sum(char.isascii() for char in text)
    return -(-ascii_chars * 2 // 5) + (len(text) - ascii_chars)


def pack_history(
    turns: Sequence[Turn],
    budget: int,
    count_tokens: Callable[[str], int] = conservative_token_count,
) -> PackedHistory:
    """Newest turn first until the budget is reached; turns are kept or dropped whole."""
    kept: list[Turn] = []
    used = 0
    for turn in reversed(turns):
        cost = count_tokens(turn.question) + count_tokens(turn.answer)
        if used + cost > budget:
            break
        kept.append(turn)
        used += cost
    return PackedHistory(tuple(reversed(kept)), len(turns) - len(kept))
