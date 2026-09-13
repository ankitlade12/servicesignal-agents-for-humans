#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  uv sync --frozen
fi
mkdir -p data
exec .venv/bin/python scripts/run.py
