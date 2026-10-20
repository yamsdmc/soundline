import sqlite3

import pytest

from soundline.adapters.stores.sqlite import SqliteLexicalIndex
from soundline.application.ports import LexicalIndex
from soundline.testing import InMemoryIndex
from soundline.testing.contracts import LexicalIndexContract


class TestInMemoryIndex(LexicalIndexContract):
    @pytest.fixture
    def index(self) -> LexicalIndex:
        return InMemoryIndex()


class TestSqliteLexicalIndex(LexicalIndexContract):
    @pytest.fixture
    def index(self) -> LexicalIndex:
        return SqliteLexicalIndex(sqlite3.connect(":memory:"))
