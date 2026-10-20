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

from soundline.application.ports import (
    DocumentStore,
    Embedder,
    LexicalIndex,
    ManifestStore,
    StoredDocument,
    Vector,
    VectorIndex,
)
from soundline.domain.chunks import Chunk
from soundline.domain.filters import F
from soundline.domain.manifest import Manifest
from soundline.domain.quotes import Span


def _chunk(source: str, text: str, **metadata: str | int | list[str]) -> Chunk:
    return Chunk(source=source, text=text, span=Span(0, len(text)), metadata=metadata)


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

    @pytest.mark.spec("RET-041")
    def test_a_filtered_search_only_returns_matching_chunks_with_their_metadata(
        self, index: LexicalIndex
    ) -> None:
        lease = _chunk("lease.md", "Rent is due on the 5th.", type="contract", year=2024)
        index.add(lease)
        index.add(_chunk("memo.md", "Rent memo for the team.", type="memo", year=2024))

        assert index.search("rent", limit=5, filter=F.eq("type", "contract")) == [lease]

    @pytest.mark.spec("RET-041")
    def test_a_filtered_search_fills_the_limit_even_when_matches_rank_low_globally(
        self, index: LexicalIndex
    ) -> None:
        for n in range(10):
            index.add(_chunk(f"memo-{n}.md", "Rent rent rent: rent reminders.", type="memo"))
        contracts = [
            _chunk(f"lease-{n}.md", f"Clause {n} mentions rent once.", type="contract")
            for n in range(2)
        ]
        for contract in contracts:
            index.add(contract)

        found = index.search("rent", limit=2, filter=F.eq("type", "contract"))

        assert sorted(found, key=lambda c: c.source) == contracts

    @pytest.mark.spec("ING-009")
    def test_removing_a_source_removes_only_its_chunks(self, index: LexicalIndex) -> None:
        kept = _chunk("rules.md", "Rent goes to the agency.")
        index.add(_chunk("lease.md", "Rent is due on the 5th."))
        index.add(_chunk("lease.md", "Rent is late after 10 days."))
        index.add(kept)

        index.remove("lease.md")

        assert index.search("rent", limit=5) == [kept]


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

    @pytest.mark.spec("ING-073")
    def test_the_model_id_names_the_embedding_space(self, embedder: Embedder) -> None:
        assert isinstance(embedder.model_id, str)
        assert embedder.model_id

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

    @pytest.mark.spec("RET-041")
    def test_a_filtered_search_returns_the_nearest_matching_chunks_even_if_far(
        self, index: VectorIndex
    ) -> None:
        for n in range(10):
            index.add(_chunk(f"memo-{n}.md", f"Memo {n}.", type="memo"), _unit(1, 0.01 * n, 0))
        far = _chunk("lease.md", "Lease.", type="contract", tags=["rent"])
        index.add(far, _unit(0, 0, 1))

        assert index.search(_unit(1, 0, 0), limit=1, filter=F.eq("tags", "rent")) == [far]

    @pytest.mark.spec("ING-009")
    def test_removing_a_source_removes_only_its_chunks(self, index: VectorIndex) -> None:
        kept = _chunk("rules.md", "Rules.")
        index.add(_chunk("lease.md", "Lease."), _unit(1, 0, 0))
        index.add(kept, _unit(0, 1, 0))

        index.remove("lease.md")

        assert index.search(_unit(1, 0, 0), limit=5) == [kept]


class DocumentStoreContract:
    @pytest.fixture
    def store(self) -> DocumentStore:
        raise NotImplementedError

    def test_an_unknown_document_has_no_revision(self, store: DocumentStore) -> None:
        assert store.get("lease.md") is None

    @pytest.mark.spec("ING-008")
    def test_a_saved_document_is_returned_by_its_source(self, store: DocumentStore) -> None:
        lease = StoredDocument("lease.md", revision="r1", text="Rent is due.")
        store.save(lease)

        assert store.get("lease.md") == lease

    @pytest.mark.spec("ING-009")
    def test_saving_a_new_revision_replaces_the_previous_one(self, store: DocumentStore) -> None:
        store.save(StoredDocument("lease.md", revision="r1", text="Rent is due."))
        store.save(StoredDocument("lease.md", revision="r2", text="Rent is late."))

        assert store.get("lease.md") == StoredDocument("lease.md", "r2", "Rent is late.")
        assert store.sources() == ["lease.md"]

    def test_a_removed_document_is_gone(self, store: DocumentStore) -> None:
        store.save(StoredDocument("lease.md", revision="r1", text="Rent is due."))
        store.save(StoredDocument("rules.md", revision="r1", text="No smoking."))

        store.remove("lease.md")

        assert store.get("lease.md") is None
        assert store.sources() == ["rules.md"]


class ManifestStoreContract:
    @pytest.fixture
    def store(self) -> ManifestStore:
        raise NotImplementedError

    @pytest.mark.spec("STO-001")
    def test_a_new_index_has_no_manifest(self, store: ManifestStore) -> None:
        assert store.load() is None

    @pytest.mark.spec("STO-001")
    def test_the_saved_manifest_is_loaded_back(self, store: ManifestStore) -> None:
        manifest = Manifest({"embedder": {"model_id": "hashing:256", "dimension": 256}})
        store.save(manifest)

        assert store.load() == manifest
