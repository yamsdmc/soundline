import hashlib
import math
import re
from collections.abc import Sequence

from soundline.application.ports import Vector

_TERM = re.compile(r"\w+")


class HashingEmbedder:
    """Fake embedder: deterministic bag-of-words feature hashing, L2-normalized.

    Texts sharing words get higher cosine similarity. `synonyms` maps words onto a shared
    term, so tests can express semantic matches without lexical overlap:
    `HashingEmbedder(synonyms={"loyer": "rent"})`.
    """

    def __init__(self, dimension: int = 256, synonyms: dict[str, str] | None = None) -> None:
        self._dimension = dimension
        self._synonyms: dict[str, str] = synonyms or {}

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> Vector:
        return self._embed(text)

    def _embed(self, text: str) -> Vector:
        vector = [0.0] * self._dimension
        terms: list[str] = _TERM.findall(text.lower())
        for term in terms:
            digest = hashlib.sha256(self._synonyms.get(term, term).encode()).digest()
            sign = 1.0 if digest[4] % 2 else -1.0
            vector[int.from_bytes(digest[:4]) % self._dimension] += sign
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return tuple(x / norm for x in vector)
