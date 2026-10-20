import pytest

from soundline.adapters.stores.sqlite import SqliteVectorIndex, open_database
from soundline.application.ports import VectorIndex
from soundline.testing import InMemoryVectorIndex
from soundline.testing.contracts import VectorIndexContract


class TestInMemoryVectorIndex(VectorIndexContract):
    @pytest.fixture
    def index(self) -> VectorIndex:
        return InMemoryVectorIndex(dimension=3)


class TestSqliteVectorIndex(VectorIndexContract):
    @pytest.fixture
    def index(self) -> VectorIndex:
        return SqliteVectorIndex(open_database(":memory:"), dimension=3)
