#!/usr/bin/env bash
# The same gate as CI, stopping at the first failure. Run before every commit.
set -euo pipefail
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run lint-imports
uv run pytest -q -n auto
uv run python scripts/spec_coverage.py
