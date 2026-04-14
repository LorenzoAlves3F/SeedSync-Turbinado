#!/bin/bash
# Starts API (foreground) + Worker (background) using the shared root venv.
# PM2 monitors this script. When uvicorn exits, the trap kills the worker cleanly.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_ROOT/venv"
WORKER_PID=""

cleanup() {
    if [ -n "$WORKER_PID" ]; then
        kill "$WORKER_PID" 2>/dev/null
        wait "$WORKER_PID" 2>/dev/null
    fi
}
trap cleanup EXIT SIGTERM SIGINT

# ── Worker (background) ────────────────────────────────────────────────────
cd "$REPO_ROOT/worker"
"$VENV/bin/python" -m app.main &
WORKER_PID=$!
echo "[seedsync] Worker started (PID $WORKER_PID)"

# ── API (foreground — PM2 tracks this process) ─────────────────────────────
cd "$REPO_ROOT/api"
echo "[seedsync] API starting on :8000"
"$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000
