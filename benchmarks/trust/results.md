# Trust benchmark results

Generated 2026-10-21 on arm64 (Darwin), model `ollama:qwen3.5:9b`, judge {"calibration": "calibrated: kappa 0.74, accuracy 0.87 on 54 labels", "correctness_version": "correctness-v1", "model": "openai:anthropic/claude-sonnet-5.5", "version": "faithfulness-v3"}, dataset `evals/trust-fr/dataset.jsonl` (47 cases, sha256 `a242e6756ed9`).

| Metric | Naive RAG (LangChain) | Soundline, verification off | Soundline |
|---|---|---|---|
| `false_answer_rate` | 0.61 [0.39, 0.83] n=18 | 0.11 [0.00, 0.28] n=18 | 0.11 [0.00, 0.28] n=18 |
| `injection_success_rate` | 0.67 [0.33, 1.00] n=6 | 0.67 [0.33, 1.00] n=6 | 0.67 [0.33, 1.00] n=6 |
| `unflagged_injection_rate` | 0.67 [0.33, 1.00] n=6 | 0.33 [0.00, 0.67] n=6 | 0.33 [0.00, 0.67] n=6 |
| `answer_rate` | 0.97 [0.90, 1.00] n=29 | 0.96 [0.89, 1.00] n=28 | 0.96 [0.89, 1.00] n=28 |
| `faithfulness` | 0.71 [0.59, 0.82] n=39 | 0.71 [0.56, 0.84] n=29 | 0.71 [0.57, 0.85] n=29 |
| `correctness` | 0.89 [0.80, 0.98] n=28 | 0.91 [0.81, 0.98] n=27 | 0.91 [0.81, 0.98] n=27 |
| `shown_citation_validity` | n/a | 0.99 [0.98, 1.00] n=29 | 1.00 [1.00, 1.00] n=29 |
| `shown_support_rate` | n/a | 0.99 [0.98, 1.00] n=29 | 1.00 [1.00, 1.00] n=29 |
| `citation_validity` | n/a | 0.99 [0.98, 1.00] n=29 | 0.99 [0.98, 1.00] n=29 |
| `citation_recall` | n/a | 0.89 [0.79, 1.00] n=28 | 0.89 [0.79, 1.00] n=28 |
| `abstention_precision` | 0.88 [0.62, 1.00] n=8 | 0.94 [0.82, 1.00] n=17 | 0.94 [0.82, 1.00] n=17 |
| `conflict_rate` | 0.00 [0.00, 0.00] n=39 | 0.10 [0.00, 0.24] n=29 | 0.10 [0.00, 0.24] n=29 |

| Per question (p50 / p95) | Naive RAG (LangChain) | Soundline, verification off | Soundline |
|---|---|---|---|
| `latency_ms` | 5,856 / 8,136 | 9,278 / 26,251 | 9,360 / 26,234 |
| `tokens_in` | 1,291 / 1,562 | 2,768 / 3,218 | 2,768 / 3,218 |
| `tokens_out` | 60 / 136 | 162 / 1,083 | 162 / 1,083 |

## Paired comparisons

Comparison of `soundline-verified` against `soundline-unverified` (47 cases, 95% bootstrap intervals, tolerance 0.0)

| metric | baseline | run | difference [95% CI] | verdict |
|---|---|---|---|---|
| abstention_precision | 0.941 | 0.941 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| answer_rate | 0.964 | 0.964 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| approximate_citation_rate | 0.059 | 0.059 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| citation_recall | 0.893 | 0.893 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| citation_validity | 0.992 | 0.992 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| conflict_rate | 0.103 | 0.103 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| correctness | 0.907 | 0.907 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| cost_usd | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | no significant change |
| faithfulness | 0.705 | 0.707 | +0.002 [+0.000, +0.007] | no significant change ⚠️ too few cases |
| false_answer_rate | 0.111 | 0.111 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| generation_error_rate | 0.021 | 0.021 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@1 | 0.586 | 0.586 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@3 | 0.828 | 0.828 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@5 | 0.931 | 0.931 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@10 | 0.966 | 0.966 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| injection_success_rate | 0.667 | 0.667 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| judge_tokens_in | 2392.522 | 2368.870 | -23.652 [-68.304, +0.000] | no significant change ⚠️ too few cases |
| judge_tokens_out | 342.326 | 339.500 | -2.826 [-7.500, +0.000] | no significant change ⚠️ too few cases |
| latency_ms | 11917.727 | 11947.818 | +30.091 [+12.450, +51.204] | regressed ⚠️ too few cases |
| lenient_parse_rate | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | no significant change |
| mrr | 0.708 | 0.708 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| ndcg@1 | 0.586 | 0.586 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| ndcg@3 | 0.706 | 0.706 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| ndcg@5 | 0.751 | 0.751 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| ndcg@10 | 0.761 | 0.761 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| precision@1 | 0.586 | 0.586 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| precision@3 | 0.460 | 0.460 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| precision@5 | 0.366 | 0.366 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| precision@10 | 0.203 | 0.203 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| recall@1 | 0.569 | 0.569 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| recall@3 | 0.828 | 0.828 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| recall@5 | 0.931 | 0.931 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| recall@10 | 0.966 | 0.966 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| shown_citation_validity | 0.992 | 1.000 | +0.008 [+0.000, +0.021] | no significant change ⚠️ too few cases |
| shown_support_rate | 0.994 | 1.000 | +0.006 [+0.000, +0.017] | no significant change ⚠️ too few cases |
| support_rate | 0.994 | 0.994 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| tokens_in | 2689.674 | 2689.674 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| tokens_out | 286.174 | 286.174 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| unflagged_injection_rate | 0.333 | 0.333 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |

Comparison of `soundline-verified` against `naive-langchain` (47 cases, 95% bootstrap intervals, tolerance 0.0)

| metric | baseline | run | difference [95% CI] | verdict |
|---|---|---|---|---|
| abstention_precision | 0.875 | 0.941 | +0.000 [+0.000, +0.000] | no significant change |
| answer_rate | 0.966 | 0.964 | +0.000 [-0.107, +0.107] | no significant change ⚠️ too few cases |
| conflict_rate | 0.000 | 0.103 | +0.107 [+0.000, +0.214] | no significant change |
| correctness | 0.893 | 0.907 | -0.038 [-0.154, +0.058] | no significant change ⚠️ too few cases |
| faithfulness | 0.709 | 0.707 | -0.166 [-0.301, -0.044] | regressed ⚠️ too few cases |
| false_answer_rate | 0.611 | 0.111 | -0.500 [-0.722, -0.278] | improved ⚠️ too few cases |
| injection_success_rate | 0.667 | 0.667 | +0.000 [-0.500, +0.500] | no significant change ⚠️ too few cases |
| judge_tokens_in | 2784.638 | 2368.870 | -393.783 [-998.196, +220.935] | no significant change ⚠️ too few cases |
| judge_tokens_out | 244.277 | 339.500 | +99.457 [-4.717, +223.283] | no significant change ⚠️ too few cases |
| latency_ms | 5958.408 | 11947.818 | +6000.965 [+4539.474, +7683.501] | regressed ⚠️ too few cases |
| tokens_in | 1302.213 | 2689.674 | +1383.304 [+1295.152, +1475.174] | regressed ⚠️ too few cases |
| tokens_out | 66.532 | 286.174 | +220.609 [+145.413, +304.783] | regressed ⚠️ too few cases |
| unflagged_injection_rate | 0.667 | 0.333 | -0.333 [-0.667, +0.000] | no significant change ⚠️ too few cases |
