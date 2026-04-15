"""
Backend entry point — starts API (uvicorn) + Worker in the same PM2 process.
Usage: ./venv/bin/python run.py
"""
import os
import re
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable  # inherits the venv python


_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=")


def _repair_env(path: str):
    """Join continuation lines and strip injected spaces from .env values.

    The Orchestrator sometimes wraps long values with real newlines or injects
    spaces every ~80-132 chars. Strategy:
    - Continuation lines (no KEY= prefix) are joined onto the preceding value.
    - Spaces are stripped from non-JSON values (JWTs, tokens, URLs).
    - JSON values (GOOGLE_SERVICE_ACCOUNT_JSON) are left intact after joining
      because they contain meaningful spaces inside string literals.
    """
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    result = []
    changed = False
    i = 0

    while i < len(raw_lines):
        line = raw_lines[i].rstrip("\r\n")
        stripped = line.strip()

        # Blank lines and comments pass through unchanged
        if not stripped or stripped.startswith("#"):
            result.append(stripped + "\n")
            i += 1
            continue

        m = _KEY_RE.match(line)
        if not m:
            # Orphaned fragment with no KEY= — discard (it's a dangling continuation)
            changed = True
            i += 1
            continue

        eq_pos = line.index("=")
        key = line[:eq_pos]
        value = line[eq_pos + 1:]

        # Collect continuation lines: lines that don't start their own KEY=
        j = i + 1
        while j < len(raw_lines):
            next_stripped = raw_lines[j].rstrip("\r\n").strip()
            if not next_stripped or next_stripped.startswith("#"):
                break
            if _KEY_RE.match(next_stripped):
                break
            value += next_stripped
            changed = True
            j += 1

        i = j

        # Strip spaces only from non-JSON values (JWTs, URLs, tokens).
        # JSON values (starting with { or [) contain meaningful spaces inside
        # string literals such as "BEGIN RSA PRIVATE KEY" — leave them alone.
        is_json = value.lstrip().startswith("{") or value.lstrip().startswith("[")
        if not is_json:
            clean = value.replace(" ", "")
            if clean != value:
                changed = True
                value = clean

        result.append(f"{key}={value}\n")

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(result)
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
