#!/usr/bin/env bash
# The trust benchmark (EVL-092): naive RAG vs Soundline, with and without verification, on
# answerable, unanswerable and adversarial questions. Runs locally with Ollama, at no cost.
#
#   make bench-trust                       # qwen3.5:9b generates and judges
#   MODEL=qwen3.5:9b JUDGE=anthropic:claude-opus-5-5 make bench-trust
#   OPENAI_BASE_URL=https://openrouter.ai/api/v1 OPENAI_API_KEY=... \
#     JUDGE=openai:anthropic/claude-sonnet-5.5 make bench-trust   # a calibrated judge
#
# SOUNDLINE_HOME is kept between runs: model calls are cached (EVL-061), so a rerun is free
# and reproduces the same numbers. Delete it, or set FRESH=1, to call the models again.
set -euo pipefail
cd "$(dirname "$0")/../.."
MODEL="${MODEL:-qwen3.5:9b}"
JUDGE="${JUDGE:-ollama:$MODEL}"
DATASET="${DATASET:-evals/trust-fr/dataset.jsonl}"
OUTPUT="${OUTPUT:-benchmarks/trust/results.md}"
CORPORA=(evals/logement-fr/corpus "${TRUST_CORPUS:-evals/trust-fr/corpus}")
export SOUNDLINE_HOME="${SOUNDLINE_HOME:-.soundline-bench}"
export SOUNDLINE_EMBEDDER=fastembed:intfloat/multilingual-e5-large
export SOUNDLINE_LLM="ollama:$MODEL"
fresh=()
[[ -n "${FRESH:-}" ]] && fresh=(--no-cache)

uv run soundline ingest "${CORPORA[@]}" > /dev/null
uv run soundline eval run "$DATASET" --name soundline-verified --judge "$JUDGE" "${fresh[@]}"
uv run soundline eval run "$DATASET" --name soundline-unverified --without-verification \
  --judge "$JUDGE" "${fresh[@]}"
answers="$SOUNDLINE_HOME/naive-answers.jsonl"
if [[ -n "${FRESH:-}" || ! -s "$answers" ]]; then
  uv run --script benchmarks/trust/naive_rag.py --model "$MODEL" --dataset "$DATASET" \
    --corpus "${CORPORA[0]}" --corpus "${CORPORA[1]}" --output "$answers"
fi
uv run python benchmarks/trust/trust_report.py --home "$SOUNDLINE_HOME" --dataset "$DATASET" \
  --naive-answers "$answers" --model "$MODEL" --judge "$JUDGE" \
  --output "$OUTPUT"
