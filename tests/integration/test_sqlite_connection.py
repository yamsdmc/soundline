import sqlite3
from types import SimpleNamespace

import pytest
import sqlean  # pyright: ignore[reportMissingTypeStubs]

from soundline.adapters.stores.sqlite import open_database


class _ConnectionWithoutExtensions:
    """Mimics sqlite3 builds compiled without extension loading (e.g. some pyenv builds)."""

    def execute(self, sql: str) -> None: ...


def _connect_without_extensions(path: str) -> _ConnectionWithoutExtensions:
    return _ConnectionWithoutExtensions()


NO_EXTENSIONS = SimpleNamespace(connect=_connect_without_extensions)


@pytest.mark.spec("ARC-014")
def test_the_standard_library_binding_is_used_when_it_can_load_sqlite_vec():
    database = open_database(":memory:", bindings=(sqlite3, sqlean))

    assert isinstance(database, sqlite3.Connection)
    assert database.execute("select vec_version()").fetchone()[0].startswith("v")


@pytest.mark.spec("ARC-014")
def test_a_binding_that_cannot_load_extensions_falls_back_to_the_next_one():
    database = open_database(":memory:", bindings=(NO_EXTENSIONS, sqlean))

    assert not isinstance(database, _ConnectionWithoutExtensions)
    assert database.execute("select vec_version()").fetchone()[0].startswith("v")


@pytest.mark.spec("ARC-014")
def test_a_clear_error_is_raised_when_no_binding_can_load_extensions():
    with pytest.raises(RuntimeError, match="no SQLite binding"):
        open_database(":memory:", bindings=(NO_EXTENSIONS,))
