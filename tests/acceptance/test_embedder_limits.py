from collections.abc import Sequence

import pytest

from soundline import Soundline
from soundline.application.ports import Vector
from soundline.testing import HashingEmbedder, ScriptedLanguageModel


class VerboseTokenizerEmbedder(HashingEmbedder):
    """Its tokenizer counts 3 tokens per word, with a 12-token input limit: like a WordPiece
    model on French text, it sees far more tokens than the chunker's own estimate."""

    def __init__(self) -> None:
        super().__init__()
        self.longest_input = 0

    @property
    def max_input_tokens(self) -> int:
        return 12

    def count_tokens(self, text: str) -> int:
        return 3 * len(text.split())

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        self.longest_input = max(self.longest_input, *(self.count_tokens(t) for t in texts))
        return super().embed_documents(texts)


@pytest.mark.spec("ING-041", "ING-072")
def test_chunks_are_sized_to_the_embedder_s_own_input_limit():
    embedder = VerboseTokenizerEmbedder()
    soundline = Soundline.in_memory(llm=ScriptedLanguageModel(), embedder=embedder, max_tokens=384)

    soundline.ingest_text(
        "lease.md", "Rent is due on the 5th of each month. Late rent costs a fee."
    )

    assert embedder.longest_input <= embedder.max_input_tokens
    assert len(soundline.search("rent", k=10)) > 1
