# Soundline

> **The eval-first RAG engine. Every answer cited. Every change measured.**

Before sailing into unknown waters, sailors dropped a *sounding line*: a weighted rope marked at regular intervals, to measure depth before committing to a course. Soundline does the same for retrieval-augmented generation: it goes deep into your documents, and it **measures** everything it does.

> **Status: specification phase.** No code yet. The specification in [`docs/spec`](docs/spec/README.md) is the source of truth, and the implementation will be driven test-first from it. Examples below show the **intended** interface. Every number on this page is illustrative until the first benchmark is published.

---

## Why another RAG library?

Building a RAG demo takes an afternoon. Building one you can **trust** is a different job. Most RAG stacks fail in the same ways:

| Common failure | What Soundline does instead |
|---|---|
| Citations that point to a chunk but not to the sentence that supports the claim | **Verified quotes**: every claim cites an exact quote. Soundline checks that the quote exists in the source, that its numbers, dates and identifiers match, and resolves it to a page and character span. Unverifiable claims are dropped, not shown |
| The model answers confidently when the documents say nothing | **Abstention is a first-class result**, with a reason, measured in evals |
| "We changed the chunk size and it *feels* better" | **Eval-first**: datasets, retrieval and generation metrics, confidence intervals, CI regression gates |
| Vectors from two embedding models silently mixed after an upgrade | **Pipeline fingerprinting**: an index knows exactly how it was built and refuses inconsistent writes |
| Pure vector search misses exact identifiers (`INV-2024-0042`) | **Hybrid retrieval**: lexical + dense, fused with RRF |
| Tables shredded by naive chunking | **Structure-aware chunking** that respects headings, tables and code blocks |
| Heavy framework, opaque abstractions | **Small, typed, hexagonal core** with no dependency on LangChain or LlamaIndex |
| Needs a cloud account to try | **Local-first**: one SQLite file and local multilingual embeddings. No API key needed to ingest and search |

**What verification does and does not prove.** A verified citation is guaranteed to exist verbatim in the source, with matching critical tokens. Whether the quote fully *supports* the claim is a judgment, which Soundline **measures** (faithfulness) rather than claims. Some providers now return precise citations natively; Soundline uses them too, and applies the same checks to every model, hosted or local.

## The trust benchmark

The first release ships with a reproducible benchmark comparing, on the same documents and questions (including unanswerable questions and prompt-injection attempts):

1. a naive RAG baseline,
2. Soundline without verification,
3. Soundline with verification.

It reports false-answer rate, faithfulness, correctness, latency and cost, with confidence intervals. One command reproduces it. **Results will be published here as they come out, including where verification does not help.**

## What it will look like

```bash
pip install soundline
soundline init
soundline ingest ./contracts
soundline ask "When is the rent due and what happens if I'm late?" --open
```

```text
Rent is due on the 5th of each month [1]. Payments more than 10 days late
incur a 5% penalty on the monthly amount [2].

[1] lease-2024.pdf, p.3: "Le loyer est payable le 5 de chaque mois"
[2] lease-2024.pdf, p.7: "une pénalité de 5 % du montant mensuel"
```

`--open` opens a self-contained page where each claim sits next to its source page, with the quote highlighted.

```python
from soundline import Soundline

sl = Soundline.open("./.soundline")
answer = sl.ask("When is the rent due?")

answer.status  # ANSWERED | PARTIAL | ABSTAINED
for c in answer.citations:
    print(c.document.source, c.location.page, c.quote)
```

```bash
soundline eval run datasets/contracts.jsonl
soundline eval gate latest --baseline main --rules gates.toml   # exit 1 on a significant regression
```

Soundline can be used as a **Python library**, a **CLI**, and an **MCP server** for agents.

## Documentation

- [Specification index](docs/spec/README.md): start here
- [Roadmap](docs/spec/12-roadmap.md): what ships in 0.1, 1.0, and later
- [Architecture Decision Records](docs/adr/README.md)
- [Contributing](CONTRIBUTING.md): how we work (strict TDD)

## License

[Apache 2.0](LICENSE)
