"""Public contract test suites for Soundline's ports (ADR 0010).

Every adapter, including the fakes in `soundline.testing`, must pass the suite of its port.
Third-party adapters can be verified the same way (API-020)::

    class TestMyIndex(LexicalIndexContract):
        @pytest.fixture
        def index(self) -> LexicalIndex:
            return MyIndex()

Requires pytest.
"""

import pytest

from soundline.application.ports import LexicalIndex
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
