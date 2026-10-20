import pytest

from soundline.application.hybrid_retriever import HybridRetriever
from soundline.domain.chunks import Chunk
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
