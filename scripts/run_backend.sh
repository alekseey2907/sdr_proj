#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/deploy/orangepi/skyshield.env}"

if [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

if [ ! -d "$ROOT_DIR/.venv" ]; then
  echo "Virtual environment not found: $ROOT_DIR/.venv"
  exit 1
fi

mkdir -p "$ROOT_DIR/backend/data"

. "$ROOT_DIR/.venv/bin/activate"
export PYTHONPATH="$ROOT_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"

exec python -m uvicorn app.main:app --host "${BACKEND_HOST:-0.0.0.0}" --port "${BACKEND_PORT:-8000}"