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
