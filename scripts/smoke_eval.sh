#!/usr/bin/env bash
# Retrieval smoke evaluation: the same steps locally and in CI (EVL-090, EVL-064).
# Offline and deterministic (hashing embedder): it catches breakage, it does not measure
# quality. Usage: scripts/smoke_eval.sh [--update-baseline]
set -euo pipefail
cd "$(dirname "$0")/.."
export SOUNDLINE_HOME="${SOUNDLINE_HOME:-$(mktemp -d)}"
export SOUNDLINE_EMBEDDER="hashing:256"
SMOKE=evals/smoke

uv run soundline ingest "$SMOKE/corpus" > /dev/null
uv run soundline eval run "$SMOKE/dataset.jsonl" --name current
if [[ "${1:-}" == "--update-baseline" ]]; then
  cp "$SOUNDLINE_HOME/evals/runs/current.json" "$SMOKE/baseline.json"
  echo "baseline updated: $SMOKE/baseline.json"
  exit 0
fi
uv run soundline eval compare "$SMOKE/baseline.json" current --format md > "$SOUNDLINE_HOME/comparison.md"
cat "$SOUNDLINE_HOME/comparison.md"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  cat "$SOUNDLINE_HOME/comparison.md" >> "$GITHUB_STEP_SUMMARY"
fi
uv run soundline eval gate current --baseline "$SMOKE/baseline.json" --rules "$SMOKE/gates.toml"
