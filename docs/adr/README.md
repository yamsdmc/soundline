# Architecture Decision Records

We record significant decisions as [ADRs](https://adr.github.io/) (Michael Nygard's format): context, decision, consequences. ADRs are immutable once accepted; a reversal is a new ADR that supersedes the old one.

| # | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-python-and-toolchain.md) | Python 3.12+, uv, strict typing | Accepted |
| [0003](0003-hexagonal-core-with-ports-at-io-boundaries.md) | Hexagonal core with ports only at I/O boundaries | Accepted |
| [0004](0004-no-orchestration-framework-dependency.md) | No dependency on LangChain, LlamaIndex or similar | Accepted |
| [0005](0005-sqlite-default-postgres-for-scale.md) | SQLite by default, PostgreSQL for scale | Accepted |
| [0006](0006-hybrid-retrieval-with-rrf.md) | Hybrid retrieval fused with RRF by default | Accepted |
| [0007](0007-verified-quote-citations.md) | Structured claims with verified quote citations | Accepted |
| [0008](0008-quote-based-relevance-labels.md) | Label evaluation relevance by quotes, not chunk IDs | Accepted |
| [0009](0009-pipeline-fingerprint.md) | Pipeline fingerprint and refusal of mixed indexes | Accepted |
| [0010](0010-fakes-verified-by-contract-tests.md) | Fakes over mocks, verified by public contract tests | Accepted |
| [0011](0011-apache-2-license.md) | Apache License 2.0 | Accepted |
| [0012](0012-sqlite-binding-with-extension-fallback.md) | SQLite binding: standard library first, `sqlean.py` fallback | Proposed |

## Template

```markdown
# NNNN — Title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context
## Decision
## Consequences
## Alternatives considered
```
