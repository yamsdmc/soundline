# Trust benchmark results

Generated 2026-10-21 on arm64 (Darwin), model `ollama:qwen3.5:9b`, judge {"calibration": "uncalibrated", "model": "ollama:qwen3.5:9b", "version": "faithfulness-v2"}, dataset `evals/trust-fr/dataset.jsonl` (47 cases, sha256 `88532805a4a4`).

| Metric | Naive RAG (LangChain) | Soundline, verification off | Soundline |
|---|---|---|---|
| `false_answer_rate` | 0.61 [0.39, 0.83] n=18 | 0.17 [0.00, 0.33] n=18 | 0.17 [0.00, 0.33] n=18 |
| `injection_success_rate` | 0.67 [0.33, 1.00] n=6 | 0.67 [0.33, 1.00] n=6 | 0.67 [0.33, 1.00] n=6 |
| `unflagged_injection_rate` | 0.67 [0.33, 1.00] n=6 | 0.33 [0.00, 0.67] n=6 | 0.33 [0.00, 0.67] n=6 |
| `answer_rate` | 0.97 [0.90, 1.00] n=29 | 0.97 [0.90, 1.00] n=29 | 0.97 [0.90, 1.00] n=29 |
| `faithfulness` | 0.74 [0.62, 0.85] n=39 | 0.86 [0.76, 0.95] n=31 | 0.86 [0.76, 0.95] n=31 |
| `shown_citation_validity` | n/a | 0.99 [0.98, 1.00] n=31 | 1.00 [1.00, 1.00] n=31 |
| `shown_support_rate` | n/a | 1.00 [0.99, 1.00] n=31 | 1.00 [1.00, 1.00] n=31 |
| `citation_validity` | n/a | 0.99 [0.98, 1.00] n=31 | 0.99 [0.98, 1.00] n=31 |
| `citation_recall` | n/a | 0.86 [0.72, 0.97] n=29 | 0.86 [0.72, 0.97] n=29 |
| `abstention_precision` | 0.88 [0.62, 1.00] n=8 | 0.94 [0.81, 1.00] n=16 | 0.94 [0.81, 1.00] n=16 |
| `conflict_rate` | 0.00 [0.00, 0.00] n=39 | 0.13 [0.03, 0.26] n=31 | 0.13 [0.03, 0.26] n=31 |

| Per question (p50 / p95) | Naive RAG (LangChain) | Soundline, verification off | Soundline |
|---|---|---|---|
| `latency_ms` | 5,856 / 8,136 | 11,083 / 22,161 | 11,084 / 22,162 |
| `tokens_in` | 1,291 / 1,562 | 2,469 / 3,101 | 2,469 / 3,101 |
| `tokens_out` | 60 / 136 | 177 / 872 | 177 / 872 |

## Paired comparisons

Comparison of `soundline-verified` against `soundline-unverified` (47 cases, 95% bootstrap intervals, tolerance 0.0)

| metric | baseline | run | difference [95% CI] | verdict |
|---|---|---|---|---|
| abstention_precision | 0.938 | 0.938 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| answer_rate | 0.966 | 0.966 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| approximate_citation_rate | 0.045 | 0.045 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| citation_recall | 0.862 | 0.862 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| citation_validity | 0.991 | 0.991 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| conflict_rate | 0.129 | 0.129 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| cost_usd | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | no significant change |
| faithfulness | 0.863 | 0.862 | -0.002 [-0.005, +0.000] | no significant change ⚠️ too few cases |
| false_answer_rate | 0.167 | 0.167 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@1 | 0.586 | 0.586 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@3 | 0.828 | 0.828 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@5 | 0.931 | 0.931 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@10 | 0.966 | 0.966 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| injection_success_rate | 0.667 | 0.667 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| judge_tokens_in | 729.298 | 718.681 | -10.617 [-30.064, +0.000] | no significant change ⚠️ too few cases |
| judge_tokens_out | 103.426 | 101.787 | -1.638 [-4.766, +0.000] | no significant change ⚠️ too few cases |
| latency_ms | 14799.825 | 14800.401 | +0.575 [+0.265, +0.849] | regressed ⚠️ too few cases |
| lenient_parse_rate | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | no significant change |
| mrr | 0.708 | 0.708 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| ndcg@1 | 0.586 | 0.586 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| ndcg@3 | 0.706 | 0.706 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| ndcg@5 | 0.751 | 0.751 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| ndcg@10 | 0.761 | 0.761 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| precision@1 | 0.586 | 0.586 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| precision@3 | 0.471 | 0.471 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| precision@5 | 0.366 | 0.366 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| precision@10 | 0.203 | 0.203 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| recall@1 | 0.569 | 0.569 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| recall@3 | 0.828 | 0.828 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| recall@5 | 0.931 | 0.931 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| recall@10 | 0.966 | 0.966 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| shown_citation_validity | 0.991 | 1.000 | +0.009 [+0.000, +0.024] | no significant change ⚠️ too few cases |
| shown_support_rate | 0.995 | 1.000 | +0.005 [+0.000, +0.014] | no significant change ⚠️ too few cases |
| support_rate | 0.995 | 0.995 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| tokens_in | 2421.234 | 2421.234 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| tokens_out | 354.617 | 354.617 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| unflagged_injection_rate | 0.333 | 0.333 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |

Comparison of `soundline-verified` against `naive-langchain` (47 cases, 95% bootstrap intervals, tolerance 0.0)

| metric | baseline | run | difference [95% CI] | verdict |
|---|---|---|---|---|
| abstention_precision | 0.875 | 0.938 | +0.000 [+0.000, +0.000] | no significant change |
| answer_rate | 0.966 | 0.966 | +0.000 [-0.103, +0.103] | no significant change ⚠️ too few cases |
| conflict_rate | 0.000 | 0.129 | +0.133 [+0.033, +0.267] | improved |
| faithfulness | 0.739 | 0.862 | +0.024 [-0.128, +0.171] | no significant change ⚠️ too few cases |
| false_answer_rate | 0.611 | 0.167 | -0.444 [-0.667, -0.222] | improved ⚠️ too few cases |
| injection_success_rate | 0.667 | 0.667 | +0.000 [-0.500, +0.500] | no significant change ⚠️ too few cases |
| judge_tokens_in | 1158.149 | 718.681 | -439.468 [-695.638, -194.979] | improved ⚠️ too few cases |
| judge_tokens_out | 83.979 | 101.787 | +17.809 [-8.043, +45.298] | no significant change ⚠️ too few cases |
| latency_ms | 5958.408 | 14800.401 | +8841.993 [+5718.980, +13622.729] | regressed ⚠️ too few cases |
| tokens_in | 1302.213 | 2421.234 | +1119.021 [+1016.702, +1231.149] | regressed ⚠️ too few cases |
| tokens_out | 66.532 | 354.617 | +288.085 [+144.128, +507.532] | regressed ⚠️ too few cases |
| unflagged_injection_rate | 0.667 | 0.333 | -0.333 [-0.667, +0.000] | no significant change ⚠️ too few cases |
