# 06 — Evaluation

## Purpose

Turn RAG quality into **numbers with error bars**, so that every change (chunk size, model, prompt, reranker) can be judged by evidence rather than intuition, and so that regressions are caught in CI.

Evaluation is a first-class feature of Soundline, not a separate tool. It is also how the project itself is developed: the benchmark suite is the third feedback loop next to acceptance and unit tests (see [11 — Testing strategy](11-testing-strategy.md)).

## Concepts

Eval dataset, eval case, relevant quote, run, baseline, judge, regression gate (see [glossary](01-glossary.md)).

## Dataset format

A dataset is a **JSONL** file (one case per line) with an optional header file `<name>.dataset.toml` describing the dataset (name, version, corpus, description, license).

```json
{
  "id": "lease-017",
  "question": "What happens if the rent is paid 15 days late?",
  "answerable": true,
  "relevant": [
    {"source": "lease-2024.pdf", "quote": "une pénalité de 5 % du montant mensuel"},
    {"source": "lease-2024.pdf", "quote": "au-delà de 10 jours de retard"}
  ],
  "reference_answer": "A 5% penalty on the monthly rent applies after 10 days of delay.",
  "tags": ["fr", "multi-hop", "numbers"],
  "filters": null
}
```

- **EVL-001** Relevance MUST be labeled by **quote** (source + exact excerpt), not by chunk ID. This keeps datasets valid across chunking, enrichment and embedding changes.
- **EVL-002** Loading a dataset MUST validate every case. In particular, each relevant quote MUST be found in the indexed corpus, using the same matching ladder as citation verification (GEN chapter). Unfound quotes are reported as dataset errors, with the closest match as a hint.
- **EVL-003** `answerable: false` cases (questions the corpus cannot answer) MUST be supported. They have no relevant quotes. The correct behavior is abstention.
- **EVL-004** Case IDs MUST be unique and stable. They are the join key for run comparisons.
- **EVL-005** Datasets MAY specify per-case filters and conversation history, to evaluate filtered search and follow-ups.

## Metrics

A retrieved chunk is **relevant** to a case if its span overlaps a relevant quote's resolved span by at least `relevance_overlap` (default: it contains ≥ 50% of the quote's characters).

### Retrieval metrics

Computed on the ranked hits of `search` (before context assembly), for configurable `k` values (default 1, 3, 5, 10):

| Metric | Definition |
|---|---|
| `recall@k` | Fraction of the case's relevant quotes covered by the top-k hits |
| `hit_rate@k` | 1 if at least one relevant quote is covered in the top-k, else 0 |
| `precision@k` | Fraction of the top-k hits that are relevant |
| `mrr` | Reciprocal rank of the first relevant hit (0 if none in the top `max_k`) |
| `ndcg@k` | Normalized discounted cumulative gain, binary relevance |
| `evidence_recall` | Fraction of relevant quotes present in the assembled evidence (what the model actually saw) |

- **EVL-010** Retrieval metrics MUST be computable **without any language model**. Retrieval evaluation is cheap, deterministic and runnable in CI on every commit.
- **EVL-011** Retrieval metrics MUST exactly match hand-computed values on the worked examples of the test suite.

### Generation metrics

| Metric | Definition | Method |
|---|---|---|
| `citation_validity` | Fraction of model citations that passed verification (before removal) | deterministic |
| `citation_recall` | Fraction of relevant quotes cited by the answer | deterministic (span overlap) |
| `support_rate` | Fraction of claims with ≥ 1 verified citation | deterministic |
| `faithfulness` | Fraction of claims entailed by their cited quotes | LLM judge |
| `correctness` | Agreement of the answer with the reference answer (rubric score 0–1) | LLM judge |
| `abstention_precision` | Among abstentions, the fraction on unanswerable cases | deterministic |
| `abstention_recall` | Among unanswerable cases, the fraction abstained | deterministic |
| `false_answer_rate` | Among unanswerable cases, the fraction answered | deterministic |
| `approximate_citation_rate` | Fraction of verified citations that needed fuzzy matching (GEN-038) | deterministic |
| `lenient_parse_rate` | Fraction of model outputs that needed the lenient parser (GEN-023) | deterministic |

- **EVL-020** Deterministic generation metrics MUST be computed from the `Answer` structure, without judges.
- **EVL-021** Judge metrics are optional and MUST be enabled explicitly with a judge model.

### Operational metrics

- **EVL-030** Every run MUST record per-case latency (total and per stage, **including citation verification and repair**), token usage and estimated cost, and aggregate them (mean, p50, p95, total). The cost of trust (verification and repair latency and tokens) is thus always visible.

## Judges

- **EVL-040** Each judge is defined by a **versioned rubric prompt** and a model. Judge outputs MUST be structured (score + rationale) and cached by `(judge version, model, inputs)`.
- **EVL-041** Faithfulness is judged **claim by claim** against the claim's cited quotes only, not against the whole document. This keeps the task narrow and reliable.
- **EVL-042** Judges SHOULD use a different model family than the generator when available, and the run report MUST state judge models.
- **EVL-043** **Judge calibration**: `soundline eval calibrate` runs a judge on a human-labeled calibration set and reports agreement (accuracy and Cohen's κ). The report MUST display the judge's calibration status next to judge metrics ("uncalibrated" when unknown).
- **EVL-044** Judges MUST NOT see which configuration produced an answer (blind evaluation). When comparing two runs pairwise, the presentation order is randomized with a recorded seed.

## Statistics

- **EVL-050** Every aggregate metric MUST be reported with a **95% confidence interval**, computed by bootstrap resampling over cases (default 2000 resamples, recorded seed).
- **EVL-051** Comparing two runs on the same dataset MUST use **paired** statistics: per-case differences, bootstrap CI of the mean difference.
- **EVL-052** A metric change is reported as one of: `improved`, `regressed`, or `no significant change`. It is `regressed` only if the upper bound of the CI of the difference is below `−tolerance`, and `improved` symmetrically.
- **EVL-053** Reports MUST show the number of cases next to every metric and warn when a dataset is too small for the requested precision (heuristic: CI half-width > tolerance).
- **EVL-054** **Run-to-run variance.** Model outputs vary between runs even at temperature 0, and case-resampling CIs do not capture this. `eval run --repeats n` executes each case `n` times with the cache bypassed for generation. Reports then show both the between-case CI and the between-repeat variance. A comparison is reported as `no significant change` when the difference lies within the between-repeat noise. Retrieval-only runs are deterministic and need no repeats.
- **EVL-055** **Multiple comparisons.** A gate with several rules applies a Holm–Bonferroni correction across its rules (family-wise error rate 5% by default), so that adding metrics does not inflate false regressions. Reports that show many metrics label unadjusted verdicts as exploratory.
- **EVL-056** **Model drift.** Runs record the model version returned by providers when available, not only the requested name. `compare` warns when two runs used different returned versions of a same-named model, because a provider-side update can masquerade as a code change.

## Runs, reports and regression gates

- **EVL-060** `soundline eval run <dataset> [--config <file>] [--name <name>]` executes every case and stores the run (configuration snapshot, pipeline fingerprint, dataset version **and content hash**, corpus content hash, per-case results, aggregates, code version, timestamp) in the eval store (`.soundline/evals/`).
- **EVL-061** Runs MUST be **reproducible**: model calls are cached by input. Re-running the same run with a warm cache reproduces identical results at zero model cost. `--no-cache` forces fresh calls.
- **EVL-062** `--retrieval-only` runs only search and computes retrieval metrics.
- **EVL-063** `soundline eval compare <run-a> <run-b>` reports metric differences with CIs and verdicts, plus the cases that changed the most (newly failing, newly passing).
- **EVL-064** `soundline eval gate <run> --baseline <run-or-name> --rules <file>` exits with code 1 if any rule fails. Rules are declared as:
  ```toml
  [[rule]]
  metric = "recall@5"
  max_regression = 0.02     # tolerance on the mean difference
  [[rule]]
  metric = "false_answer_rate"
  max_value = 0.05          # absolute ceiling
  ```
- **EVL-065** Reports MUST be available as terminal tables, JSON (machine-readable, stable schema), Markdown (for PR comments) and a standalone HTML file (per-case drill-down: question, hits with explanations, answer, citations, verdicts).
- **EVL-066** A baseline can be promoted by name (`soundline eval baseline set main <run>`), so CI compares against a named reference. `compare` refuses runs whose dataset content hashes differ, unless `--allow-dataset-change` is passed (then only shared case IDs are compared, and the report says so).
- **EVL-067** A reusable **GitHub Action** (`soundline-dev/soundline-eval-action`) runs an eval on a pull request, compares it with a named baseline, and posts or updates **one** PR comment with: the metric differences with CIs and verdicts, the cases that flipped (newly failing or passing) with links to their drill-down, and a **chunk diff** for flipped cases (how the chunks covering their relevant quotes changed). It is usable by any project with a Soundline index, not only Soundline itself.

## Experiments

> **Scope: later.**

- **EVL-070** `soundline eval sweep <dataset> --grid <file>` runs a dataset over a grid of configuration variations (e.g. `chunking.max_tokens = [256, 512, 1024]` × `retrieval.reranker = [none, "bge-reranker"]`) and produces a comparison table.
- **EVL-071** Configurations that only affect retrieval MUST reuse ingestion when the pipeline fingerprint is unchanged. Variations that change the fingerprint build separate, cached indexes.

## Synthetic dataset generation

> **Scope: later.** For 0.1, datasets are hand-written; the smoke and trust datasets are small and reviewed.

- **EVL-080** `soundline eval generate --corpus <c> --n <count>` samples chunks (stratified by document) and asks a language model to produce question + relevant quote(s) + reference answer for each. Generated quotes MUST pass verification, or the case is discarded.
- **EVL-081** Generation MUST support question styles: factual lookup, numeric, multi-hop (two chunks from the same document), paraphrased (low lexical overlap with the source), and **unanswerable** (plausible questions that the corpus does not answer, verified by retrieval that finds nothing relevant).
- **EVL-082** Generated cases MUST be marked `"origin": "synthetic"` and `"reviewed": false`. Reports MUST break metrics down by origin.
- **EVL-083** `soundline eval review <dataset>` offers a terminal workflow to accept, edit or reject cases (sets `reviewed: true`).

## Public benchmark suite

- **EVL-090** The repository MUST ship scripts to download and evaluate on public datasets (initial candidates: BEIR subsets such as SciFact and FiQA for retrieval; a document QA set with PDFs for end-to-end), plus a small committed **smoke dataset** built from permissively licensed documents.
- **EVL-091** Benchmark results for each release MUST be published in the documentation with configuration, hardware, model versions and confidence intervals.
- **EVL-092** **The trust benchmark** (flagship). A committed, reproducible benchmark compares, on the same corpus and questions, including **unanswerable** and **adversarial** (prompt-injection) cases:
  1. a naive RAG baseline (dense-only retrieval, free-text answer with `[n]` markers), built with a popular framework at a pinned version;
  2. Soundline with verification disabled;
  3. Soundline with schema citations and verification;
  4. Soundline with native provider citations and verification (where available).

  It reports `false_answer_rate`, `faithfulness`, `citation_validity`, `correctness`, latency and cost, with CIs, as one table and chart in the README. It runs with one command (`make bench-trust`) and also as a notebook. Its purpose is to **measure** the effect of verification, whatever the result. If verification does not help on some metric, the README says so.

## Invariants

- **INV-EVL-1** All retrieval metrics are in `[0, 1]`. Perfect rankings score 1, and empty rankings score 0.
- **INV-EVL-2** `recall@k` is non-decreasing in `k`.
- **INV-EVL-3** Comparing a run with itself yields zero differences and `no significant change` for every metric.
- **INV-EVL-4** Metrics are invariant to case order.

## Test list (starting point)

1. Loading a valid one-case JSONL dataset.
2. Duplicate case IDs are rejected.
3. A relevant quote absent from the corpus is reported, with the closest match as a hint.
4. `hit_rate@1` on a single case with the relevant chunk first equals 1.
5. `recall@k`, `mrr` and `ndcg@k` match hand-computed values (three worked examples each).
6. A chunk overlapping 40% of a quote is not relevant; one with 60% is (default threshold).
7. Unanswerable case + abstention counts toward `abstention_recall`; an answer counts toward `false_answer_rate`.
8. `citation_recall` from a scripted answer citing one of two relevant quotes equals 0.5.
9. Bootstrap CI with a fixed seed is deterministic, and contains the mean.
10. Paired comparison of a run with itself → no significant change (INV-EVL-3).
11. A clear regression on a synthetic pair of runs → `regressed`, and the gate exits 1.
12. Re-running with a warm cache makes zero model calls and reproduces results.
13. Judge results are cached; the judge prompt contains only the claim and its quotes.
14. JSON report validates against its published schema.
15. Sweep reuses the index when only retrieval settings vary.
16. Synthetic generation discards cases whose quotes fail verification.
17. Properties INV-EVL-1 to INV-EVL-4 (Hypothesis).
18. With `--repeats 3` and a scripted model that varies between repeats, the report shows between-repeat variance.
19. A gate with three rules applies Holm–Bonferroni: a borderline regression on one rule passes after adjustment (worked example).
20. `compare` refuses runs over datasets with different content hashes.
21. Two runs with different provider-returned model versions → drift warning.

## Open questions

- Graded relevance (0–3) in addition to binary: worth the labeling cost?
- Should Soundline export to and import from Ragas / other formats? Probably import/export adapters, after 1.0.
