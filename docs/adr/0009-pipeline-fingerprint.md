# 0009 — Pipeline fingerprint and refusal of mixed indexes

- Status: Accepted
- Date: 2026-10-20

## Context

Vectors from different embedding models (or the same model with different preprocessing) live in incompatible spaces. Mixing them in one index silently degrades retrieval with no error. The same applies, less dramatically, to chunks produced by different chunker settings.

## Decision

Each corpus has a manifest holding a **pipeline fingerprint**: a hash of every component identity, version and setting that affects stored data. Writes and queries with a mismatching configuration fail with `IndexMismatchError`. Changing the pipeline requires an explicit `reindex`, which builds a shadow index and swaps it atomically.

## Consequences

- No silent corruption, at the cost of an explicit step after configuration changes.
- Components must bump their version whenever their output changes; golden-output tests enforce this (STO-003).
- Query-time settings stay outside the fingerprint, so retrieval experiments do not require reindexing.
