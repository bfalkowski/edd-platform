#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

load_env_file() {
  local env_file
  for env_file in "$ROOT_DIR/.env.local" "$ROOT_DIR/.env"; do
    if [[ -f "$env_file" ]]; then
      echo "Loading local environment from ${env_file#$ROOT_DIR/}"
      set -a
      # shellcheck source=/dev/null
      source "$env_file"
      set +a
      return
    fi
  done
}

enable_local_langfuse_if_running() {
  if curl -fsS http://127.0.0.1:3001/api/public/health >/dev/null 2>&1; then
    export LANGFUSE_BASE_URL="${LANGFUSE_BASE_URL:-http://localhost:3001}"
    export LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-pk-lf-local-demo}"
    export LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-sk-lf-local-demo}"
    echo "Using local Langfuse on ${LANGFUSE_BASE_URL}"
  fi
}

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

load_env_file
enable_local_langfuse_if_running

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
