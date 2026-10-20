import ast
import sys
from pathlib import Path

import pytest

DOMAIN = Path(__file__).parents[2] / "src" / "soundline" / "domain"


def non_stdlib_imports(source: str) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module)
    return {
        module
        for module in imported
        if module.split(".")[0] not in sys.stdlib_module_names
        and not module.startswith("soundline.domain")
    }


def test_third_party_and_other_layer_imports_are_detected():
    source = (
        "import numpy as np\n"
        "from dataclasses import dataclass\n"
        "from soundline.adapters.sqlite import SqliteStore\n"
        "from soundline.domain.chunk import Chunk\n"
        "from . import fusion\n"
    )

    assert non_stdlib_imports(source) == {"numpy", "soundline.adapters.sqlite"}


@pytest.mark.spec("ARC-001")
@pytest.mark.parametrize(
    "module", sorted(DOMAIN.rglob("*.py")), ids=lambda path: str(path.relative_to(DOMAIN))
)
def test_domain_modules_import_only_the_standard_library_and_the_domain(module: Path):
    assert non_stdlib_imports(module.read_text(encoding="utf-8")) == set()
