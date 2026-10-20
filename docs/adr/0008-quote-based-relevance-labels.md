# 0008 — Label evaluation relevance by quotes, not chunk IDs

- Status: Accepted
- Date: 2026-10-20

## Context

Many RAG evaluation setups label relevance by chunk ID. Any change in chunking, which is exactly what one wants to evaluate, invalidates the labels.

## Decision

Eval cases label relevant evidence as `(source, exact quote)`. At evaluation time, quotes are resolved to spans in the current index, and a retrieved chunk is relevant if it covers enough of a quote's span (default ≥ 50% of its characters).

## Consequences

- One dataset can compare any chunking strategies and sizes fairly.
- Quotes must remain findable: dataset validation (EVL-002) reports quotes that no longer match after source edits.
- Very large chunks trivially "cover" quotes, which inflates recall. Reports therefore always show chunk size statistics and `precision@k` next to recall.
