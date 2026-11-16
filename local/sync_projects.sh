#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)

for lock in $(find "$ROOT" -name uv.lock -not -path '*/.venv/*' -not -path '*/node_modules/*'  -not -path "$ROOT/local/*"); do
  dir=$(dirname "$lock")
  echo "==> syncing $dir"
  (cd "$dir" && uv sync --frozen)   
done