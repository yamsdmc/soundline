"""Traceability between spec behaviors (docs/spec) and the tests that cover them.

Usage: python scripts/spec_coverage.py [SPEC_DIR] [TESTS_DIR]

Exits with 1 when a test references a behavior ID that the spec does not define.
Uncovered behaviors are reported but do not fail: the spec describes the destination.
"""

import ast
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_DEFINITION = re.compile(r"\*\*([A-Z]{3,4}-\d{3})\*\*")
_MANDATORY = re.compile(r"\b(MUST|SHOULD)\b")
_OPTIONAL = re.compile(r"\bMAY\b")


def defined_behaviors(markdown: str) -> list[str]:
    return _DEFINITION.findall(markdown)


def optional_behaviors(markdown: str) -> set[str]:
    return {
        behavior
        for line in markdown.splitlines()
        for behavior in _DEFINITION.findall(line)
        if _OPTIONAL.search(line) and not _MANDATORY.search(line)
    }


def referenced_behaviors(test_source: str) -> set[str]:
    return {
        argument.value
        for node in ast.walk(ast.parse(test_source))
        if isinstance(node, ast.Call) and _is_spec_marker(node.func)
        for argument in node.args
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
    }


def _is_spec_marker(func: ast.expr) -> bool:
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "spec"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "mark"
    )


@dataclass(frozen=True)
class CoverageReport:
    covered: set[str]
    uncovered: set[str]
    optional_uncovered: set[str]
    unknown: set[str]


def coverage_report(spec_markdowns: Iterable[str], test_sources: Iterable[str]) -> CoverageReport:
    specs = list(spec_markdowns)
    defined = {behavior for markdown in specs for behavior in defined_behaviors(markdown)}
    optional = set[str]().union(*(optional_behaviors(markdown) for markdown in specs))
    referenced = set[str]().union(*(referenced_behaviors(source) for source in test_sources))
    return CoverageReport(
        covered=defined & referenced,
        uncovered=defined - referenced - optional,
        optional_uncovered=(optional & defined) - referenced,
        unknown=referenced - defined,
    )


def main(argv: list[str]) -> int:
    spec_dir = Path(argv[0]) if argv else Path("docs/spec")
    tests_dir = Path(argv[1]) if len(argv) > 1 else Path("tests")
    report = coverage_report(
        (path.read_text(encoding="utf-8") for path in sorted(spec_dir.glob("*.md"))),
        (path.read_text(encoding="utf-8") for path in sorted(tests_dir.rglob("*.py"))),
    )
    mandatory = len(report.covered) + len(report.uncovered)
    print(f"covered:  {len(report.covered)}/{mandatory} mandatory behaviors")
    print(f"optional: {len(report.optional_uncovered)} not yet implemented")
    if report.unknown:
        print(f"unknown behavior IDs referenced by tests: {', '.join(sorted(report.unknown))}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
