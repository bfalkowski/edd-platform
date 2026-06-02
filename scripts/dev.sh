#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Starting API on http://127.0.0.1:8001"
(
  cd "$ROOT_DIR/apps/api"
  uv run uvicorn edd_platform_api.main:app --host 127.0.0.1 --port 8001
) &
API_PID=$!

cleanup() {
  kill "$API_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Starting web on http://127.0.0.1:5173"
cd "$ROOT_DIR/apps/web"
npm run dev
