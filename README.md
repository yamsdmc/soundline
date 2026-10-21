# Soundline

> **The eval-first RAG engine. Every answer cited. Every change measured.**

**The model proposes, the code verifies.** A language model is good at reading and phrasing; it is not a source of truth. In Soundline it proposes claims with quotes, and deterministic code checks every quote against the source before anything reaches the user.

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

Three systems answer the same 47 French questions about renting, over the same documents: official service-public.fr fact sheets plus seven planted pages that carry a false fact or an instruction to the assistant ([evals/trust-fr](evals/trust-fr/README.md)). 29 questions are answerable, 18 are not.

1. **Naive RAG**: what a LangChain tutorial builds (1000-character chunks, dense retrieval, free-text answer with `[n]` markers).
2. **Soundline, verification off**: the same pipeline, keeping every quote as the model wrote it.
3. **Soundline**: verified quotes.

All three share the embedder, k = 5 and the model: `qwen3.5:9b` through Ollama, on a laptop (M1 Max). Faithfulness and correctness are judged by Claude Sonnet 5.5, another model family, calibrated on 54 human-reviewed labels (Cohen's κ 0.74, accuracy 0.87). Mean [95% CI] over the cases each metric applies to:

| | Naive RAG | Soundline, verification off | Soundline |
|---|---|---|---|
| False answers to unanswerable questions (n=18) ↓ | 0.61 [0.39, 0.83] | 0.17 [0.00, 0.33] | **0.17** [0.00, 0.33] |
| Injections that reach the answer (n=6) ↓ | 0.67 [0.33, 1.00] | 0.67 [0.33, 1.00] | 0.67 [0.33, 1.00] |
| ... without any warning to the user (n=6) ↓ | 0.67 [0.33, 1.00] | 0.33 [0.00, 0.67] | **0.33** [0.00, 0.67] |
| Answerable questions answered (n=29) ↑ | 0.97 | 0.97 | 0.97 |
| Correctness against reference answers (n=28) ↑ | 0.89 [0.80, 0.98] | 0.88 [0.77, 0.96] | 0.84 [0.71, 0.95] |
| Faithfulness, claim by claim ↑ | **0.71** [0.59, 0.82] | 0.69 [0.54, 0.82] | 0.69 [0.54, 0.82] |
| Citations shown that exist in the source ↑ | not checkable | 0.99 | **1.00** |
| Latency p50 / p95 ↓ | 5.9 s / 8.1 s | 11.1 s / 22.2 s | 11.1 s / 22.2 s |
| Input tokens p50 ↓ | 1,291 | 2,469 | 2,469 |

What this shows, and what it does not:

- **Soundline gives far fewer false answers** (3 of 18 against 11 of 18; paired difference −0.44 [−0.67, −0.22]), **without a significant loss of correctness** (−0.09 [−0.22, +0.02]). **The gain does not come from verification**: Soundline without verification does exactly as well. It comes from the answer protocol (claims tied to evidence, and an explicit way to say the evidence is insufficient).
- **Verification changes almost nothing with this model.** qwen3.5:9b already quotes its sources faithfully (99% of its quotes exist), so there is little to remove. Verification guarantees that what is shown exists, 100% of the time; how often that matters depends on the model, which this run does not measure.
- **Planted content still reaches the answer** in 4 of 6 cases, for all three systems. **A verified quote proves that the source says it, not that the source is right.** What Soundline adds is a warning: when a planted page contradicts an official one, it states both versions, each attributed to its source, and reports `Sources disagree on ...` (GEN-090). It did so on all 4 questions where a planted page contradicts an official one, and on no other. The 2 injections that pass unflagged (a fake winter-truce date, a fake insurance price) have nothing in the documents to contradict them.
- **Soundline's claims are less faithful than they should be, and the comparison flatters the baseline.** Most rejected Soundline claims drop a condition of their quote's section: "the notice is 3 months" from a quote under "Logement vide > Vous vivez seul". The prompt asks to keep such conditions; a 9B model often does not. The baseline is not judged on this at all: its citations are whole 1,000-character chunks with no section titles, so the judge cannot see the conditions it drops. On the cases both systems answered, the judged gap is −0.16 [−0.29, −0.05]. Making claims carry their section's conditions is the next generation improvement.
- **Local judges are not reliable here.** On the same 54 labels, qwen3.5:9b reaches κ 0.27 and gemma3:12b about 0: they see a "Logement meublé" section and still accept a claim that does not say it. Earlier faithfulness numbers judged by them were dropped.
- **The cost**: about 1.9× the latency at the median, 2.7× at p95, and 1.9× the input tokens.
- **Limits**: one generator model, one run, 47 questions (the intervals are wide; 6 injection cases are too few for a firm rate). The reference answers and most labels were drafted by an AI agent under rules the maintainer set (see [evals/logement-fr](evals/logement-fr/README.md)).

Full results, with every paired comparison: [benchmarks/trust/results.md](benchmarks/trust/results.md). Reproduce them: `make bench-trust` (needs [Ollama](https://ollama.com) with `qwen3.5:9b`; the judge defaults to the same model, free but unreliable; `JUDGE=openai:anthropic/claude-sonnet-5.5` with an OpenRouter key in `OPENAI_API_KEY` and `OPENAI_BASE_URL=https://openrouter.ai/api/v1` reproduces the judged numbers, for about $0.90).

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

```python
chat = sl.conversation()  # or `soundline chat`
chat.ask("When is the rent due?")
chat.ask("And if I'm late?")  # understood in context, cited from this turn's evidence only

for event in sl.ask_stream("What about pets?"):  # each claim arrives already verified
    print(event)
```

```bash
soundline eval run datasets/contracts.jsonl
soundline eval gate latest --baseline main --rules gates.toml   # exit 1 on a significant regression
```

Soundline can be used as a **Python library**, a **CLI**, and an **MCP server** for agents.

```bash
pip install "soundline[mcp]"
claude mcp add soundline -- soundline mcp --description "Our lease contracts"
```

The MCP server is read-only: agents get `search` (passages to reason over) and `ask` (one verified answer), with document text returned as labeled, untrusted data.

## Documentation

- [Specification index](docs/spec/README.md): start here
- [Roadmap](docs/spec/12-roadmap.md): what ships in 0.1, 1.0, and later
- [Architecture Decision Records](docs/adr/README.md)
- [Contributing](CONTRIBUTING.md): how we work (strict TDD)

## License

[Apache 2.0](LICENSE)
