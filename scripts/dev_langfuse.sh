#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker info >/dev/null 2>&1; then
  active_context="$(docker context show 2>/dev/null || true)"
  if [[ "$active_context" == "colima" ]] && command -v colima >/dev/null 2>&1; then
    echo "Docker is not reachable; starting Colima."
    colima start
  fi
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not reachable. Start Docker Desktop or Colima, then retry." >&2
  exit 1
fi

echo "Starting local Postgres"
docker compose -f "$ROOT_DIR/docker-compose.yml" up -d postgres

if curl -fsS http://127.0.0.1:3001/api/public/health >/dev/null 2>&1; then
  echo "Reusing existing local Langfuse on http://localhost:3001"
else
  echo "Starting local Langfuse on http://localhost:3001"
  docker compose \
    -f "$ROOT_DIR/docker-compose.yml" \
    -f "$ROOT_DIR/docker-compose.langfuse.yml" \
    up -d langfuse-web langfuse-worker

  echo "Waiting for Langfuse..."
  for _ in {1..90}; do
    if curl -fsS http://127.0.0.1:3001/api/public/health >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
fi

if ! curl -fsS http://127.0.0.1:3001/api/public/health >/dev/null 2>&1; then
  echo "Langfuse did not become healthy on http://localhost:3001." >&2
  exit 1
fi

export LANGFUSE_BASE_URL="${LANGFUSE_BASE_URL:-http://localhost:3001}"
export LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-pk-lf-local-demo}"
export LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-sk-lf-local-demo}"

echo "Local Langfuse is ready."
echo "  UI:    http://localhost:3001"
echo "  Login: admin@local.dev / local-demo-password"
echo "  Keys:  pk-lf-local-demo / sk-lf-local-demo"
echo

exec "$ROOT_DIR/scripts/dev.sh"
