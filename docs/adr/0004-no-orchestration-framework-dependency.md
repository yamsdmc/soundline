# 0004 — No dependency on LangChain, LlamaIndex or similar

- Status: Accepted
- Date: 2026-10-20

## Context

General LLM orchestration frameworks offer many integrations but bring large dependency trees, frequent breaking changes and abstractions that obscure exactly what is sent to models. Soundline's value lies in precise control over retrieval, prompts, verification and evaluation.

## Decision

Soundline does not depend on general orchestration frameworks. Provider integrations use official SDKs or plain HTTP, behind Soundline's own narrow ports.

## Consequences

- More integration code to write and maintain, kept small by narrow ports and contract suites.
- Users of those frameworks can still use Soundline as a retriever: thin integration packages (`soundline-langchain`, `soundline-llamaindex`) MAY be published separately, outside the core.

## Alternatives considered

- **Building on LlamaIndex**: fastest start, but the core concepts (nodes, query engines) would constrain the design and the dependency footprint would violate ARC-010.
