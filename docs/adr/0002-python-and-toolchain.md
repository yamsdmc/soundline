# 0002 — Python 3.12+, uv, strict typing

- Status: Accepted
- Date: 2026-10-20

## Context

The RAG ecosystem (parsers such as Docling and pypdfium2, local embedding and reranking models, evaluation tooling, notebooks) is overwhelmingly Python. The primary audience — application developers and ML engineers — works in Python.

## Decision

- Python **3.12+** (modern generics syntax, `typing.override`, performance improvements).
- **uv** for environments, locking and running; **hatchling** as build backend.
- **pyright in strict mode** over the whole package, with `py.typed` shipped.
- **ruff** for linting and formatting.

## Consequences

- Users on 3.10/3.11 cannot use Soundline. Acceptable for a new project; revisit if adoption demands it.
- Strict typing slows the first lines but makes refactoring — central to TDD — safe and fast.

## Alternatives considered

- **TypeScript**: strong for web developers and a less crowded ecosystem, but weaker for local models, document parsing and evaluation tooling.
- **mypy** instead of pyright: viable; pyright chosen for speed and stricter inference.
