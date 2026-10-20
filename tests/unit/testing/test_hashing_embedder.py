from soundline.testing import HashingEmbedder


def cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_texts_without_shared_words_are_unrelated_unless_declared_synonyms():
    plain = HashingEmbedder()
    bilingual = HashingEmbedder(synonyms={"loyer": "rent", "payable": "due"})

    def similarity(embedder: HashingEmbedder) -> float:
        return cosine(embedder.embed_query("loyer payable"), embedder.embed_query("rent due"))

    assert similarity(plain) < 0.5
    assert similarity(bilingual) > 0.99
