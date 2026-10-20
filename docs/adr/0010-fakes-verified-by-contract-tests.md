# 0010 — Fakes over mocks, verified by public contract tests

- Status: Accepted
- Date: 2026-10-20

## Context

Strict TDD needs fast, deterministic tests at every level. Mock-based tests that assert call sequences couple tests to implementation details and break during refactoring, which discourages the refactoring step of TDD. Fakes avoid this, but can drift from real behavior.

## Decision

- Each port has a **fake**: a working, in-memory, deterministic implementation.
- Each port has a **contract test suite**, and every adapter, fakes included, must pass it.
- Fakes and contract suites are **public** (`soundline.testing`), so users can test their applications and third-party adapters with them.

## Consequences

- Tests assert outcomes, not interactions; refactoring stays cheap.
- Writing a fake is real work, but it is shared by all tests and by users.
- A real adapter discrepancy found in production becomes a new contract test, which then protects every adapter.
