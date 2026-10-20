"""Public contract test suites for Soundline's ports (ADR 0010).

Every adapter, including the fakes in `soundline.testing`, must pass the suite of its port.
Third-party adapters can be verified the same way (API-020)::

    class TestMyIndex(LexicalIndexContract):
        @pytest.fixture
        def index(self) -> LexicalIndex:
            return MyIndex()

Requires pytest.
"""

import math

import pytest

from soundline.application.ports import Embedder, LexicalIndex, Vector, VectorIndex
from soundline.domain.chunks import Chunk
from soundline.domain.quotes import Span


def _chunk(source: str, text: str) -> Chunk:
    return Chunk(source=source, text=text, span=Span(0, len(text)))


class LexicalIndexContract:
    @pytest.fixture
    def index(self) -> LexicalIndex:
        raise NotImplementedError

    def test_searching_an_empty_index_finds_nothing(self, index: LexicalIndex) -> None:
        assert index.search("When is rent due?", limit=5) == []

    def test_a_stored_chunk_is_returned_unchanged(self, index: LexicalIndex) -> None:
        rent = Chunk(source="lease.md", text="Rent is due on the 5th.", span=Span(40, 63))
        index.add(rent)

        assert index.search("rent", limit=5) == [rent]

    def test_only_chunks_sharing_a_term_with_the_query_are_found(self, index: LexicalIndex) -> None:
        rent = _chunk("lease.md", "Rent is due on the 5th of each month.")
        index.add(rent)
        index.add(_chunk("rules.md", "Pets are allowed in the garden."))

        assert index.search("monthly RENT", limit=5) == [rent]

    @pytest.mark.spec("RET-010")
    def test_a_chunk_containing_a_rare_exact_identifier_ranks_first(
        self, index: LexicalIndex
    ) -> None:
        invoice = _chunk("invoices.md", "Invoice INV-2024-0042 covers the rent of March.")
        for month in ("January", "February", "April", "May"):
            index.add(_chunk(f"{month}.md", f"The rent of {month} was paid on time."))
        index.add(invoice)

        assert index.search("rent INV-2024-0042", limit=3)[0] == invoice

    @pytest.mark.spec("RET-001")
    def test_no_more_hits_than_the_limit_are_returned(self, index: LexicalIndex) -> None:
        for n in range(5):
            index.add(_chunk(f"{n}.md", f"Rent note number {n}."))

        assert len(index.search("rent", limit=3)) == 3

    @pytest.mark.spec("RET-013")
    @pytest.mark.parametrize("hostile", ['"AND OR ( * :', "NEAR(", "rent*", "-", "''", ""])
    def test_a_query_made_of_operators_or_punctuation_does_not_raise(
        self, index: LexicalIndex, hostile: str
    ) -> None:
        index.add(_chunk("lease.md", "Rent is due on the 5th."))

        index.search(hostile, limit=5)


def _cosine(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class EmbedderContract:
    @pytest.fixture
    def embedder(self) -> Embedder:
        raise NotImplementedError

    def test_vectors_have_the_declared_dimension_and_unit_length(self, embedder: Embedder) -> None:
        vectors = [
            *embedder.embed_documents(["Rent is due on the 5th."]),
            embedder.embed_query("rent"),
        ]

        for vector in vectors:
            assert len(vector) == embedder.dimension
            assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0, rel_tol=1e-3)

    def test_embedding_is_deterministic(self, embedder: Embedder) -> None:
        assert embedder.embed_query("When is rent due?") == embedder.embed_query(
            "When is rent due?"
        )

    def test_a_batch_embeds_each_text_as_it_would_alone(self, embedder: Embedder) -> None:
        texts = ["Rent is due on the 5th.", "Pets are allowed in the garden."]

        batch = embedder.embed_documents(texts)
        alone = [embedder.embed_documents([text])[0] for text in texts]

        for together, single in zip(batch, alone, strict=True):
            assert _cosine(together, single) == pytest.approx(1.0, abs=1e-4)

    @pytest.mark.spec("RET-022")
    def test_a_query_is_closer_to_a_related_passage_than_to_an_unrelated_one(
        self, embedder: Embedder
    ) -> None:
        related, unrelated = embedder.embed_documents(
            ["The rent is due on the 5th of each month.", "Pets are allowed in the garden."]
        )
        query = embedder.embed_query("When is the rent due?")

        assert _cosine(query, related) > _cosine(query, unrelated)


def _unit(*components: float) -> Vector:
    norm = math.sqrt(sum(x * x for x in components))
    return tuple(x / norm for x in components)


class VectorIndexContract:
    """Indexes are built with dimension 3 by the fixture."""

    @pytest.fixture
    def index(self) -> VectorIndex:
        raise NotImplementedError

    def test_searching_an_empty_index_finds_nothing(self, index: VectorIndex) -> None:
        assert index.search(_unit(1, 0, 0), limit=5) == []

    def test_the_nearest_vectors_come_first_and_chunks_are_returned_unchanged(
        self, index: VectorIndex
    ) -> None:
        north = Chunk(source="north.md", text="North.", span=Span(10, 16))
        east = _chunk("east.md", "East.")
        north_east = _chunk("north-east.md", "North-east.")
        index.add(east, _unit(0, 1, 0))
        index.add(north, _unit(1, 0, 0))
        index.add(north_east, _unit(1, 1, 0))

        assert index.search(_unit(1, 0.1, 0), limit=2) == [north, north_east]

    @pytest.mark.spec("RET-001")
    def test_no_more_hits_than_the_limit_are_returned(self, index: VectorIndex) -> None:
        for n in range(5):
            index.add(_chunk(f"{n}.md", f"Note {n}."), _unit(1, n, 0))

        assert len(index.search(_unit(1, 0, 0), limit=3)) == 3

    @pytest.mark.spec("STO-011")
    def test_a_vector_of_the_wrong_dimension_is_rejected(self, index: VectorIndex) -> None:
        with pytest.raises(ValueError, match="dimension"):
            index.add(_chunk("flat.md", "Flat."), _unit(1, 0))
