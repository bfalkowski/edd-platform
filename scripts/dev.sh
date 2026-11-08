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

require_free_port() {
  local port="$1" var="$2"
  # lsof may be missing or unable to see other users' processes, so also try to connect.
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 \
    || (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null; then
    echo "Port ${port} is already in use (maybe another worktree's dev server)." >&2
    echo "Choose another port, for example: ${var}=$((port + 10)) ./scripts/dev.sh" >&2
    exit 1
  fi
}

load_env_file
enable_local_langfuse_if_running

API_PORT="${EDD_API_PORT:-8001}"
WEB_PORT="${EDD_WEB_PORT:-5173}"
API_URL="http://127.0.0.1:${API_PORT}"

require_free_port "$API_PORT" EDD_API_PORT
require_free_port "$WEB_PORT" EDD_WEB_PORT

echo "Starting API on ${API_URL}"
(
  cd "$ROOT_DIR/apps/api"
  export EDD_PLATFORM_DATABASE_URL="${EDD_PLATFORM_DATABASE_URL:-postgresql://edd_platform:edd_platform@127.0.0.1:15432/edd_platform}"
  exec uv run uvicorn edd_platform_api.main:app --host 127.0.0.1 --port "$API_PORT"
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
  if curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if ! curl -fsS "${API_URL}/health" >/dev/null 2>&1; then
  echo "API did not become healthy on ${API_URL}."
  exit 1
fi

echo "Starting web on http://127.0.0.1:${WEB_PORT} (API proxy -> ${API_URL})"
cd "$ROOT_DIR/apps/web"
export VITE_API_PROXY_TARGET="$API_URL"
npm exec --no -- vite --host 0.0.0.0 --port "$WEB_PORT" --strictPort
