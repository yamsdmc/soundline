from types import SimpleNamespace

import pytest

from soundline.adapters.stores.sqlite import choose_binding, open_database


class _Connection:
    def close(self) -> None: ...


class _ConnectionWithExtensions(_Connection):
    def enable_load_extension(self, enabled: bool) -> None: ...


def _binding(connection_type: type[_Connection]) -> SimpleNamespace:
    """A fake DB-API module. Tests must not depend on how the running Python was built:
    some builds (e.g. CI toolcache Pythons on macOS) cannot load SQLite extensions."""

    def connect(path: str) -> _Connection:
        return connection_type()

    return SimpleNamespace(connect=connect)


CAPABLE = _binding(_ConnectionWithExtensions)
ALSO_CAPABLE = _binding(_ConnectionWithExtensions)
NO_EXTENSIONS = _binding(_Connection)


@pytest.mark.spec("ARC-014")
def test_the_first_binding_able_to_load_extensions_is_chosen():
    assert choose_binding((CAPABLE, ALSO_CAPABLE)) is CAPABLE


@pytest.mark.spec("ARC-014")
def test_a_binding_that_cannot_load_extensions_is_skipped_for_the_next_one():
    assert choose_binding((NO_EXTENSIONS, CAPABLE)) is CAPABLE


@pytest.mark.spec("ARC-014")
def test_a_clear_error_is_raised_when_no_binding_can_load_extensions():
    with pytest.raises(RuntimeError, match="no SQLite binding"):
        choose_binding((NO_EXTENSIONS,))


@pytest.mark.spec("ARC-014")
def test_an_opened_database_has_sqlite_vec_loaded_whatever_binding_this_python_needs():
    database = open_database(":memory:")

    assert database.execute("select vec_version()").fetchone()[0].startswith("v")


def test_every_database_of_a_process_uses_the_same_sqlite_binding():
    """Loading sqlite-vec into two different SQLite libraries aborts the process."""
    first, second = open_database(":memory:"), open_database(":memory:")

    assert type(first) is type(second)
