import pytest

from soundline.application.ports import Embedder
from soundline.testing import HashingEmbedder
from soundline.testing.contracts import EmbedderContract


class TestHashingEmbedder(EmbedderContract):
    @pytest.fixture
    def embedder(self) -> Embedder:
        return HashingEmbedder()
