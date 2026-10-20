import pytest

from soundline.application.hybrid_retriever import HybridRetriever
from soundline.domain.chunks import Chunk
from soundline.domain.errors import ProviderUnavailableError
from soundline.domain.filters import Filter
from soundline.domain.quotes import Span
from soundline.testing import HashingEmbedder, InMemoryIndex, InMemoryVectorIndex


def chunk(source: str, text: str) -> Chunk:
    return Chunk(source=source, text=text, span=Span(0, len(text)))


RENT = chunk("rent.md", "Rent is payable on the 5th.")
FEES = chunk("fees.md", "Late rent incurs a fee.")
PETS = chunk("pets.md", "Dogs are welcome.")


def retriever_with(*chunks: Chunk) -> HybridRetriever:
    embedder = HashingEmbedder(synonyms={"pay": "payable"})
    lexical, dense = InMemoryIndex(), InMemoryVectorIndex(embedder.dimension)
    for c in chunks:
        lexical.add(c)
        dense.add(c, embedder.embed_documents([c.text])[0])
    return HybridRetriever(lexical, dense, embedder)


def test_nothing_indexed_means_no_hits():
    assert retriever_with().hits("rent", limit=5) == []


@pytest.mark.spec("RET-030", "RET-031")
def test_lexical_and_dense_rankings_are_fused():
    hits = retriever_with(RENT, FEES, PETS).hits("When must I pay the rent?", limit=5)

    assert hits[0].chunk == RENT
    assert hits[0].ranks == {"lexical": 1, "dense": 1}


@pytest.mark.spec("RET-031")
def test_a_chunk_found_only_by_meaning_is_still_a_hit():
    hits = retriever_with(RENT, PETS).hits("When must I pay?", limit=5)

    assert hits[0].chunk == RENT
    assert hits[0].ranks["lexical"] is None


def test_search_returns_the_chunks_of_the_hits_so_ask_can_use_it():
    retriever = retriever_with(RENT, FEES)

    assert retriever.search("rent", limit=1) == [retriever.hits("rent", limit=1)[0].chunk]


class UnavailableEmbedder(HashingEmbedder):
    def embed_query(self, text: str) -> tuple[float, ...]:
        raise ProviderUnavailableError("embedding service timed out")


class UnavailableIndex(InMemoryIndex):
    def search(self, text: str, limit: int, filter: Filter | None = None) -> list[Chunk]:
        raise ProviderUnavailableError("lexical index unreachable")


@pytest.mark.spec("RET-034")
def test_search_degrades_to_the_lexical_retriever_when_dense_retrieval_fails():
    lexical, dense = InMemoryIndex(), InMemoryVectorIndex(256)
    lexical.add(RENT)
    retriever = HybridRetriever(lexical, dense, UnavailableEmbedder())

    result = retriever.search_result("rent", limit=5)

    assert [hit.chunk for hit in result.hits] == [RENT]
    assert result.degraded
    assert result.warnings == ["dense retrieval unavailable: embedding service timed out"]


@pytest.mark.spec("RET-034")
def test_search_fails_clearly_when_every_retriever_fails():
    retriever = HybridRetriever(UnavailableIndex(), InMemoryVectorIndex(256), UnavailableEmbedder())

    with pytest.raises(ProviderUnavailableError, match="every retriever failed"):
        retriever.search_result("rent", limit=5)


def test_a_healthy_search_is_not_degraded():
    result = retriever_with(RENT).search_result("rent", limit=5)

    assert not result.degraded
    assert result.warnings == []
