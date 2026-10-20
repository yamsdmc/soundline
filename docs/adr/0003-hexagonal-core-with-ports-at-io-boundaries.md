# 0003 — Hexagonal core with ports only at I/O boundaries

- Status: Accepted
- Date: 2026-10-20

## Context

RAG systems depend on many fast-moving external technologies: model providers, vector stores, parsers. Tests must run offline, fast and deterministically. At the same time, strict TDD requires that internal design emerge from tests, not from up-front diagrams.

## Decision

- Adopt a hexagonal architecture: domain (pure), application (use cases and ports), adapters (driven and driving), single composition root.
- **Ports are defined up front only where the system touches I/O**: parsers, embedders, language models, rerankers, stores, tokenizer, clock, cache, tracer, source reader. They are the seams tests need.
- **No internal abstraction is designed up front.** Inside the domain and application layers, structure emerges through refactoring.
- Layer rules are enforced in CI with `import-linter`.

## Consequences

- Every port needs a fake and a contract suite (see ADR 0010), which is extra work that pays off in fast and reliable tests.
- Port signatures in the spec are hypotheses; the first tests may change them.

## Alternatives considered

- **Layered architecture without ports**: simpler, but makes offline testing depend on mocking libraries at import paths, which is brittle.
- **Designing the full class model first**: contradicts the TDD doctrine and tends to produce speculative abstractions.
