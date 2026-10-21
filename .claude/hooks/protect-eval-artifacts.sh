#!/usr/bin/env bash
# PreToolUse hook: agents must not edit evaluation ground truth by hand.
# "Every invariant written in a README must become a test, a gate or a hook."
set -euo pipefail
path=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
[[ -z "$path" ]] && exit 0
relative="${path#"${CLAUDE_PROJECT_DIR:-$PWD}"/}"
case "$relative" in
  evals/smoke/baseline.json)
    echo "Blocked: $relative is generated. Run scripts/smoke_eval.sh --update-baseline after an intended change, and commit it." >&2
    exit 2 ;;
  evals/smoke/dataset.jsonl|evals/smoke/gates.toml|evals/smoke/corpus/*)
    echo "Blocked: $relative is evaluation ground truth. Changing the dataset, the corpus or the gates is a deliberate human decision; ask the user first." >&2
    exit 2 ;;
esac
exit 0
