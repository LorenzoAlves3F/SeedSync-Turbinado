"""
Backend entry point — starts API (uvicorn) + Worker in the same PM2 process.
Usage: ./venv/bin/python run.py
"""
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable  # inherits the venv python


def _repair_env(path: str):
    """Strip spaces injected by the Orchestrator into long .env values.

    The Orchestrator wraps long values with line breaks or spaces every ~80 chars.
    None of our values (JWT tokens, JSON blobs, URLs) contain intentional spaces,
    so stripping all spaces from the VALUE portion of each KEY=VALUE line is safe.
    """
    if not os.path.exists(path):
        return
    lines = []
    changed = False
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip("\n")
            # Leave comments and blank lines untouched
            if stripped.startswith("#") or "=" not in stripped:
                lines.append(line)
                continue
            key, _, value = stripped.partition("=")
            clean_value = value.replace(" ", "")
            if clean_value != value:
                changed = True
            lines.append(f"{key}={clean_value}\n")
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[seedsync] repaired .env at {path}", flush=True)


def main():
    procs = []

    def cleanup(signum=None, frame=None):
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    # Self-heal .env files before starting subprocesses
    _repair_env(os.path.join(ROOT, "worker", ".env"))
    _repair_env(os.path.join(ROOT, "api", ".env"))
    _repair_env(os.path.join(ROOT, ".env"))

    worker = subprocess.Popen(
        [PYTHON, "-m", "app.main"],
        cwd=os.path.join(ROOT, "worker"),
    )
    procs.append(worker)
    print(f"[seedsync] worker started (pid {worker.pid})", flush=True)

    api = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=os.path.join(ROOT, "api"),
    )
    procs.append(api)
    print(f"[seedsync] api started (pid {api.pid})", flush=True)

    while True:
        for p in procs:
            if p.poll() is not None:
                print(f"[seedsync] process {p.pid} exited ({p.returncode})", flush=True)
                cleanup()
        time.sleep(2)


if __name__ == "__main__":
    main()
