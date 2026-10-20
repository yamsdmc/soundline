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


def test_hashing_embedders_with_different_vectors_have_different_model_ids():
    ids = {
        HashingEmbedder().model_id,
        HashingEmbedder(dimension=128).model_id,
        HashingEmbedder(synonyms={"pay": "payable"}).model_id,
    }

    assert len(ids) == 3
    assert HashingEmbedder().model_id == HashingEmbedder().model_id
