# Smoke evaluation

A small, hand-written retrieval dataset that runs on every pull request.

- **Corpus**: 6 short documents written for this project (French and English, sections, a table,
  code, an HTML page). No third-party or private content.
- **Dataset**: 22 questions, one of them unanswerable, labeled by quote (ADR 0008).
- **Embedder**: `hashing:256`, offline and deterministic, so that a red gate always means a code
  change and never a model download or a floating-point difference.

## What it is, and what it is not

It is a **canary**: it catches broken retrieval (chunking, fusion, filters, parsing). It is **not**
a quality benchmark: with 6 documents, finding the right passage in the top 5 is easy, and
21 answerable cases cannot tell a 2-point change from noise. The comparison says so (`too few
cases`). Model-based benchmarks on public datasets come with M5 (EVL-090, EVL-092).

One known miss is kept on purpose: `en-leak` ranks second, because without stemming
"reported" does not match "report" and stop words weigh more in a short chunk (RET-014).

## Commands

```bash
scripts/smoke_eval.sh                    # evaluate and gate against baseline.json
scripts/smoke_eval.sh --update-baseline  # after an intended change; commit the new baseline
```
