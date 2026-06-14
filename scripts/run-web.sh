#!/usr/bin/env bash
#
# Launch the optional web interface (FastAPI + Uvicorn).
#
# This is the ONLY place the web stack is started. The rest of the container
# never imports it, so the web interface is entirely optional.
#
set -euo pipefail

HOST="${WEB_HOST:-0.0.0.0}"
PORT="${WEB_PORT:-8080}"
APP_DIR="${AUTOMATION_APP:-/opt/automation}/web"

cd "$APP_DIR"

echo "Starting automation web interface on http://${HOST}:${PORT}"
exec uvicorn app:app --host "$HOST" --port "$PORT" "$@"
