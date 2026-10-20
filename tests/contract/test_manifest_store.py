import pytest

from soundline.adapters.stores.sqlite import SqliteManifestStore, open_database
from soundline.application.ports import ManifestStore
from soundline.testing import InMemoryManifestStore
from soundline.testing.contracts import ManifestStoreContract


class TestInMemoryManifestStore(ManifestStoreContract):
    @pytest.fixture
    def store(self) -> ManifestStore:
        return InMemoryManifestStore()


class TestSqliteManifestStore(ManifestStoreContract):
    @pytest.fixture
    def store(self) -> ManifestStore:
        return SqliteManifestStore(open_database(":memory:"))
