# 0006 — Hybrid retrieval fused with RRF by default

- Status: Accepted
- Date: 2026-10-20

## Context

Dense retrieval captures paraphrases but misses exact identifiers, rare terms and names. Lexical retrieval does the reverse. Their scores live on incomparable scales (BM25 is unbounded, cosine is in [-1, 1]), and score distributions vary by query and corpus.

## Decision

Run lexical and dense retrieval by default and fuse with **Reciprocal Rank Fusion** (`k = 60`, equal weights). Weighted score fusion is available as an alternative for experimentation.

## Consequences

- No score calibration needed; RRF depends on ranks only and is robust across corpora.
- RRF scores are not interpretable as relevance probabilities, so relevance-based abstention requires a reranker (GEN-002).
- Defaults remain subject to benchmark evidence (CFG-022).

## Alternatives considered

- **Dense only**: simplest, measurably weaker on identifier-heavy corpora.
- **Learned fusion**: needs training data per corpus; out of scope.
