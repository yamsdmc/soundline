# 12 — Roadmap

## Strategy

1. **Walking skeleton first**: the thinnest possible end-to-end slice, through the **Python API only**, with fakes behind every port. It fixes the test harness and the first seams before any real complexity.
2. **Measure before optimizing**: retrieval evaluation arrives **before** answer generation, and the trust benchmark is part of the first release, not an afterthought.
3. **Ship a sharp 0.1**: few features, each excellent and demonstrable. Everything else waits behind the [scope table](README.md#scope).

Each milestone lists its scope, the spec IDs it covers, and its **definition of done**.

---

## Release 0.1 — prove the idea

### M0 — Foundations

**Goal:** a repository where writing the first test is frictionless.

- GitHub repository `yamsdmc/soundline`.
- `pyproject.toml` (uv, hatchling), `src/` layout, Python 3.12+, `py.typed`.
- ruff, pyright strict, pytest with plugins, Hypothesis profiles, `pytest-socket`.
- `import-linter` contracts for ARC-001 to ARC-004 (initially trivially satisfied).
- `scripts/spec_coverage.py` and the `spec` pytest marker. Per-scope reporting needs per-behavior scope tags, which are added in M2 when the first 0.1 behaviors land.
- CI (GitHub Actions): lint, types, tests on Python 3.12 and 3.13 × Linux, macOS, Windows.
- **Spike (timeboxed, one day):** SQLite binding with extension loading on all three OSes (ARC-014). The outcome is an ADR.
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue and PR templates, `CHANGELOG.md`.

**Done when:** `uv run pytest` runs green in CI on three operating systems, and the SQLite binding ADR is accepted.

### M1 — Walking skeleton

**Goal:** one acceptance test, through the Python API:

```python
sl = Soundline.in_memory(embedder=HashingEmbedder(), llm=ScriptedLanguageModel(...))
sl.ingest_text("notes.txt", "Rent is due on the 5th.")
answer = sl.ask("When is rent due?")
assert answer.status is AnswerStatus.ANSWERED
assert answer.citations[0].quote == "Rent is due on the 5th"
```

- Whatever minimal code makes it pass: one chunk per document, lexical search in memory, exact-match verification.
- No CLI, no contract suites, no real adapters yet.

**Spec:** ING-001 (in-memory form), ING-040, RET-001, GEN-001, GEN-030, GEN-040.

**Done when:** that test is green, refactored, and the layer rules hold.

### M2 — Real local stack

**Goal:** useful on real Markdown, HTML and text corpora, offline, from the CLI.

- Contract suites for embedder, stores and language model, with fakes passing them.
- SQLite store (FTS5 + sqlite-vec). fastembed adapter, multilingual default (CFG-023).
- Normalization with offset maps (code points and UTF-16), Markdown and HTML parsers, structural chunker with embedder-aware sizing, Hypothesis invariants.
- Hybrid retrieval with RRF, filters (RET-041 semantics), explanations, determinism.
- Manifest, pipeline fingerprint, consistency guards, idempotent re-ingestion, `sync`, atomic replacement.
- CLI: `init`, `ingest`, `sync`, `search`, `inspect`, `doctor`.

**Spec:** ING-001→049 (excluding later-scope), ING-070→083, RET-001→044, RET-060, STO-001→012, STO-020→043, CLI-001→006, CFG-*.

**Done when:** a 1,000-document Markdown corpus ingests and searches offline on all three OSes, with all invariants holding.

### M3 — Retrieval evaluation

- Dataset format, validation and content hashing; quote-based relevance.
- Retrieval metrics, bootstrap CIs, paired comparison, gates, terminal, JSON and Markdown reports.
- Committed smoke dataset (FR and EN). BEIR subset scripts.
- CI job: retrieval eval on every PR, gated against `main`.

**Spec:** EVL-001→011, EVL-050→053, EVL-060→066 (except HTML), EVL-090.

**Done when:** a PR changing `rrf_k` shows a comparison table with CIs in CI.

### M4 — Verified answers

- Anthropic and OpenAI-compatible adapters (structured output, native citations for Anthropic), with cassettes.
- Verification ladder with critical-token agreement, approximate flag, single-evidence rule, claim dropping, PARTIAL and ABSTAINED statuses, lenient parser.
- Prompt templates, versioning, approval tests, multilingual answers.
- Streaming with verified claims (post-generation emission is acceptable, GEN-051 note), conversations and follow-up condensation.
- Usage and cost accounting. CLI `ask` and `chat`.

**Spec:** GEN-001→051, GEN-060→071, RET-070→071, RET-080→083, OBS-020.

**Done when:** INV-GEN-1 and INV-GEN-5 hold on the smoke dataset with real models, and a fully local setup (Ollama) answers with verified citations.

### M5 — Trust benchmark, viewer and MCP (release 0.1)

- Deterministic generation metrics. Judges for faithfulness and correctness, with caching.
- Unanswerable and adversarial (prompt-injection) datasets.
- **Trust benchmark** (EVL-092), with results published in the README, whatever they are.
- **Citation viewer** (`ask --open`, `answer.to_html()`).
- MCP server (stdio): `search`, `ask`, `list_corpora`.
- Documentation site: quickstart, local-only setup, "evaluate your RAG", concepts (why quotes, why RRF, why eval-first).

**Spec:** EVL-020→042, EVL-044, EVL-092, SEC-001→005, CLI-007, MCP-001→002.

**Done when:** `pip install soundline` → `ingest` → `ask --open` works in under 5 minutes on a fresh machine, and `make bench-trust` reproduces the README table.

---

## Release 1.0 — make it dependable

- Rerankers (local multilingual cross-encoder, Cohere, Voyage), each landing **with an evaluation comparison**.
- Contextual enrichment with caching and cost estimates (ING-060→067).
- PDF header and footer detection, CJK lexical tokenizer.
- Statistical rigor: repeats and variance (EVL-054), Holm–Bonferroni gates (EVL-055), model drift (EVL-056).
- The GitHub Action (EVL-067).
- Citation resolution after re-ingestion (API-016).
- Async API parity, API freeze under SemVer.
- Mutation score ≥ 90% in the domain; spec coverage 100% for 0.1 and 1.0 scopes.

## Later (candidates, not commitments)

- HTTP server with auth, jobs, SSE, Prometheus and Docker (HTTP-\*, OPS-\*).
- PostgreSQL adapter, shadow reindex, export and import, multi-tenant ACLs.
- Synthetic dataset generation and review, judge calibration, sweeps, HTML eval report.
- Multi-query, neighbour expansion, diversity.
- DOCX, Docling (complex PDFs, OCR).
- External vector databases (Qdrant, LanceDB) through the split ports.
- NLI-based entailment verification stage.
- Graph-based retrieval for corpus-wide questions; multimodal retrieval.
- Agentic retrieval mode (iterative search driven by the model with Soundline tools).
