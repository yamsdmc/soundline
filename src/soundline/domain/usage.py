"""Token usage and estimated cost of model calls (GEN-070, EVL-030)."""

from collections.abc import Mapping
from dataclasses import dataclass

_PER_MILLION = 1_000_000
_LOCAL_PROVIDERS = ("ollama:",)  # runs on the user's machine: no per-token price


@dataclass(frozen=True)
class TokenUsage:
    """`input` excludes cached tokens, which are priced apart."""

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            self.input + other.input,
            self.output + other.output,
            self.cache_read + other.cache_read,
            self.cache_write + other.cache_write,
        )

    def __sub__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            self.input - other.input,
            self.output - other.output,
            self.cache_read - other.cache_read,
            self.cache_write - other.cache_write,
        )

    @property
    def total_input(self) -> int:
        return self.input + self.cache_read + self.cache_write


@dataclass(frozen=True)
class Price:
    """USD per million tokens. Cached reads and writes default to the input price."""

    input: float
    output: float
    cache_read: float | None = None
    cache_write: float | None = None

    def cost(self, tokens: TokenUsage) -> float:
        cache_read = self.input if self.cache_read is None else self.cache_read
        cache_write = self.input if self.cache_write is None else self.cache_write
        return (
            tokens.input * self.input
            + tokens.output * self.output
            + tokens.cache_read * cache_read
            + tokens.cache_write * cache_write
        ) / _PER_MILLION


@dataclass(frozen=True)
class StageUsage:
    stage: str
    """`generation`, `generation_retry`; later `rewrite`, `repair` (GEN-070)."""
    model: str
    tokens: TokenUsage
    cost_usd: float | None
    """None when the model has no known price."""


@dataclass(frozen=True)
class Usage:
    stages: tuple[StageUsage, ...] = ()

    @property
    def tokens(self) -> TokenUsage:
        return sum((stage.tokens for stage in self.stages), TokenUsage())

    @property
    def cost_usd(self) -> float | None:
        """Unknown, rather than understated, as soon as one stage has no price."""
        costs = [stage.cost_usd for stage in self.stages]
        if any(cost is None for cost in costs):
            return None
        return sum(cost for cost in costs if cost is not None)


def price_for(model: str, table: Mapping[str, Price]) -> Price | None:
    if model in table:
        return table[model]
    if model.startswith(_LOCAL_PROVIDERS):
        return Price(0.0, 0.0)
    return None
