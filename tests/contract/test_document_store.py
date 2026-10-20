import pytest

from soundline.adapters.stores.sqlite import SqliteDocumentStore, open_database
from soundline.application.ports import DocumentStore
from soundline.testing import InMemoryDocumentStore
from soundline.testing.contracts import DocumentStoreContract


class TestInMemoryDocumentStore(DocumentStoreContract):
    @pytest.fixture
    def store(self) -> DocumentStore:
        return InMemoryDocumentStore()


class TestSqliteDocumentStore(DocumentStoreContract):
    @pytest.fixture
    def store(self) -> DocumentStore:
        return SqliteDocumentStore(open_database(":memory:"))
