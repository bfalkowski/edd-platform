#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Scanning tracked files for secrets"
python "$ROOT_DIR/scripts/secret_scan.py"

echo "Running API tests"
(
  cd "$ROOT_DIR/apps/api"
  uv run pytest
)

echo "Linting OpenAPI contract"
(
  cd "$ROOT_DIR/apps/api"
  uv run python ../../scripts/lint_openapi.py
)

echo "Building web"
(
  cd "$ROOT_DIR/apps/web"
  npm run build
)
