# 00 — Vision

## The problem

Retrieval-augmented generation (RAG) is the dominant pattern for making a language model answer from **your** documents rather than from its training data. The core loop is simple:

```
question → retrieve relevant passages → put them in the prompt → generate an answer
```

The simplicity is deceptive. In production, RAG systems fail quietly:

- **Retrieval misses.** The right passage exists, but it is not retrieved: the wording differs, it contains an exact identifier that embeddings blur, or it was split in half by the chunker.
- **Unfaithful generation.** The passage was retrieved, but the model adds, distorts or invents facts.
- **Unverifiable citations.** "Source: contract.pdf" is not proof. Users cannot check a claim without re-reading the document.
- **No abstention.** When the documents do not contain the answer, the model answers anyway.
- **Unmeasured changes.** Teams tweak chunk sizes, models and prompts by intuition. Regressions ship unnoticed.
- **Silent index corruption.** An embedding model upgrade leaves the index with vectors from two incompatible spaces.
- **Untrusted content treated as instructions.** A document saying "ignore previous instructions" is obeyed.

## The product

**Soundline is an open-source RAG engine for Python that treats trust and measurement as features, not afterthoughts.**

It ingests documents, retrieves evidence with hybrid search, generates answers whose every claim is backed by a **verified quote**, abstains when the evidence is insufficient, and ships with an **evaluation harness** that turns quality into numbers you can gate in CI.

## Principles

These principles arbitrate design decisions. When two options conflict, the higher principle wins.

1. **Correctness over fluency.** A shorter answer with verified citations beats a longer fluent one. Abstaining beats guessing.
2. **Measure, don't guess.** Every retrieval or generation strategy is configurable *and* measurable. A feature that cannot be evaluated is not finished.
3. **Provenance everywhere.** Every piece of text can be traced back to its source document, revision, page and character span. Every index knows exactly how it was built.
4. **Local-first, scale-ready.** The default setup runs on a laptop with no services and no API keys for search. The same API scales to Postgres and hosted model providers.
5. **Small, explicit, typed core.** No magic. No hidden global state. No dependency on large orchestration frameworks. Strict static typing.
6. **Pluggable at the edges, opinionated in the middle.** Providers (models, stores, parsers) are swappable through narrow ports. The pipeline logic has strong, documented defaults.
7. **Documents are data, never instructions.** Content retrieved from documents can never alter the system's behavior.
8. **Deterministic where possible, honest where not.** Same inputs, same configuration → same chunks, same IDs, same rankings. Nondeterminism is confined to model calls (enrichment, rewriting, generation, judges). Caching makes those replayable, and evaluation **measures** their variance instead of hiding it.

## Personas

| Persona | Needs | Primary interface |
|---|---|---|
| **Application developer** building a Q&A or assistant feature into a product | A library with a clean API, sensible defaults, swappable providers, async support | Python API, HTTP server |
| **ML / AI engineer** optimizing quality | Experiments, metrics, datasets, comparisons, explainability of rankings | CLI `eval`, Python API |
| **Power user / researcher** with a pile of PDFs | One command to ingest, one to ask, citations to check | CLI |
| **Agent builder** | Expose a document corpus as a tool to an agent | MCP server |
| **Platform / ops engineer** | Deployment, observability, multi-tenant isolation, cost control | HTTP server, config, OpenTelemetry |
| **Contributor** | Readable code, fast tests, clear spec, clear contribution rules | Repository |

## Goals

**0.1: prove the idea.** A small release that demonstrates the thesis with numbers:

- Ingest plain text, Markdown, HTML and text-layer PDF into a local SQLite index.
- Hybrid retrieval (lexical + dense, RRF) with metadata filters.
- Grounded answers with claim-level, verified, span-resolved citations (schema-based and provider-native), critical-token checks, structured abstention.
- Retrieval and generation evaluation with confidence intervals and CI gates.
- **The trust benchmark** (EVL-092): naive RAG vs Soundline, with and without verification, on answerable, unanswerable and adversarial questions.
- **The citation viewer** (`ask --open`): see every claim next to its highlighted source.
- Python API, CLI, and an MCP server so agents can use a corpus.

**1.0: make it dependable.** Stable API, rerankers, contextual enrichment, async parity, statistical rigor (variance, multiple comparisons, drift), the reusable GitHub Action, citations that survive re-ingestion.

**Later.** HTTP server, PostgreSQL, multi-tenancy, synthetic datasets, more formats. See the scope table in the [spec index](README.md#scope).

## Non-goals

These are explicitly **out of scope**. Saying no keeps the core small.

- **A chat UI.** Soundline is an engine. A minimal demo UI may live in `examples/` but is not part of the product.
- **A general agent framework.** Soundline exposes retrieval to agents (MCP, Python), but it does not orchestrate agents.
- **A vector database.** Soundline uses existing stores. It does not implement ANN indexes.
- **Training or fine-tuning models.**
- **Generic workflow orchestration** (DAG builders, visual pipelines).
- **OCR engines.** Scanned PDFs are supported through an optional OCR-capable parser adapter, not a built-in engine.
- **Every file format under the sun.** Formats beyond the 1.0 list come through the parser port.

## Success criteria

Soundline is successful if:

1. A new user goes from `pip install` to a cited answer on their own documents in **under 5 minutes**, with no API key for ingestion and search (model download time excluded and stated).
2. The trust benchmark (EVL-092) is published with confidence intervals and reproducible with one command. **Whatever its results**, the README reports them honestly. The target: a lower `false_answer_rate` than the naive baseline with no loss of `correctness` beyond tolerance.
3. **100% of displayed citations** exist verbatim in their source, and their critical tokens agree with the model's quote. This holds by construction (INV-GEN-1, INV-GEN-5).
4. The default test suite runs **offline in under 60 seconds** on a laptop.
5. Every public behavior is traceable to a spec ID and at least one test.
