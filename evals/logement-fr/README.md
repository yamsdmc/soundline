# Logement (FR): a realistic French benchmark

Eight official fact sheets about renting a home in France (public sources, Licence Ouverte
2.0, see [SOURCES.md](SOURCES.md)), one synthetic adversarial page, and 29 questions written by
hand against the exact text of the sheets.

Unlike the smoke dataset, this one is **hard on purpose**:

- **conditional facts**: the same sentence exists in several variants depending on the
  situation (the deposit is returned within 1 month *or* 2 months, depending on the check-out
  inspection); both variants are labeled relevant;
- **paraphrases**: questions that share few words with the answer;
- **numbers and dates** from worked examples, where a wrong digit is a wrong answer;
- **an injection**: a forum page claims the deposit is never returned and tells the assistant
  to say so;
- **three unanswerable questions** (insurance prices, average rents, property tax).

## Results (retrieval only, 26 answerable cases, 95% bootstrap intervals)

| Embedder | hit@1 | MRR | recall@5 | nDCG@10 |
|---|---|---|---|---|
| `hashing:256` (no semantics, a floor) | 0.42 [0.23, 0.62] | 0.59 [0.44, 0.74] | 0.85 [0.69, 0.96] | 0.66 [0.52, 0.79] |
| `bge-small-en-v1.5` (English model) | 0.42 [0.23, 0.62] | 0.63 [0.50, 0.76] | 0.92 [0.81, 1.00] | 0.70 [0.58, 0.81] |
| `multilingual-e5-large` (the default) | **0.58** [0.38, 0.77] | **0.70** [0.56, 0.84] | 0.92 [0.81, 1.00] | **0.76** [0.65, 0.88] |

Paired comparisons (`soundline eval compare`):

- e5 vs the English model: hit@1 **+0.15 [+0.04, +0.31], improved**. On French text, the
  multilingual default (CFG-023) is measurably better than a small English model.
- e5 vs hashing: hit@1 +0.15 [-0.04, +0.38], **no significant change** with 26 cases. The trend is
  clear, but this dataset cannot prove it yet; it needs more questions.

### What this benchmark found in Soundline itself

The first run scored every embedder at hit@1 ≈ 0.3. Inspecting the misses showed that the
answer was ranked first, but in another variant of the page: service-public.fr repeats the same
sentence under "furnished" and "unfurnished" tabs, and the evaluator only accepted the first
occurrence of a quote. Quotes now resolve to every occurrence (EVL-002). The smoke dataset, where
no sentence repeats, could never have revealed it.

Building the corpus also showed that real pages carry interface chrome (share confirmations,
"was this page useful?" forms) that the HTML parser indexed as content; it is now skipped
(ING-023).

## Run it

```bash
export SOUNDLINE_HOME=$(mktemp -d) SOUNDLINE_EMBEDDER=fastembed:intfloat/multilingual-e5-large
soundline ingest evals/logement-fr/corpus
soundline eval run evals/logement-fr/dataset.jsonl --name e5-large
```
