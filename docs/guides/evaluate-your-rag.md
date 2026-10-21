# Evaluate your RAG

"It looks better, ship it" is how retrieval quality regresses unnoticed. This guide gets you
from zero to a regression gate in CI.

## 1. Start with 15 questions

You do not need hundreds of cases to start. Write 10 to 15 questions your users actually ask,
and for each one, copy the exact sentence from your documents that answers it:

```json
{"id": "rent-due", "question": "When is rent due?", "relevant": [{"source": "lease.md", "quote": "Rent is payable on the 5th of each month"}]}
```

Label relevance by **quote**, not by chunk: your chunking will change, your quotes will not
(ADR 0008). Soundline checks every quote against the index and points at the closest sentence
when one does not match.

Add at least one question your documents **cannot** answer, with `"answerable": false`. A RAG
that never says "I don't know" is not trustworthy.

## 2. Measure

```bash
soundline ingest ./docs
soundline eval run questions.jsonl --name baseline
```

Every metric comes with a 95% confidence interval. Read it before reading the number.

## 3. Know what 15 cases can and cannot tell you

Fifteen cases are enough to **detect breakage**: when retrieval falls apart, recall drops from
1.0 to 0.0 and no interval hides that. They are **not** enough to claim a small improvement:
going from 0.7 to 0.8 on 15 cases is usually noise. `soundline eval compare` says so explicitly
("too few cases") instead of letting you believe it. Grow the dataset when you need to tell
small changes apart.

## 4. Deterministic metrics before judges

Retrieval metrics (recall, MRR, nDCG) and the structural checks of answers (is every citation
verified? how many claims were dropped?) need no language model: they are free, fast and
reproducible. Use LLM judges only for what code cannot decide, such as whether a quote actually
supports a claim.

## 5. Gate it in CI

```toml
# gates.toml
[[rule]]
metric = "recall@5"
max_regression = 0.05
```

```bash
soundline eval run questions.jsonl --name pr
soundline eval gate pr --baseline baseline.json --rules gates.toml   # exit 1 on a regression
```

A rule fails only when the whole confidence interval of the change is beyond its tolerance,
so noise does not block your pull requests, and real regressions do.

This repository does exactly this on every pull request: see `evals/smoke` and
`scripts/smoke_eval.sh`.
