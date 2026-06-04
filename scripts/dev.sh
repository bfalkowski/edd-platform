#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return
  fi

  echo "Stopping existing process on port ${port}: ${pids//$'\n'/ }"
  kill $pids >/dev/null 2>&1 || true
  for _ in {1..20}; do
    if [[ -z "$(lsof -ti "tcp:${port}" 2>/dev/null || true)" ]]; then
      return
    fi
    sleep 0.25
  done

  pids="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "Force stopping process on port ${port}: ${pids//$'\n'/ }"
    kill -9 $pids >/dev/null 2>&1 || true
  fi
}

stop_port 8001
stop_port 5173

echo "Starting API on http://127.0.0.1:8001"
(
  cd "$ROOT_DIR/apps/api"
  export EDD_PLATFORM_DATABASE_URL="${EDD_PLATFORM_DATABASE_URL:-postgresql://edd_platform:edd_platform@127.0.0.1:15432/edd_platform}"
  uv run uvicorn edd_platform_api.main:app --host 127.0.0.1 --port 8001
) &
API_PID=$!

cleanup() {
  kill "$API_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in {1..30}; do
  if ! kill -0 "$API_PID" >/dev/null 2>&1; then
    echo "API failed to start. Check the error above."
    exit 1
  fi
  if curl -fsS http://127.0.0.1:8001/health >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! curl -fsS http://127.0.0.1:8001/health >/dev/null 2>&1; then
  echo "API did not become healthy on http://127.0.0.1:8001."
  exit 1
fi

echo "Starting web on http://127.0.0.1:5173"
cd "$ROOT_DIR/apps/web"
npm run dev
