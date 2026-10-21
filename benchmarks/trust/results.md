# Trust benchmark results

Generated 2026-10-21 on arm64 (Darwin), model `ollama:qwen3.5:9b`, judge {"calibration": "uncalibrated", "model": "ollama:qwen3.5:9b", "version": "faithfulness-v2"}, dataset `evals/trust-fr/dataset.jsonl` (47 cases, sha256 `88532805a4a4`).

| Metric | Naive RAG (LangChain) | Soundline, verification off | Soundline |
|---|---|---|---|
| `false_answer_rate` | 0.61 [0.39, 0.83] n=18 | 0.17 [0.00, 0.33] n=18 | 0.17 [0.00, 0.33] n=18 |
| `injection_success_rate` | 0.67 [0.33, 1.00] n=6 | 0.67 [0.33, 1.00] n=6 | 0.67 [0.33, 1.00] n=6 |
| `answer_rate` | 0.97 [0.90, 1.00] n=29 | 0.97 [0.90, 1.00] n=29 | 0.97 [0.90, 1.00] n=29 |
| `faithfulness` | 0.74 [0.62, 0.85] n=39 | 0.86 [0.75, 0.95] n=31 | 0.86 [0.75, 0.95] n=31 |
| `shown_citation_validity` | n/a | 0.99 [0.98, 1.00] n=31 | 1.00 [1.00, 1.00] n=31 |
| `shown_support_rate` | n/a | 1.00 [0.99, 1.00] n=31 | 1.00 [1.00, 1.00] n=31 |
| `citation_validity` | n/a | 0.99 [0.98, 1.00] n=31 | 0.99 [0.98, 1.00] n=31 |
| `citation_recall` | n/a | 0.84 [0.71, 0.97] n=29 | 0.84 [0.71, 0.97] n=29 |
| `abstention_precision` | 0.88 [0.62, 1.00] n=8 | 0.94 [0.81, 1.00] n=16 | 0.94 [0.81, 1.00] n=16 |

| Per question (p50 / p95) | Naive RAG (LangChain) | Soundline, verification off | Soundline |
|---|---|---|---|
| `latency_ms` | 5,856 / 8,136 | 10,425 / 25,424 | 10,421 / 25,336 |
| `tokens_in` | 1,291 / 1,562 | 2,380 / 2,820 | 2,380 / 2,820 |
| `tokens_out` | 60 / 136 | 169 / 882 | 169 / 882 |

## Paired comparisons

Comparison of `soundline-verified` against `soundline-unverified` (47 cases, 95% bootstrap intervals, tolerance 0.0)

| metric | baseline | run | difference [95% CI] | verdict |
|---|---|---|---|---|
| abstention_precision | 0.938 | 0.938 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| answer_rate | 0.966 | 0.966 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| approximate_citation_rate | 0.040 | 0.040 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| citation_recall | 0.845 | 0.845 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| citation_validity | 0.992 | 0.992 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| cost_usd | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | no significant change |
| faithfulness | 0.856 | 0.856 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| false_answer_rate | 0.167 | 0.167 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@1 | 0.586 | 0.586 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@3 | 0.828 | 0.828 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@5 | 0.931 | 0.931 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| hit_rate@10 | 0.966 | 0.966 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| injection_success_rate | 0.667 | 0.667 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| judge_tokens_in | 796.915 | 780.574 | -16.340 [-41.511, +0.000] | no significant change ⚠️ too few cases |
| judge_tokens_out | 104.191 | 103.085 | -1.106 [-4.468, +1.149] | no significant change ⚠️ too few cases |
| latency_ms | 12742.401 | 12737.049 | -5.352 [-11.804, -0.930] | improved ⚠️ too few cases |
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
| shown_citation_validity | 0.992 | 1.000 | +0.008 [+0.000, +0.021] | no significant change ⚠️ too few cases |
| shown_support_rate | 0.995 | 1.000 | +0.005 [+0.000, +0.014] | no significant change ⚠️ too few cases |
| support_rate | 0.995 | 0.995 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| tokens_in | 2291.702 | 2291.702 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |
| tokens_out | 279.532 | 279.532 | +0.000 [+0.000, +0.000] | no significant change ⚠️ too few cases |

Comparison of `soundline-verified` against `naive-langchain` (47 cases, 95% bootstrap intervals, tolerance 0.0)

| metric | baseline | run | difference [95% CI] | verdict |
|---|---|---|---|---|
| abstention_precision | 0.875 | 0.938 | +0.000 [+0.000, +0.000] | no significant change |
| answer_rate | 0.966 | 0.966 | +0.000 [-0.103, +0.103] | no significant change ⚠️ too few cases |
| faithfulness | 0.739 | 0.856 | +0.018 [-0.128, +0.168] | no significant change ⚠️ too few cases |
| false_answer_rate | 0.611 | 0.167 | -0.444 [-0.667, -0.222] | improved ⚠️ too few cases |
| injection_success_rate | 0.667 | 0.667 | +0.000 [-0.500, +0.500] | no significant change ⚠️ too few cases |
| judge_tokens_in | 1158.149 | 780.574 | -377.574 [-654.745, -87.298] | improved ⚠️ too few cases |
| judge_tokens_out | 83.979 | 103.085 | +19.106 [-9.553, +53.149] | no significant change ⚠️ too few cases |
| latency_ms | 5958.408 | 12737.049 | +6778.641 [+5127.724, +8847.345] | regressed ⚠️ too few cases |
| tokens_in | 1302.213 | 2291.702 | +989.489 [+899.979, +1077.936] | regressed ⚠️ too few cases |
| tokens_out | 66.532 | 279.532 | +213.000 [+128.830, +319.681] | regressed ⚠️ too few cases |
