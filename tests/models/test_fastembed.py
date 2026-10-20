import pytest

from soundline.adapters.embedders.fastembed import FastembedEmbedder
from soundline.application.ports import Embedder
from soundline.testing.contracts import EmbedderContract

pytestmark = pytest.mark.models


@pytest.fixture(scope="module")
def small_model() -> FastembedEmbedder:
    """A small English model keeps this run fast; the adapter is model-agnostic."""
    return FastembedEmbedder("BAAI/bge-small-en-v1.5")


class TestFastembedEmbedder(EmbedderContract):
    @pytest.fixture
    def embedder(self, small_model: FastembedEmbedder) -> Embedder:
        return small_model

    def test_the_dimension_is_the_model_s(self, embedder: Embedder) -> None:
        assert embedder.dimension == 384
