import pytest

from soundline.domain.chunks import Chunk
from soundline.domain.quotes import Span


@pytest.mark.spec("ING-010")
def test_the_same_chunk_always_gets_the_same_id():
    first = Chunk(source="lease.md", text="Rent is due.", span=Span(0, 12))
    again = Chunk(source="lease.md", text="Rent is due.", span=Span(0, 12))

    assert first.id == again.id


@pytest.mark.spec("ING-010")
def test_chunks_differing_by_source_span_or_text_get_different_ids():
    base = Chunk(source="lease.md", text="Rent is due.", span=Span(0, 12))
    variants = [
        Chunk(source="other.md", text="Rent is due.", span=Span(0, 12)),
        Chunk(source="lease.md", text="Rent is due.", span=Span(40, 52)),
        Chunk(source="lease.md", text="Rent is late", span=Span(0, 12)),
    ]

    assert len({base.id, *(variant.id for variant in variants)}) == 4
