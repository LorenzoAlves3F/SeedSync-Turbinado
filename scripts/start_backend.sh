#!/bin/bash
# Starts API (foreground) + Worker (background) as a single PM2-managed process.
# PM2 monitors this script. When uvicorn exits, the script exits,
# PM2 restarts it, and the worker is killed/restarted cleanly via the trap.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKER_PID=""

cleanup() {
    if [ -n "$WORKER_PID" ]; then
        kill "$WORKER_PID" 2>/dev/null
        wait "$WORKER_PID" 2>/dev/null
    fi
}
trap cleanup EXIT SIGTERM SIGINT

# ── Start worker in background ─────────────────────────────────────────────
cd "$REPO_ROOT/worker"
./venv/bin/python -m app.main &
WORKER_PID=$!
echo "[backend] Worker started (PID $WORKER_PID)"

# ── Start API in foreground ────────────────────────────────────────────────
cd "$REPO_ROOT/api"
echo "[backend] Starting API on port 8000..."
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
