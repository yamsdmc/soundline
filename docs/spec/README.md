# Soundline Specification

This specification is the **source of truth** for Soundline's behavior. It is written to be **driven by tests**, not to dictate an implementation.

## How to read this specification

The specification describes **observable behavior**: what a user, a caller or an operator can see. It deliberately does **not** describe internal classes, function signatures or module layouts beyond the public interfaces and the ports at I/O boundaries. Those must **emerge** through test-driven development (see [11 — Testing strategy](11-testing-strategy.md)).

Each functional chapter follows the same structure:

1. **Purpose**: why this capability exists.
2. **Concepts**: the vocabulary involved (defined in the [glossary](01-glossary.md)).
3. **Behaviors**: numbered, testable statements (`ING-012`, `RET-004`…). Each behavior is written so that it can become one or more acceptance tests. Behavior IDs are stable: they are referenced from tests, ADRs and issues.
4. **Invariants**: properties that must hold for *all* inputs. They are candidates for property-based tests.
5. **Test list**: a starting [test list](https://tidyfirst.substack.com/p/canon-tdd) in the Canon TDD sense. It is a list of scenarios to explore, ordered roughly from simplest to hardest. It is **expected to grow and change** during implementation.
6. **Open questions**: deliberately undecided points.

### Requirement keywords

The keywords **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT** and **MAY** are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

A behavior whose statement is a **MAY** describes an optional capability. It needs tests only once implemented, and spec coverage reports it as `optional` until then.

### Normative and non-normative content

Behaviors (`XXX-nnn`) and invariants (`INV-*`) are **normative**. Everything marked *non-normative*, *hypothesis* or *illustrative* (data shapes, algorithms, layouts, example DSLs) is guidance for the first tests. TDD may replace it, and the behaviors win.

## Scope

The specification describes the destination, not the next release. Every behavior belongs to a scope:

| Scope | Meaning | Contents |
|---|---|---|
| **0.1** | The first public release: small, sharp, demonstrable | Python API, CLI, SQLite store, text/Markdown/HTML parsers and basic PDF (text layer, pages), structural chunking, hybrid RRF retrieval with filters, verified answers (schema and native citations, critical-token check, abstention), retrieval evaluation and deterministic generation metrics, judges for faithfulness and correctness, gates, the **trust benchmark** (EVL-092), the **citation viewer** (CLI-007), MCP server (stdio, `search` and `ask`), the prompt-injection mitigations SEC-001 to SEC-005 |
| **1.0** | Stable API, production-grade single node | Rerankers, contextual enrichment, PDF header and footer detection, CJK tokenizer, run-to-run variance and multiple-comparison corrections, model drift detection, the GitHub Action (EVL-067), citation resolution after re-ingestion (API-016), async API parity, mutation-testing target |
| **later** | Valuable, explicitly deferred | HTTP server and its operations chapter (HTTP-\*, OPS-\*), PostgreSQL (STO-050 to STO-053), multi-tenant ACLs (SEC-011, SEC-012), shadow reindex (STO-013, STO-014), export and import (STO-070), synthetic datasets and review (EVL-080 to EVL-083), judge calibration (EVL-043), sweeps (EVL-070, EVL-071), HTML eval report (EVL-065 HTML part), multi-query, neighbour expansion and diversity (RET-062, RET-063, RET-072), DOCX and Docling, unverified token streaming (GEN-052), MCP resources and HTTP transport, Prometheus metrics, budget guard |

Sections in the scope **later** carry a banner. Spec coverage is computed per scope: 0.1 ships when all 0.1 behaviors are covered.

## Chapters

| # | Chapter | Prefix | Summary |
|---|---|---|---|
| 00 | [Vision](00-vision.md) | — | Problem, principles, personas, non-goals, success criteria |
| 01 | [Glossary](01-glossary.md) | — | Ubiquitous language |
| 02 | [Architecture](02-architecture.md) | `ARC` | Hexagonal core, ports, packaging, dependency rules |
| 03 | [Ingestion](03-ingestion.md) | `ING` | Loading, parsing, normalizing, chunking, enriching, embedding |
| 04 | [Retrieval](04-retrieval.md) | `RET` | Lexical, dense, hybrid fusion, filters, reranking, context assembly |
| 05 | [Grounded generation](05-generation.md) | `GEN` | Answers, verified citations, abstention, streaming, conversations |
| 06 | [Evaluation](06-evaluation.md) | `EVL` | Datasets, metrics, judges, statistics, regression gates |
| 07 | [Storage & index lifecycle](07-storage.md) | `STO` | Stores, manifest, fingerprints, consistency, migrations |
| 08 | [Interfaces](08-interfaces.md) | `API` `CLI` `HTTP` `MCP` | Python API, CLI, HTTP server, MCP server |
| 09 | [Configuration & providers](09-configuration.md) | `CFG` | Config sources, providers, defaults |
| 10 | [Observability, security & operations](10-operations.md) | `OBS` `SEC` `OPS` | Tracing, cost, prompt injection, isolation, limits |
| 11 | [Testing strategy](11-testing-strategy.md) | — | How we do TDD, test doubles, contracts, eval loop |
| 12 | [Roadmap](12-roadmap.md) | — | Milestones from walking skeleton to 1.0 |

## Traceability

Every behavior ID **MUST** be referenced by at least one test once implemented. A test references the behaviors it covers with a marker:

```python
@pytest.mark.spec("ING-007")
def test_reingesting_unchanged_document_is_a_noop(): ...
```

A tooling script (`scripts/spec_coverage.py`, milestone M0) reports behaviors without tests and tests that reference unknown behaviors. The report runs in CI.

## Changing the specification

The specification evolves with the code. A behavior change follows this order:

1. Open a pull request that edits the spec (and, if structural, adds an ADR).
2. Update or add the acceptance test so that it fails (red).
3. Implement (green), then refactor.

A pull request **MUST NOT** change behavior without changing the spec.
