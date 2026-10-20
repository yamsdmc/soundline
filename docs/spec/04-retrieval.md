# 04 — Retrieval

## Purpose

Given a query, return the passages most likely to contain the answer, **explainably** and **within budget**. Retrieval recall is the ceiling of answer quality: a fact that is not retrieved cannot be cited.

## Concepts

Query, search query, retriever (lexical, dense), candidate, fusion, reranker, hit, explanation, evidence, context window budget (see [glossary](01-glossary.md)).

## Pipeline

```
query
 └─► query processing  (optional rewrite / multi-query / follow-up condensation)
      └─► first stage   lexical top-N  ∥  dense top-N     (same filters, concurrent)
           └─► fusion   RRF → candidates
                └─► rerank (optional) → top-M
                     └─► post-processing  dedupe · neighbour expansion · diversity
                          └─► hits (search)  or  context assembly → evidence (ask)
```

## Behaviors

### Search API contract

- **RET-001** `search(query, k)` returns at most `k` hits, ordered by final score descending.
- **RET-002** Searching an empty corpus returns an empty list. It is not an error.
- **RET-003** Searching a corpus that does not exist raises `NotFoundError` (`corpus_not_found`).
- **RET-004** Every hit exposes the chunk text, the document (ID, source URI, revision, metadata), the section path, the location, the final score, and an **explanation**.
- **RET-005** The explanation of a hit lists, for each stage it went through, the rank and the raw score: `lexical: rank 3, bm25 12.4`, `dense: rank 1, cosine 0.83`, `rrf: 0.0325`, `rerank: 0.91`. A retriever that did not return the chunk is recorded as absent.
- **RET-006** Rankings MUST be deterministic for a given index state, configuration and query. Ties MUST be broken by chunk ID.

### Lexical retrieval

- **RET-010** Lexical retrieval MUST find chunks containing rare exact tokens (identifiers, codes, names) that dense retrieval tends to miss (e.g. `INV-2024-0042`).
- **RET-011** Lexical scoring MUST be BM25 or an equivalent TF-IDF family scorer, as provided by the store.
- **RET-012** Lexical indexing covers the chunk text **and** its context prefix (section path, enrichment).
- **RET-013** User query text MUST be safely escaped for the store's full-text query syntax. A query made of operators or punctuation (`"AND OR ( * :"`) MUST NOT raise an error.
- **RET-014** Language-specific stemming and stop words SHOULD be configurable per corpus. The default is language-agnostic tokenization (no stemming), because a wrong stemmer is worse than none.
- **RET-015** Languages written without spaces (Chinese, Japanese, Thai) are not segmented by word-based full-text tokenizers. For such corpora, a character n-gram lexical tokenizer (e.g. FTS5 `trigram`) MUST be selectable, and the documentation MUST state that lexical retrieval is degraded on them with the default tokenizer.

### Dense retrieval

- **RET-020** Dense retrieval MUST embed the query with `embed_query` of the **same embedder model** recorded in the index manifest. A mismatch raises `IndexMismatchError` (see STO-012).
- **RET-021** Similarity is cosine similarity (vectors normalized at write time). The stored score is the cosine value.
- **RET-022** Dense retrieval MUST find semantically related chunks without lexical overlap (fixture: "When must I pay?" ↔ "Rent is payable on the 5th").

### Hybrid fusion

- **RET-030** By default, Soundline MUST run lexical and dense retrieval, each returning `first_stage_k` candidates (default 50), and fuse them with **Reciprocal Rank Fusion**: `score(c) = Σ_r w_r / (k_rrf + rank_r(c))`, with `k_rrf = 60` and weights `w_r = 1` by default.
- **RET-031** A chunk returned by only one retriever is still a candidate, scored by that retriever's contribution only.
- **RET-032** Retriever weights and `k_rrf` MUST be configurable. Setting a weight to 0 disables that retriever (pure lexical or pure dense mode).
- **RET-033** An alternative fusion, weighted sum of min-max normalized scores, MAY be selected by configuration for experimentation.
- **RET-034** If one retriever fails (provider unavailable), search MUST continue in degraded mode with the other one, record a warning in the trace, and mark the result `degraded: true`. If all retrievers fail, search raises `ProviderUnavailableError`.

### Filters

- **RET-040** Filters on metadata MUST be supported with these operators: `eq`, `ne`, `in`, `nin`, `gt`, `gte`, `lt`, `lte`, `exists`, and the logical combinators `and`, `or`, `not`.
- **RET-041** A filtered search MUST behave **as if retrieval ran only over the chunks matching the filter**: it returns up to `k` matching hits even when matching chunks rank low globally. Post-filtering a global top-N is not conforming.
  - For **exact** search backends, results MUST be identical to a search over the filtered subset.
  - For **approximate** (ANN) backends, this is a recall target: on the shared contract fixtures, filtered recall@k against exact filtered search MUST be ≥ 0.95, **including** highly selective filters (< 1% of chunks match). Adapters reach this however they can, typically by falling back to an exact scan over the filtered rows when the filter is selective.
  - How a store applies filters (native index constraints, SQL pre-selection, exact scan) is an adapter concern, not a spec concern.
- **RET-042** Filters on reserved keys `sl.document_id`, `sl.source`, `sl.media_type`, `sl.ingested_at` MUST be supported.
- **RET-043** Filtering on an unknown key matches nothing (for `eq`, `in`, `exists`) rather than raising. A filter with a type mismatch (`gt` on a string key) raises `InvalidFilterError`.
- **RET-044** The filter language MUST have one canonical JSON form (shared by Python, CLI, HTTP and MCP). The Python API MAY offer a builder:
  ```python
  F.eq("type", "contract") & F.gte("year", 2023)
  ```
  ```json
  {"and": [{"eq": ["type", "contract"]}, {"gte": ["year", 2023]}]}
  ```

### Reranking

- **RET-050** When a reranker is configured, the top `rerank_k` fused candidates (default 30) are reranked, and the final order is the reranker's.
- **RET-051** The reranker receives the chunk text with its context prefix.
- **RET-052** Reranker failure MUST degrade to the fused order with a warning (`degraded: true`).
- **RET-053** A `min_rerank_score` threshold MAY drop hits below it.

### Post-processing

- **RET-060** Overlapping hits from the same document (overlapping spans) MUST be merged into one hit covering the union span, keeping the best score.
- **RET-061** Near-duplicate hits from different documents (same normalized text, e.g. a clause copied across contracts) are **kept**, because their provenance differs. They MAY be grouped in the explanation.
- **RET-062** **Neighbour expansion** (optional): each hit MAY be expanded with up to `n` adjacent chunks of the same section, so the model gets the surrounding context. The hit keeps its original span for scoring and reports the expanded span separately.
- **RET-063** **Diversity** (optional): a per-document cap `max_hits_per_document` MAY limit how many hits one document contributes.

### Query processing

- **RET-070** By default, the search query is the user's query, unchanged.
- **RET-071** **Follow-up condensation**: in a conversation, when history is present, the latest message MUST be rewritten into a standalone search query by the language model ("What about late fees?" → "What are the late fees for rent payment in the lease?"). The rewritten query appears in the trace.
- **RET-072** **Multi-query** (optional): the language model produces up to `n` reformulations. Each is retrieved, and all ranked lists are fused with RRF.
- **RET-073** Query processing failures MUST degrade to the original query with a warning.

### Context assembly (for `ask`)

- **RET-080** Evidence is assembled from hits in rank order until the **context budget** (default 6000 tokens) would be exceeded. A hit that does not fit is skipped, not truncated. Smaller following hits may still fit.
- **RET-081** Evidence items MUST receive short, answer-scoped IDs `E1…En` in rank order.
- **RET-082** Each evidence item presented to the model MUST include its source label (file name, page or section path) and its text. The context prefix is **not** included as quotable text. It MAY appear as a separate, clearly labeled "context" line.
- **RET-083** Evidence ordering in the prompt MAY place the strongest evidence at the beginning and end (mitigating "lost in the middle"). This is configurable and evaluated.

## Invariants

- **INV-RET-1** RRF scores are invariant to the absolute scores of retrievers. Only ranks matter.
- **INV-RET-2** For any candidate set, the output of fusion is a permutation of the union of the inputs (no loss, no duplication).
- **INV-RET-3** A filtered search never returns a hit whose metadata does not satisfy the filter.
- **INV-RET-4** A search in corpus A never returns a chunk of corpus B.
- **INV-RET-5** Total evidence tokens ≤ context budget.
- **INV-RET-6** Monotonicity: adding a retriever with weight 0 never changes the result.

## Test list (starting point)

1. Searching an empty corpus returns no hits.
2. A query that is a word in exactly one ingested chunk returns that chunk first (lexical, fake store).
3. `k` limits the number of hits.
4. RRF: a chunk ranked 1st by both retrievers beats one ranked 1st by only one.
5. RRF: worked example with known ranks produces the exact expected scores (triangulate with three cases).
6. RRF ties are broken by chunk ID.
7. A chunk found only by dense retrieval is still returned (HashingEmbedder fixture with synonyms mapped).
8. Weight 0 on dense equals pure lexical results.
9. An exact identifier query finds its chunk via lexical retrieval, even when dense ranks it low.
10. A query of only punctuation and operators does not raise.
11. `eq` filter restricts results; filtered search still returns `k` hits when enough match.
12. `and` / `or` / `not` combinations (table-driven tests).
13. Unknown key with `eq` → no hits; `gt` on a string key → `InvalidFilterError`.
14. Corpus isolation: identical content in two corpora, search in one returns only its own.
15. Explanation lists ranks and scores per stage, and marks absent retrievers.
16. Dense retriever failure → lexical-only results flagged `degraded`.
17. Reranker reorders candidates; reranker failure keeps fused order with a warning.
18. Overlapping hits from one document are merged.
19. Neighbour expansion adds adjacent chunks within the section only.
20. `max_hits_per_document` caps per-document hits.
21. Context assembly skips a hit that does not fit and includes a later smaller one.
22. Evidence IDs are `E1…En` in rank order.
23. Follow-up condensation sends a standalone query to retrievers (ScriptedLanguageModel).
24. Multi-query fuses all reformulations.
25. Properties INV-RET-1 to INV-RET-6 (Hypothesis).

## Open questions

- Should `first_stage_k` adapt to `k` and the presence of a reranker? Measure.
- Should query-time HyDE (hypothetical document embeddings) be offered? Only behind evaluation evidence.
- Parent-document retrieval (index small chunks, return their section) versus neighbour expansion: one mechanism or both?
