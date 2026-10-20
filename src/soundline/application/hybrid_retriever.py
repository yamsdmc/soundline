from soundline.application.ports import Embedder, LexicalIndex, VectorIndex
from soundline.domain.chunks import Chunk
from soundline.domain.fusion import fuse
from soundline.domain.hits import Hit


class HybridRetriever:
    """Lexical and dense retrieval fused with RRF (RET-030)."""

    def __init__(
        self,
        lexical: LexicalIndex,
        dense: VectorIndex,
        embedder: Embedder,
        first_stage_k: int = 50,
    ) -> None:
        self._lexical = lexical
        self._dense = dense
        self._embedder = embedder
        self._first_stage_k = first_stage_k

    def hits(self, text: str, limit: int) -> list[Hit]:
        rankings = {
            "lexical": self._lexical.search(text, self._first_stage_k),
            "dense": self._dense.search(self._embedder.embed_query(text), self._first_stage_k),
        }
        chunks = {chunk.id: chunk for ranking in rankings.values() for chunk in ranking}
        fused = fuse({name: [chunk.id for chunk in ranking] for name, ranking in rankings.items()})
        return [Hit(chunks[hit.item], hit.score, hit.ranks) for hit in fused[:limit]]

    def search(self, text: str, limit: int) -> list[Chunk]:
        return [hit.chunk for hit in self.hits(text, limit)]
