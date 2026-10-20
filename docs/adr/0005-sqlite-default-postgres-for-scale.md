# 0005 — SQLite by default, PostgreSQL for scale

- Status: Accepted
- Date: 2026-10-20

## Context

The first-run experience must require no services (success criterion 1). Production deployments need concurrency, replication and large-scale vector indexes.

## Decision

- **Default store: SQLite** in a single file, with FTS5 (lexical) and sqlite-vec (dense). One transaction covers documents, chunks and both indexes.
- **Scale store: PostgreSQL** with pgvector (HNSW) and built-in full-text search, again with single-transaction atomicity.
- Both pass the same store contract suite.

## Consequences

- Hybrid search and atomic replacement are simple on both, because each keeps everything in one database.
- SQLite vector search is exact (brute force) and bounded in scale, at about 100k chunks per corpus (STO-042). The documentation states the limits and when to switch.
- sqlite-vec's KNN constraints support only a subset of filter operators, so rich filters are evaluated in SQL (STO-043).
- Some Python builds cannot load SQLite extensions. A fallback binding is required (ARC-014).
- PostgreSQL is scheduled after 1.0 (see the scope table). The split store ports keep the door open.
- Dedicated vector databases are deferred to after 1.0, supported by the split store ports.

## Alternatives considered

- **LanceDB or Chroma as default**: embedded and vector-native, but weaker for transactional updates and full-text search, and they add a second storage engine for documents.
- **Qdrant/Weaviate**: require a running service; poor first-run experience.
