#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

CH_PORT="${CLICKHOUSE_PORT:-8123}"
API_PORT="${PORT:-8000}"
API_HOST="${API_HOST:-127.0.0.1}"

trap 'kill $(jobs -p) 2>/dev/null; exit 0' SIGINT SIGTERM

# --- ClickHouse ---
if ! curl -sf "http://localhost:${CH_PORT}/ping" >/dev/null 2>&1; then
  echo "→ Starting ClickHouse..."
  if [[ ! -x ./clickhouse ]]; then
    echo "  ./clickhouse binary not found — installing (one-time)..." >&2
    curl -sf https://clickhouse.com/ | sh >&2 || {
      echo "✗ ClickHouse install failed. Get the binary from https://clickhouse.com/docs/en/install" >&2
      exit 1
    }
  fi
  ./clickhouse server --daemon >/dev/null 2>&1
  for i in $(seq 1 20); do
    curl -sf "http://localhost:${CH_PORT}/ping" >/dev/null 2>&1 && break
    sleep 0.5
  done
  if ! curl -sf "http://localhost:${CH_PORT}/ping" >/dev/null 2>&1; then
    echo "✗ ClickHouse failed to start" >&2; exit 1
  fi
  echo "  ClickHouse ready on :${CH_PORT}"
else
  echo "  ClickHouse already running on :${CH_PORT}"
fi

# --- Schema (idempotent) ---
echo "→ Applying schema..."
set +e
SCHEMA_LOG=$(mktemp)
uv run python src/greenlight/db/seed/apply_schema.py 2>"$SCHEMA_LOG"
SCHEMA_RC=$?
set -e
if [[ $SCHEMA_RC -eq 0 ]]; then
  echo "  Schema OK"
elif grep -qE "ALREADY_EXISTS|TABLE_ALREADY_EXISTS|DATABASE_ALREADY_EXISTS" "$SCHEMA_LOG"; then
  echo "  Schema already applied (idempotent)"
else
  echo "✗ Schema apply failed (exit $SCHEMA_RC):" >&2
  cat "$SCHEMA_LOG" >&2
  rm -f "$SCHEMA_LOG"
  exit 1
fi
rm -f "$SCHEMA_LOG"

# --- Frontend (background, optional) ---
if [[ "${WEB:-0}" == "1" ]]; then
  echo "→ Starting frontend dev server..."
  cd src/greenlight/web && npm run dev --silent &
  WEB_PID=$!
  cd "$DIR"
  echo "  Frontend on :5173 (pid ${WEB_PID})"
fi

# --- FastAPI ---
echo "→ Starting FastAPI on :${API_HOST}:${API_PORT}..."
exec uv run uvicorn greenlight.api.app:app --host "$API_HOST" --port "$API_PORT"
