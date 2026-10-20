"""Metadata filters: one language for Python, JSON, CLI, HTTP and MCP (RET-040 to RET-044).

Semantics, chosen so that every store can evaluate them identically:
- a condition on a key that a document does not have is false (`ne` and `nin` included);
  only `not` can turn it true;
- values of different types never match (a string is neither greater nor smaller than 2023);
- a list value (e.g. tags) satisfies `eq` when it contains the operand, `in` when it shares
  an element with the operands.
"""

import operator
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

type Scalar = str | int | float | bool
type Metadata = Mapping[str, Scalar | Sequence[str]]
type ComparisonOperator = Literal["eq", "ne", "gt", "gte", "lt", "lte"]
type MembershipOperator = Literal["in", "nin"]

_COMPARISONS: tuple[ComparisonOperator, ...] = ("eq", "ne", "gt", "gte", "lt", "lte")


class InvalidFilterError(ValueError):
    code = "invalid_filter"


class _Combinable:
    def __and__(self, other: "Filter") -> "And":
        return And((cast("Filter", self), other))

    def __or__(self, other: "Filter") -> "Or":
        return Or((cast("Filter", self), other))

    def __invert__(self) -> "Not":
        return Not(cast("Filter", self))


@dataclass(frozen=True)
class Compare(_Combinable):
    op: ComparisonOperator
    key: str
    value: Scalar


@dataclass(frozen=True)
class Member(_Combinable):
    op: MembershipOperator
    key: str
    values: tuple[Scalar, ...]


@dataclass(frozen=True)
class Exists(_Combinable):
    key: str


@dataclass(frozen=True)
class And(_Combinable):
    items: tuple["Filter", ...]


@dataclass(frozen=True)
class Or(_Combinable):
    items: tuple["Filter", ...]


@dataclass(frozen=True)
class Not(_Combinable):
    item: "Filter"


type Filter = Compare | Member | Exists | And | Or | Not


class F:
    """Builder: `F.eq("type", "contract") & F.gte("year", 2023)`."""

    @staticmethod
    def eq(key: str, value: Scalar) -> Compare:
        return Compare("eq", key, value)

    @staticmethod
    def ne(key: str, value: Scalar) -> Compare:
        return Compare("ne", key, value)

    @staticmethod
    def gt(key: str, value: Scalar) -> Compare:
        return Compare("gt", key, value)

    @staticmethod
    def gte(key: str, value: Scalar) -> Compare:
        return Compare("gte", key, value)

    @staticmethod
    def lt(key: str, value: Scalar) -> Compare:
        return Compare("lt", key, value)

    @staticmethod
    def lte(key: str, value: Scalar) -> Compare:
        return Compare("lte", key, value)

    @staticmethod
    def in_(key: str, values: Sequence[Scalar]) -> Member:
        return Member("in", key, tuple(values))

    @staticmethod
    def nin(key: str, values: Sequence[Scalar]) -> Member:
        return Member("nin", key, tuple(values))

    @staticmethod
    def exists(key: str) -> Exists:
        return Exists(key)


def matches(condition: Filter, metadata: Metadata) -> bool:
    match condition:
        case And(items):
            return all(matches(item, metadata) for item in items)
        case Or(items):
            return any(matches(item, metadata) for item in items)
        case Not(item):
            return not matches(item, metadata)
        case Exists(key):
            return key in metadata
        case Member(op, key, values):
            if key not in metadata:
                return False
            shared = any(_equal(metadata[key], value) for value in values)
            return shared if op == "in" else not shared
        case Compare(op, key, value):
            if key not in metadata:
                return False
            return _compare(op, metadata[key], value)


def _same_kind(a: object, b: object) -> bool:
    def kind(x: object) -> str:
        if isinstance(x, bool):
            return "bool"
        return "number" if isinstance(x, int | float) else type(x).__name__

    return kind(a) == kind(b)


def _equal(actual: Scalar | Sequence[str], value: Scalar) -> bool:
    if isinstance(actual, list | tuple):
        return value in actual
    return _same_kind(actual, value) and actual == value


_ORDER: dict[str, Callable[[Any, Any], bool]] = {
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
}


def _compare(op: ComparisonOperator, actual: Scalar | Sequence[str], value: Scalar) -> bool:
    if op in ("eq", "ne"):
        return _equal(actual, value) == (op == "eq")
    if isinstance(actual, list | tuple) or not _same_kind(actual, value):
        return False
    return _ORDER[op](actual, value)


def parse_filter(data: object) -> Filter:
    """Parses the canonical JSON form, e.g. {"and": [{"eq": ["type", "contract"]}, ...]}."""
    if not isinstance(data, Mapping) or len(data) != 1:  # pyright: ignore[reportUnknownArgumentType]
        raise InvalidFilterError(f"a filter is an object with exactly one operator, got {data!r}")
    op, operand = next(iter(cast("Mapping[str, object]", data).items()))
    if op in ("and", "or"):
        if not isinstance(operand, list) or not operand:
            raise InvalidFilterError(f"{op!r} takes a non-empty list of filters")
        items = tuple(parse_filter(item) for item in cast("list[object]", operand))
        return And(items) if op == "and" else Or(items)
    if op == "not":
        return Not(parse_filter(operand))
    if op == "exists":
        if not isinstance(operand, str):
            raise InvalidFilterError("'exists' takes a key")
        return Exists(operand)
    key, value = _key_and_operand(op, operand)
    if op in ("in", "nin"):
        if not isinstance(value, list) or not all(
            _is_scalar(v) for v in cast("list[object]", value)
        ):
            raise InvalidFilterError(f"{op!r} takes a key and a list of values")
        return Member(op, key, tuple(cast("list[Scalar]", value)))
    if op in _COMPARISONS:
        if not _is_scalar(value) or (op in _ORDER and isinstance(value, bool)):
            raise InvalidFilterError(f"{op!r} takes a key and a single comparable value")
        return Compare(op, key, cast("Scalar", value))
    raise InvalidFilterError(f"unknown filter operator {op!r}")


def _key_and_operand(op: str, operand: object) -> tuple[str, object]:
    if (
        not isinstance(operand, list)
        or len(cast("list[object]", operand)) != 2
        or not isinstance(cast("list[object]", operand)[0], str)
    ):
        raise InvalidFilterError(f"{op!r} takes [key, value], got {operand!r}")
    key, value = cast("list[object]", operand)
    return cast("str", key), value


def _is_scalar(value: object) -> bool:
    return isinstance(value, str | int | float | bool)
