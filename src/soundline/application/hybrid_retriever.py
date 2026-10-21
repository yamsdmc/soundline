from collections.abc import Callable

from soundline.application.ports import Embedder, LexicalIndex, Vector, VectorIndex
from soundline.domain.chunks import Chunk
from soundline.domain.errors import ProviderUnavailableError
from soundline.domain.filters import Filter
from soundline.domain.fusion import fuse
from soundline.domain.hits import Hit, SearchResult
from soundline.domain.tracing import Tracer


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

    def search_result(
        self,
        text: str,
        limit: int,
        filter: Filter | None = None,
        tracer: Tracer | None = None,
    ) -> SearchResult:
        """Both retrievers apply the same filter before ranking (RET-041). If one is
        unavailable, the other answers alone and the result says so (RET-034)."""
        tracer = tracer or Tracer()
        rankings: dict[str, list[Chunk]] = {}
        warnings: list[str] = []
        with tracer.span("soundline.search"):
            try:
                with tracer.span("embed query"):
                    query: Vector | None = self._embedder.embed_query(text)
            except ProviderUnavailableError as error:
                query = None
                warnings.append(f"dense retrieval unavailable: {error}")
            retrievers: dict[str, Callable[[], list[Chunk]]] = {
                "lexical": lambda: self._lexical.search(text, self._first_stage_k, filter)
            }
            if query is not None:
                retrievers["dense"] = lambda: self._dense.search(query, self._first_stage_k, filter)
            for name, retrieve in retrievers.items():
                try:
                    with tracer.span(name) as span:
                        rankings[name] = retrieve()
                        span.attributes["hits"] = len(rankings[name])
                except ProviderUnavailableError as error:
                    warnings.append(f"{name} retrieval unavailable: {error}")
            if not rankings:
                raise ProviderUnavailableError(f"every retriever failed: {'; '.join(warnings)}")
            with tracer.span("fuse", method="rrf") as span:
                chunks = {chunk.id: chunk for ranking in rankings.values() for chunk in ranking}
                fused = fuse({n: [chunk.id for chunk in r] for n, r in rankings.items()})
                hits = [Hit(chunks[hit.item], hit.score, hit.ranks) for hit in fused[:limit]]
                span.attributes["hits"] = len(hits)
        return SearchResult(hits, bool(warnings), warnings, tracer.root)

    def hits(self, text: str, limit: int, filter: Filter | None = None) -> list[Hit]:
        return self.search_result(text, limit, filter).hits

    def search(self, text: str, limit: int) -> list[Chunk]:
        return [hit.chunk for hit in self.hits(text, limit)]
