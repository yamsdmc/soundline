# 0001 — Record architecture decisions

- Status: Accepted
- Date: 2026-10-20

## Context

Soundline is an open-source project meant to outlive the memory of any single contributor. Contributors need to know not only *what* the design is, but *why*, so that they can change it safely.

## Decision

Significant decisions are recorded as ADRs in `docs/adr/`, numbered sequentially, using the template in the [index](README.md). A decision is significant if it affects the public API, the architecture's boundaries, stored data, dependencies, or the project's governance.

## Consequences

- Pull requests that make such decisions include an ADR.
- Accepted ADRs are not edited (except typos and links). Changing a decision means writing a superseding ADR.
