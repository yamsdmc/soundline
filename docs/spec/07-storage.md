# 07 — Storage and index lifecycle

## Purpose

Persist documents, chunks, lexical and vector indexes **consistently**, and make every index **self-describing** so that it can never silently mix incompatible data.

## Concepts

Index, manifest, pipeline fingerprint, corpus, document, revision, chunk (see [glossary](01-glossary.md)).

## Logical data model

> **Non-normative.** This model shows what must be persisted, not a schema. Each adapter designs its own tables.

```
Manifest(corpus, schema_version, fingerprint, components{parser…, chunker…, enricher…, embedder{model_id, dimension}},
         created_at, updated_at, stats{documents, chunks, tokens})

Document(id, corpus, source_uri, revision, media_type, metadata, normalized_text, offset_map,
         ingested_at, fingerprint)

Chunk(id, document_id, ordinal, start, end, text, context_prefix, section_path, location, metadata*)
      * inherited from document, denormalized for filtering

LexicalEntry(chunk_id, indexed_text = context_prefix + "\n" + text)
VectorEntry(chunk_id, vector[dimension])
```

The normalized text of each document is **stored**, because quote verification and span resolution need it at query time, without re-reading or re-parsing sources.

## Behaviors

### Manifest and fingerprints

- **STO-001** Each corpus MUST have exactly one manifest, created on first ingestion.
- **STO-002** The pipeline fingerprint is a SHA-256 of a canonical JSON serialization of all components' identities, versions and settings that affect stored data. Settings that only affect query time (k, fusion weights, reranker, prompts) MUST NOT be part of the fingerprint.
- **STO-003** Each component's identity includes a version (e.g. `soundline.chunker.structural@1`). Changing a component's behavior in a way that changes output MUST bump its version. This is enforced by **golden-output tests** per component.
- **STO-004** `soundline inspect manifest` displays the manifest in a readable form.

### Consistency guards

- **STO-010** Ingesting into a corpus whose manifest fingerprint differs from the current configuration's fingerprint MUST fail with `IndexMismatchError` (`index_fingerprint_mismatch`). The message lists which components differ and suggests `soundline reindex`.
- **STO-011** Writing a vector whose dimension differs from the manifest's dimension MUST fail. This guard is independent of the fingerprint check, as a second line of defense.
- **STO-012** Querying with an embedder whose model ID differs from the manifest's MUST fail with `IndexMismatchError` (see RET-020).
- **STO-013** *(Scope: later. Until then, `reindex` rebuilds the corpus in place after confirmation, and searches are unavailable during the rebuild.)* `soundline reindex [--corpus c]` rebuilds a corpus with the current configuration into a **shadow index**, then swaps it atomically. Queries keep using the old index until the swap. Re-parsing is avoided when the parser and normalization versions are unchanged, because normalized text is stored. Re-embedding is avoided when only enrichment-independent parts changed.
- **STO-014** An interrupted reindex leaves the old index intact and the shadow index resumable or discardable (`soundline reindex --abort`).

### Transactions

- **STO-020** Replacing a document (delete old chunks, insert new chunks across document store, lexical index and vector index) MUST be atomic with respect to readers.
- **STO-021** For single-backend adapters (SQLite, PostgreSQL), atomicity uses one database transaction.
- **STO-022** For multi-backend compositions without shared transactions, Soundline MUST use **revision-tagged writes**: new chunks are written under the new revision, the document's `current_revision` pointer is switched in the document store (the commit point), and old revisions are garbage-collected. Readers filter on the current revision.
- **STO-023** A crash between write steps MUST leave the corpus readable at the previous revision. Garbage collection (`soundline gc`) removes orphans and is safe to run at any time.

### Corpora

- **STO-030** Corpora are created implicitly on first ingestion, or explicitly (`soundline corpus create <name>`). Names match `[a-z0-9][a-z0-9_-]{0,62}`.
- **STO-031** Each corpus has its own manifest. Different corpora MAY use different embedders.
- **STO-032** Deleting a corpus removes all its data. It requires explicit confirmation in the CLI (`--yes` for scripts).
- **STO-033** `soundline corpus list` shows corpora with document and chunk counts and fingerprint summaries.

### SQLite adapter (default)

- **STO-040** One SQLite database file per Soundline home (default `./.soundline/index.db`), in WAL mode, holding all corpora.
- **STO-041** Lexical index: FTS5 with the `unicode61` tokenizer (diacritics removal configurable) by default, `trigram` selectable (RET-015). Dense index: `sqlite-vec`.
- **STO-042** Vector search on SQLite is exact (brute force). The documented, benchmarked scale is **about 100k chunks per corpus** with interactive latency. For reference, a full sqlite-vec scan is reported at ~68 ms for 100k vectors of dimension 384 on an Apple M1 Pro, and cost grows linearly with count and dimension. Optional int8 or binary quantization with float rescoring MAY extend this range. Beyond it, the documentation directs users to PostgreSQL. `soundline doctor` warns when a corpus exceeds the documented scale.
- **STO-043** Filters are evaluated in SQL over denormalized chunk metadata, and vector distances are computed over the filtered rows. `vec0` metadata columns MAY be used as an optimization only for what they support (scalar types; `=`, `!=`, `<`, `<=`, `>`, `>=`; at most 16 columns). Lists, `in`/`nin`, `exists`, `or` and `not` are evaluated in SQL outside the KNN constraint. Filter translation MUST be parameterized: no string interpolation of values.

### PostgreSQL adapter

> **Scope: later.** The split store ports and the contract suite are designed with it in mind from 0.1.

- **STO-050** Uses `pgvector` (HNSW index, cosine distance) and PostgreSQL full-text search (`tsvector`, `ts_rank_cd`, or BM25 via an extension when available, detected at startup).
- **STO-051** Metadata stored as `jsonb` with a GIN index. Filters are translated to `jsonb` operators, parameterized.
- **STO-052** Schema created and migrated by Soundline (see below). A configurable schema name allows several Soundline installs in one database.
- **STO-053** HNSW search parameters (`ef_search`) are configurable. Filtered vector search enables iterative index scans when available (pgvector ≥ 0.8, `hnsw.iterative_scan = relaxed_order`, followed by re-sorting by distance). Iterative scans are bounded (`hnsw.max_scan_tuples`) and can still return fewer than `k` rows for very selective filters. The adapter MUST therefore fall back to an exact scan over the filtered rows when the filter's estimated selectivity is below a configurable threshold, or when the ANN pass returns fewer than `k` rows. Conformance is measured by the filtered-recall contract test (RET-041).

### Migrations

- **STO-060** The storage schema is versioned. Opening an index with an older schema version runs migrations automatically **only** when the migration is backwards-compatible and fast. Otherwise, opening fails with instructions to run `soundline migrate`.
- **STO-061** Opening an index created by a **newer** Soundline version MUST fail with a clear message, and never attempt a downgrade.
- **STO-062** Every migration is tested on a fixture database created by the previous release.

### Export and import

> **Scope: later.**

- **STO-070** `soundline export --corpus c <file>` writes a portable archive (JSONL documents and chunks, vectors as binary NumPy-compatible arrays, manifest). `soundline import` restores it into any store adapter with a compatible fingerprint.

## Store contract test suite

Every store adapter, including the in-memory fake, MUST pass the same contract suite, covering:

1. Insert and retrieve a document with its chunks.
2. Replace a document atomically (readers never see a mix).
3. Delete a document and its chunks from all indexes.
4. Lexical search ranks a document containing a rare term first.
5. Vector search returns the nearest vector first.
6. Every filter operator and combinator (shared table-driven cases with expected results).
7. Filtered search behaves as a search over the filtered subset (RET-041): exact equality for exact backends, filtered recall@k ≥ 0.95 for ANN backends, including a filter matching < 1% of chunks.
8. Corpus isolation.
9. Manifest persistence and fingerprint mismatch detection.
10. Dimension guard.
11. Query escaping (hostile lexical queries do not error).
12. Concurrent readers during a write.

## Open questions

- Should Soundline support external vector databases (Qdrant, LanceDB) in 1.0 through the split ports, or only after? Only after, unless contributed with the contract suite passing.
- Should normalized text be compressed in storage (zstd)? Measure size on the benchmark corpus.
