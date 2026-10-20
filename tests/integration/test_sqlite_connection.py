import sqlite3
from types import SimpleNamespace

import pytest
import sqlean  # pyright: ignore[reportMissingTypeStubs]

from soundline.adapters.stores.sqlite import choose_binding, open_database


class _ConnectionWithoutExtensions:
    """Mimics sqlite3 builds compiled without extension loading (e.g. some pyenv builds)."""

    def close(self) -> None: ...


def _connect_without_extensions(path: str) -> _ConnectionWithoutExtensions:
    return _ConnectionWithoutExtensions()


NO_EXTENSIONS = SimpleNamespace(connect=_connect_without_extensions)


@pytest.mark.spec("ARC-014")
def test_the_standard_library_binding_is_chosen_when_it_can_load_extensions():
    assert choose_binding((sqlite3, sqlean)) is sqlite3


@pytest.mark.spec("ARC-014")
def test_a_binding_that_cannot_load_extensions_is_skipped_for_the_next_one():
    assert choose_binding((NO_EXTENSIONS, sqlean)) is sqlean


@pytest.mark.spec("ARC-014")
def test_a_clear_error_is_raised_when_no_binding_can_load_extensions():
    with pytest.raises(RuntimeError, match="no SQLite binding"):
        choose_binding((NO_EXTENSIONS,))


@pytest.mark.spec("ARC-014")
def test_an_opened_database_has_sqlite_vec_loaded():
    database = open_database(":memory:")

    assert database.execute("select vec_version()").fetchone()[0].startswith("v")


def test_every_database_of_a_process_uses_the_same_sqlite_binding():
    """Loading sqlite-vec into two different SQLite libraries aborts the process."""
    first, second = open_database(":memory:"), open_database(":memory:")

    assert type(first) is type(second)
