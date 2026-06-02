#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Running API tests"
(
  cd "$ROOT_DIR/apps/api"
  uv run pytest
)

echo "Building web"
(
  cd "$ROOT_DIR/apps/web"
  npm run build
)
