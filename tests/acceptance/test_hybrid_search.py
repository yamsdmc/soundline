import pytest

from soundline import F, Filter, InvalidFilterError, Soundline
from soundline.testing import HashingEmbedder, ScriptedLanguageModel

LEASE = "Rent is payable on the 5th of each month."
INVOICE = "Invoice INV-2024-0042 was issued in March."
PETS = "Dogs and cats are welcome in the garden."


def soundline_with(*documents: tuple[str, str]) -> Soundline:
    embedder = HashingEmbedder(synonyms={"pay": "payable"})
    soundline = Soundline.in_memory(llm=ScriptedLanguageModel(), embedder=embedder)
    for source, text in documents:
        soundline.ingest_text(source, text)
    return soundline


@pytest.mark.spec("RET-002")
def test_searching_an_empty_corpus_returns_no_hits():
    assert soundline_with().search("When must I pay?") == []


@pytest.mark.spec("RET-022", "RET-031")
def test_a_passage_sharing_no_word_with_the_query_is_found_by_meaning():
    soundline = soundline_with(("lease.md", LEASE), ("pets.md", PETS))

    hits = soundline.search("When must I pay?")

    assert hits[0].source == "lease.md"


@pytest.mark.spec("RET-010", "RET-030")
def test_an_exact_identifier_is_found_by_the_lexical_retriever():
    soundline = soundline_with(("lease.md", LEASE), ("invoice.md", INVOICE), ("pets.md", PETS))

    hits = soundline.search("INV-2024-0042")

    assert hits[0].source == "invoice.md"


@pytest.mark.spec("RET-004", "RET-005")
def test_each_hit_explains_its_rank_in_every_retriever():
    soundline = soundline_with(("lease.md", LEASE), ("pets.md", PETS))

    hit = soundline.search("When must I pay?")[0]

    assert hit.text == LEASE
    assert hit.ranks == {"lexical": None, "dense": 1}
    assert hit.score > 0


@pytest.mark.spec("RET-001")
def test_k_limits_the_number_of_hits():
    soundline = soundline_with(*((f"{n}.md", f"Rent note {n}.") for n in range(5)))

    assert len(soundline.search("rent", k=3)) == 3


@pytest.mark.spec("RET-040", "RET-041", "RET-044", "API-002")
@pytest.mark.parametrize(
    "contracts_only",
    [F.eq("type", "contract"), {"eq": ["type", "contract"]}],
    ids=["builder", "canonical-json"],
)
def test_search_can_be_restricted_by_metadata_with_the_builder_or_json(
    contracts_only: Filter | dict[str, object],
):
    embedder = HashingEmbedder()
    soundline = Soundline.in_memory(llm=ScriptedLanguageModel(), embedder=embedder)
    soundline.ingest_text("memo.md", "Rent rent rent: reminders.", metadata={"type": "memo"})
    soundline.ingest_text("lease.md", "Rent is due on the 5th.", metadata={"type": "contract"})

    hits = soundline.search("rent", filters=contracts_only)

    assert [hit.source for hit in hits] == ["lease.md"]


@pytest.mark.spec("RET-043")
def test_a_malformed_filter_is_rejected_before_searching():
    soundline = soundline_with(("lease.md", LEASE))

    with pytest.raises(InvalidFilterError):
        soundline.search("rent", filters={"like": ["type", "con%"]})
