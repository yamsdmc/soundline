# 10 — Observability, security and operations

## Observability

### Traces

- **OBS-001** Every use case execution (ingest, search, ask, eval case) produces a **trace**: a tree of spans with names, durations, attributes and events. Span names are documented, and they become stable (public API) once released. The tree below is a non-normative starting point; the names emerge with the stages:
  ```
  soundline.ask
  ├── soundline.query.rewrite
  ├── soundline.retrieve
  │   ├── soundline.retrieve.lexical
  │   ├── soundline.retrieve.dense
  │   │   └── soundline.embed.query
  │   ├── soundline.fuse
  │   └── soundline.rerank
  ├── soundline.context.assemble
  ├── soundline.generate
  ├── soundline.citations.verify
  └── soundline.policy.abstention
  ```
- **OBS-002** With the `otel` extra enabled, traces are exported through OpenTelemetry, following the GenAI semantic conventions for model call attributes (model, token usage, operation name) where applicable.
- **OBS-003** Prompt and completion contents are **not** recorded in exported spans by default (they may contain sensitive document text). Opt-in via `observability.record_content = true`.
- **OBS-004** `--explain` (CLI) and `explain=True` (API) return the trace inline with the result: queries, candidate rankings per stage, evidence, prompt version, verification outcomes, timings, usage.

### Logs and metrics

- **OBS-010** Logs are structured (key/value). JSON format is selectable. Library code MUST NOT configure the root logger. It logs under the `soundline` logger hierarchy.
- **OBS-011** The HTTP server exposes Prometheus-compatible metrics at `/metrics` (when enabled): request counts and latencies per route, model call counts and latencies, token usage and estimated cost per model, abstention rate, degraded result rate.

### Cost accounting

- **OBS-020** Every model call records token usage, and cost is estimated from the price table. Totals are reported per ingestion, per answer, and per eval run.
- **OBS-021** An optional **budget guard** (`max_cost_usd` per ingestion or eval run) stops processing before exceeding the budget, and reports partial results.

## Security

### Threat model (summary)

| Asset | Threat | Mitigation |
|---|---|---|
| Model behavior | **Indirect prompt injection** through ingested documents | SEC-001 to SEC-004 |
| Corpus confidentiality | Cross-corpus or cross-tenant leakage | SEC-010 to SEC-012 |
| Host system | Path traversal, SSRF, decompression bombs, malicious files | SEC-020 to SEC-024 |
| Secrets | Leakage of API keys | CFG-004, SEC-030 |
| Supply chain | Malicious dependencies | SEC-040 to SEC-042 |

### Prompt injection

- **SEC-001** Retrieved content is always wrapped as delimited, labeled data, with instructions that it is untrusted (GEN-010). Delimiters MUST be robust: evidence text containing the delimiter sequence is escaped.
- **SEC-002** Soundline never grants tools, code execution or side effects to the generation model. The model's only output is a structured answer, so a successful injection can at worst degrade the answer, and it cannot act.
- **SEC-003** Citation verification bounds the damage of injection: injected "facts" that are not quoted from evidence are dropped.
- **SEC-004** The benchmark suite MUST include an **adversarial dataset** (documents with embedded instructions, fake system messages, exfiltration attempts via markdown links) with metrics: injection success rate (target 0 on the default configuration) and answer quality impact.
- **SEC-005** Rendered Markdown answers MUST NOT include images or links whose URLs were not present verbatim in the evidence (blocks exfiltration through image URLs in UIs that render Markdown).

### Isolation and access control

- **SEC-010** Corpus isolation is enforced by the store adapters at query level (INV-RET-4, contract-tested), not only by callers.
- **SEC-011** For multi-tenant deployments, **document-level access control** is supported through a reserved metadata key `sl.acl` (list of principals). When the caller's principals are provided, a mandatory filter is injected **inside the use case**, combined with `and` with user filters, and cannot be removed by request parameters.
- **SEC-012** Traces, eval reports and error messages MUST NOT include content from corpora that the caller cannot access.

### Input handling

- **SEC-020** File size, page count, archive expansion ratio and parse time are bounded (configurable) to resist decompression bombs and pathological files. Parsing happens with timeouts.
- **SEC-021** Ingested HTML is parsed without executing scripts and without fetching remote resources.
- **SEC-022** XML-based formats (DOCX) are parsed with external entity resolution disabled (XXE).
- **SEC-023** The CLI resolves paths relative to the invocation directory, does not follow symlinks by default (ING-006), and never writes outside the Soundline home except for explicit output paths.
- **SEC-024** URL ingestion (CLI) blocks private, loopback and link-local addresses by default (SSRF protection), with an opt-out flag.

### Secrets and supply chain

- **SEC-030** Secret values are wrapped in a type that masks itself in `repr`, `str`, logs and serialization.
- **SEC-040** Runtime dependencies are minimal and reviewed. The core installation does not pull large frameworks (ARC-010).
- **SEC-041** Releases are built in CI, published to PyPI with **trusted publishing** (OIDC), with build provenance attestations, and an SBOM attached to GitHub releases.
- **SEC-042** Dependabot (or Renovate) and `pip-audit` run in CI. A `SECURITY.md` defines private vulnerability reporting.

## Operations

> **Scope: later** (follows the HTTP server), except OPS-006 (performance targets), which applies from 0.1.

- **OPS-001** A Docker image (`ghcr.io/soundline-dev/soundline`) runs the HTTP server, non-root, with a read-only root filesystem except for the data volume.
- **OPS-002** Configuration of the container is entirely through environment variables and a mounted config file.
- **OPS-003** `/health` and `/ready` support orchestrator probes. Graceful shutdown finishes in-flight requests within a configurable timeout.
- **OPS-004** Ingestion jobs on the server run in a bounded worker pool. Job state survives restarts when backed by PostgreSQL. With SQLite, in-flight jobs are marked failed on restart and are safely re-runnable (idempotency, ING-007).
- **OPS-005** Backups: documented procedures for SQLite (online backup API, `soundline backup`) and PostgreSQL (standard tooling). Export/import (STO-070) provides portability.
- **OPS-006** Performance targets SHOULD be met on the reference hardware (documented: CPU model, RAM, OS). They are measured by `scripts/bench_perf.py`, which uses a fixed synthetic corpus, warm-up runs excluded, 200 queries, and reports p50 and p95. CI tracks regressions on a smaller fixed micro-benchmark relative to `main` (> 20% slower fails), not against absolute numbers, because CI hardware varies.
  - `search` p95 < 150 ms on 100k chunks, SQLite, local embeddings, no reranker, excluding first model load and query embedding.
  - Ingestion throughput of plain text ≥ 50 pages/s, excluding embedding.
  - Default test suite < 60 s.

## Test list (starting point)

1. `ask` produces a trace with the documented span names in the right hierarchy (`RecordingTracer`).
2. Exported span attributes contain no prompt content by default.
3. Budget guard stops an ingestion before exceeding the budget, and reports partial results.
4. Evidence containing the delimiter sequence is escaped in the prompt.
5. A scripted model output containing a non-evidence image URL → image removed from the Markdown rendering.
6. ACL: a caller with principals `[alice]` never gets chunks with `sl.acl = [bob]`, even with a user filter `or`-ing everything (parametrized over search, ask and MCP).
7. A secret value never appears in `repr`, logs or the output of `config show` and `doctor`.
8. A DOCX with an external entity does not resolve it.
9. A zip bomb DOCX is rejected by the expansion ratio limit.
10. URL ingestion of `http://127.0.0.1` is blocked by default.
