# 02 — Architecture

## Purpose

This chapter defines the **boundaries** that Soundline commits to: the dependency rule, the ports at I/O boundaries, and the packaging. Everything *inside* the core (classes, functions, modules) is left to emerge through TDD.

> **Why ports are specified up front while the rest emerges:** ports sit where tests need substitution (network, disk, models, time). Deciding them early lets every test run offline and fast from day one. Their exact method signatures are still **hypotheses**, refined by the first tests that use them.

## Style: hexagonal (ports and adapters)

```
            ┌──────────────────────────────────────────────────────────┐
            │                     Driving adapters                     │
            │   Python API      CLI (Typer)     HTTP (FastAPI)    MCP  │
            └──────────────┬───────────────────────────────────────────┘
                           │ calls use cases
            ┌──────────────▼───────────────────────────────────────────┐
            │                      Application                         │
            │  Ingest · Sync · Search · Ask · Evaluate · Inspect       │
            │  (use cases: orchestration, transactions, tracing)       │
            ├──────────────────────────────────────────────────────────┤
            │                        Domain                            │
            │  Normalization · Chunking · Fusion · Context assembly ·  │
            │  Citation verification · Abstention policy · Metrics ·   │
            │  Statistics · Fingerprints · IDs                         │
            │  (pure Python, no I/O, no third-party runtime deps)      │
            └──────────────┬───────────────────────────────────────────┘
                           │ depends on ports (Protocols)
            ┌──────────────▼───────────────────────────────────────────┐
            │                     Driven adapters                      │
            │ Parsers · Embedders · LLMs · Rerankers · Stores · Tokens │
            │ Clock · Tracer · Cache                                   │
            └──────────────────────────────────────────────────────────┘
```

### Dependency rule

- **ARC-001** The domain layer MUST NOT import from the application, adapters, or any third-party runtime library. Standard library only (plus typing helpers).
- **ARC-002** The application layer MUST depend only on the domain and on ports. It MUST NOT import adapters.
- **ARC-003** Adapters MAY depend on the domain (to build domain objects) and on third-party libraries. They MUST NOT depend on each other.
- **ARC-004** Driving adapters (API, CLI, HTTP, MCP) MUST go through application use cases. They MUST NOT call driven adapters directly.
- **ARC-005** The dependency rule MUST be enforced automatically in CI with `import-linter` contracts.
- **ARC-006** Composition (wiring adapters to ports from configuration) happens in a single **composition root**. No service locator, no global registry lookups in the core.

## Ports

Ports are `typing.Protocol` classes. Each port has:

- a **fake** adapter (in-memory, deterministic) shipped in the package under `soundline.testing`, so that users can test their own integrations too;
- a **contract test suite** that every adapter, including the fake, MUST pass (see [11 — Testing strategy](11-testing-strategy.md)).

The signatures below are **starting hypotheses**. They are shown in Python for precision, but the tests decide their final shape.

### `Parser`

Turns raw bytes into a parsed document (elements + normalized text + offset map).

```python
class Parser(Protocol):
    id: str  # e.g. "soundline.markdown@1"

    def supports(self, media_type: str) -> bool: ...
    def parse(self, raw: bytes, media_type: str, source: SourceUri) -> ParsedDocument: ...
```

Built-in adapters: plain text, Markdown, HTML, PDF (pypdfium2, text layer), DOCX. Optional adapters: Docling (complex PDFs, tables, OCR).

### `Embedder`

```python
class Embedder(Protocol):
    model_id: str  # e.g. "fastembed:intfloat/multilingual-e5-large"
    dimension: int
    max_input_tokens: int

    def count_tokens(self, text: str) -> int: ...  # in the model's own tokenizer
    def embed_documents(self, texts: Sequence[str]) -> list[Vector]: ...
    def embed_query(self, text: str) -> Vector: ...
```

The query/document distinction exists because many models use asymmetric prefixes or instructions (e.g. `query:` / `passage:` for E5 models). Those prefixes count toward `max_input_tokens`, and the adapter accounts for them in `count_tokens`.

`count_tokens` exists because the embedder's input limit is expressed in **its own** tokenizer (WordPiece, SentencePiece…), which can produce far more tokens than a generic tokenizer, especially on non-English text. Chunk sizing against a generic tokenizer alone would cause silent truncation (see ING-041).

Built-in adapters: fastembed (local, default), OpenAI-compatible, Voyage, Cohere. Fake: `HashingEmbedder` (deterministic bag-of-words hashing).

### `LanguageModel`

```python
class LanguageModel(Protocol):
    model_id: str

    def generate(self, request: GenerationRequest) -> GenerationResult: ...
    def stream(self, request: GenerationRequest) -> Iterator[GenerationEvent]: ...
```

`GenerationRequest` carries system prompt, messages, an optional **output schema** (structured output) and sampling settings. `GenerationResult` carries text and/or structured output, token usage and stop reason.

Built-in adapters: Anthropic, OpenAI-compatible (OpenAI, Ollama, vLLM, LM Studio…). Fake: `ScriptedLanguageModel` (returns pre-programmed responses and records requests).

### `Reranker`

```python
class Reranker(Protocol):
    model_id: str

    def rerank(self, query: str, passages: Sequence[str]) -> list[float]: ...
```

Built-in adapters: local cross-encoder (fastembed/sentence-transformers), Cohere, Voyage. Fake: lexical-overlap reranker.

### `Tokenizer`

```python
class Tokenizer(Protocol):
    id: str

    def count(self, text: str) -> int: ...
```

Used for **generation context budgets** and as the unit of chunking settings. Default: a fast approximation (tiktoken `o200k_base`). The value only needs to be stable and roughly proportional to provider token counts. Exact provider counts are not required, and budgets keep a safety margin. Embedder input limits are checked with `Embedder.count_tokens`, never with this port.

### Stores

Storage is split into three ports so that hybrid backends remain possible (e.g. Postgres for documents with an external vector DB), while single-backend adapters implement all three in one transaction.

```python
class DocumentStore(Protocol):  # documents, chunks, manifest; transactional
    ...


class LexicalIndex(Protocol):  # full-text search over chunk text (+ context prefix)
    def search(
        self, corpus: CorpusName, text: str, filters: Filter, limit: int
    ) -> list[ScoredChunkRef]: ...


class VectorIndex(Protocol):  # nearest-neighbour search over chunk embeddings
    def search(
        self, corpus: CorpusName, vector: Vector, filters: Filter, limit: int
    ) -> list[ScoredChunkRef]: ...
```

Plus a `UnitOfWork` that spans the three for atomic document replacement (see [07 — Storage](07-storage.md)).

Built-in adapters: SQLite (sqlite-vec + FTS5; default), PostgreSQL (pgvector + full-text search). Fake: in-memory store implementing all three with brute-force search.

### Supporting ports

| Port | Purpose | Default adapter | Fake |
|---|---|---|---|
| `Clock` | Timestamps (ingestion time, runs) | system UTC clock | `FrozenClock` |
| `Cache` | Content-addressed cache for model calls (enrichment, judges, eval replay) | SQLite file cache | in-memory dict |
| `Tracer` | Spans and events | OpenTelemetry (optional), no-op | `RecordingTracer` |
| `SourceReader` | Reading bytes from source URIs | local filesystem, HTTP(S) | in-memory map |

## Data flow

### Ingestion

```
SourceReader ─► bytes ─► revision hash ─► (unchanged? stop)
   ─► Parser ─► ParsedDocument ─► Chunker (domain) ─► Chunks
   ─► [Enricher (LanguageModel, cached)] ─► context prefixes
   ─► Embedder (batched) ─► vectors
   ─► UnitOfWork: replace document's chunks in DocumentStore + LexicalIndex + VectorIndex
```

### Ask

```
Query ─► [rewrite (LanguageModel)] ─► search query
   ─► LexicalIndex ∥ VectorIndex  (concurrently, same filters)
   ─► Fusion (domain, RRF) ─► [Reranker] ─► dedupe / neighbour expansion
   ─► Context assembly (domain, token budget) ─► Evidence E1..En
   ─► Pre-generation abstention policy (domain)
   ─► LanguageModel (structured output: claims + citations)
   ─► Citation verification (domain) ─► post-generation policy
   ─► Answer
```

## Package layout (non-normative hypothesis)

> Learned in M1: the Python facade lives outside `interfaces/` because, in a library, the facade *is* the composition root (`Soundline.in_memory(...)`, `Soundline.open(...)` wire adapters). Inside `interfaces/` it would have to import adapters, which ARC-004 forbids. CLI, HTTP and MCP call the facade.
>
> This layout only shows where things are expected to land. Only the layer boundaries (ARC-001 to ARC-006) are normative. Modules inside `domain/` and `application/` emerge from refactoring.

```
src/soundline/
  domain/          # pure logic: chunking, fusion, citations, metrics, ids…
  application/     # use cases + ports (Protocols)
  adapters/
    parsers/  embedders/  llms/  rerankers/  stores/  …
  interfaces/
    cli/          # Typer app
    http/         # FastAPI app
    mcp/          # MCP server
  api.py           # Soundline facade (public Python API) = composition root (ARC-006)
  testing/         # public fakes + contract test suites
  config/          # settings models
tests/
  acceptance/      # spec scenarios through public interfaces, fakes only
  unit/            # domain and application
  contract/        # port contract suites applied to each adapter
  integration/     # real adapters (sqlite always; postgres, providers opt-in)
evals/             # datasets, configs and scripts for the quality loop
docs/
```

The layout inside `domain/` and `application/` is **not** prescribed and will emerge.

## Packaging and optional dependencies

- **ARC-010** `pip install soundline` MUST provide the domain, application, SQLite store, text/Markdown/HTML/PDF parsers, local embeddings (fastembed) and the CLI. It MUST NOT require PyTorch.
- **ARC-011** Heavier or provider-specific dependencies MUST be optional extras:

| Extra | Adds |
|---|---|
| `soundline[anthropic]` | Anthropic LLM adapter |
| `soundline[openai]` | OpenAI-compatible LLM and embedding adapters |
| `soundline[postgres]` | PostgreSQL adapter (psycopg 3, pgvector) |
| `soundline[server]` | HTTP server (FastAPI, uvicorn) |
| `soundline[mcp]` | MCP server |
| `soundline[docling]` | Docling parser (complex PDFs, OCR) |
| `soundline[rerank]` | Local cross-encoder rerankers |
| `soundline[otel]` | OpenTelemetry exporter |
| `soundline[all]` | Everything |

- **ARC-012** Importing `soundline` MUST NOT import optional dependencies. Using an adapter whose extra is missing MUST raise an error naming the extra to install.
- **ARC-013** Supported Python versions: 3.12 and later. Fully typed (`py.typed`), checked with pyright in strict mode.
- **ARC-014** The SQLite store MUST work on Python builds whose `sqlite3` module cannot load extensions (e.g. some macOS system and pyenv builds), which would make `sqlite-vec` unusable. Soundline detects this at startup and falls back to a SQLite binding that ships with extension loading enabled (candidates: `sqlean.py`, `apsw`; to be decided by a spike in M0). `soundline doctor` reports which binding is in use. CI MUST cover macOS, Linux and Windows wheels.

## Sync and async

- **ARC-020** Every use case MUST be available in both synchronous and asynchronous forms through the public API.
- **ARC-021** The core is implemented **async-first**. The sync API is a thin wrapper that MUST work both inside and outside an existing event loop (e.g. Jupyter).
- **ARC-022** Independent I/O within a use case (lexical and dense retrieval, embedding batches, parallel enrichment) SHOULD run concurrently, bounded by configurable concurrency limits.

## Errors

- **ARC-030** All errors raised to users derive from `SoundlineError`, with stable subclasses (`ConfigurationError`, `IngestionError`, `IndexMismatchError`, `ProviderError`, `ProviderUnavailableError`, `NotFoundError`…).
- **ARC-031** Errors MUST carry a stable machine-readable `code` (e.g. `index_fingerprint_mismatch`) and a human message that says **what to do next**.
- **ARC-032** Provider errors MUST distinguish **retryable** (rate limit, timeout, 5xx) from **non-retryable** (auth, invalid request) failures. Retryable errors are retried with exponential backoff and jitter, within configurable limits.

## Open questions

- Should the `UnitOfWork` be a port of its own, or a capability of `DocumentStore` that the index ports join? To be decided by the first multi-store test.
- Whether to expose a plugin entry-point mechanism (`soundline.parsers` entry points) in 1.0 or rely on explicit registration only.
