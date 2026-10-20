from soundline.domain.chunks import Chunk
from soundline.domain.quotes import Span
from soundline.testing import InMemoryIndex


def chunk(source: str, text: str) -> Chunk:
    return Chunk(source=source, text=text, span=Span(0, len(text)))


RENT = chunk("lease.md", "Rent is due on the 5th of each month.")
PETS = chunk("rules.md", "Pets are allowed in the garden.")
LATE = chunk("fees.md", "Late rent payments incur a fee when rent is due.")


def test_searching_an_empty_index_finds_nothing():
    assert InMemoryIndex().search("When is rent due?", limit=5) == []


def test_only_chunks_sharing_a_term_with_the_query_are_found():
    index = InMemoryIndex()
    index.add(RENT)
    index.add(PETS)

    assert index.search("monthly RENT?", limit=5) == [RENT]


def test_chunks_sharing_more_query_terms_rank_first_within_the_limit():
    index = InMemoryIndex()
    for c in (PETS, RENT, LATE):
        index.add(c)

    assert index.search("late rent fee", limit=2) == [LATE, RENT]
