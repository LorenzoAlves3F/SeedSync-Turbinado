import asyncio
import hashlib
import logging
import os
import random
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Any
from .config import POLL_INTERVAL_SECONDS, SUPABASE_URL, SUPABASE_HEADERS, DRY_RUN
from .audit import log
from .ingestion.ingester import LeadIngester
from .ingestion.schema_manager import ensure_table_columns
from .integrations.sheets import fetch_new_rows
from .http_client import http_client

# Silence noisy external logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ── Rotating Batch Config ──────────────────────────────────────────────────
# Checks CLIENTS_PER_BATCH clients every POLL_INTERVAL_SECONDS.
# Optimized for Quota Safety: 5 clients/min ensures we stay under Google's 60 req/min.
CLIENTS_PER_BATCH = 5
# Hard wall on how long a single client is allowed to take (covers slow Sheets reads + DB writes)
CLIENT_PROCESS_TIMEOUT_SECS = 30
# Maximum simultaneous gspread calls — keeps us under Google's 60 req/min quota
MAX_CONCURRENT_SHEETS = 2
# Jitter range between task launches to spread API pressure across time
STAGGER_MIN_SECS, STAGGER_MAX_SECS = 1.0, 3.0

# Global rotating offset — persists across job cycles within the same process
_client_offset = 0

# Global Semaphore to prevent "burst" pressure on Google Sheets API
_sheets_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SHEETS)


async def fetch_all_configs():
    """Async: Fetch all active client configs."""
    try:
        r = await http_client.get(
            f"{SUPABASE_URL}/rest/v1/source_configs",
            headers=SUPABASE_HEADERS,
            params={"active": "eq.true", "order": "client_id.asc"}
        )
        if r.is_success:
            return r.json()
        log("scheduler", "fetch_configs_failed", error=r.text[:200])
        return []
    except Exception as e:
        log("scheduler", "fetch_configs_exception", error=str(e))
        return []


async def update_cursor(config_id: str, new_index: int):
    """Async: Persist the new sync cursor."""
    if DRY_RUN:
        return
    try:
        r = await http_client.patch(
            f"{SUPABASE_URL}/rest/v1/source_configs",
            headers=SUPABASE_HEADERS,
            params={"id": "eq." + config_id},
            json={"last_row_index": new_index}
        )
        if not r.is_success:
            log("scheduler", "cursor_update_failed", config_id=config_id, new_index=new_index, error=r.text[:200])
    except Exception as e:
        log("scheduler", "cursor_update_exception", config_id=config_id, new_index=new_index, error=str(e))


async def _has_client_history(client_id: str) -> bool:
    """Returns True if this client has any entries in ingestion_log (including init sentinels)."""
    try:
        r = await http_client.get(
            f"{SUPABASE_URL}/rest/v1/ingestion_log",
            headers=SUPABASE_HEADERS,
            params={"client_id": f"eq.{client_id}", "limit": "1", "select": "client_id"}
        )
        if r.is_success:
            return len(r.json()) > 0
        return True  # On error, assume history exists — process normally (safe default)
    except Exception:
        return True


async def _mark_client_initialized(client_id: str, skipped: int):
    """Write a sentinel to ingestion_log so fresh-start guard doesn't re-trigger."""
    try:
        fp = hashlib.sha256(
            f"__init__{client_id}__{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()
        await http_client.post(
            f"{SUPABASE_URL}/rest/v1/ingestion_log",
            headers=SUPABASE_HEADERS,
            json={
                "client_id": client_id,
                "row_fingerprint": fp,
                "raw_payload": {"_init": True, "skipped_rows": skipped},
                "status": "initialized",
                "whatsapp_status": "skipped",
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as e:
        log("scheduler", "init_sentinel_failed", client=client_id, error=str(e))


async def process_client(conf: Dict[str, Any]):
    """Async task to sync a single client with strict internal timeout and concurrency control."""
    client_id = conf["client_id"]
    sheet_id = conf["sheet_id"]
    worksheet = conf["worksheet_name"]
    last_index = conf["last_row_index"]

    # Use semaphore to throttle concurrent Google Sheets requests
    async with _sheets_semaphore:
        try:
            # Wrap the actual ingestion in an internal timeout
            async def _run_sync():
                # 1. Fetch new rows strictly forward
                rows, header_sample = await fetch_new_rows(sheet_id, worksheet, last_index)
                if not rows:
                    return 0

                # 1b. Fresh-start guard: on a new deployment the ingestion_log is
                # empty, so dedup won't catch historical leads. If this client has
                # no history at all, fast-forward the cursor to the current sheet
                # end and write a sentinel — don't send old leads as notifications.
                if not await _has_client_history(client_id):
                    start_row_actual = max(2, last_index + 2)
                    new_index = max(last_index, start_row_actual + len(rows) - 2)
                    await update_cursor(conf["id"], new_index)
                    await _mark_client_initialized(client_id, len(rows))
                    log("scheduler", "cursor_initialized", client=client_id,
                        skipped=len(rows), new_index=new_index)
                    return 0

                # 2. Ensure schema exists
                is_ready = await ensure_table_columns(conf["target_table"], header_sample)
                if not is_ready:
                    return 0

                # 3. Process batch
                ingester = LeadIngester(client_id, conf)
                try:
                    success_count = await ingester.process_batch(rows)
                except Exception as e:
                    # ABORT CURSOR UPDATE IF INSERTION FAILED
                    log("scheduler", "batch_processing_aborted", client=client_id, error=str(e))
                    return 0

                # 4. Calculate new High-Water Mark (strictly forward only)
                # Row numbering: row 1 = header, row 2 = first data row.
                # last_index is a 0-based count of data rows seen so far, so the
                # next unread sheet row is (last_index + 2). We subtract 2 because
                # len(rows) includes blank rows up to the end of the fetched range.
                start_row_actual = max(2, last_index + 2)
                highest_row_now = start_row_actual + len(rows) - 2
                new_index = max(last_index, highest_row_now)
                
                if new_index > last_index:
                    await update_cursor(conf["id"], new_index)
                    return (new_index - last_index)
                return 0

            # Apply a hard time limit to this individual client's processing
            new_count = await asyncio.wait_for(_run_sync(), timeout=CLIENT_PROCESS_TIMEOUT_SECS)
            if new_count > 0:
                log("scheduler", "client_finished", client=client_id, new_rows=new_count)

        except asyncio.TimeoutError:
            log("scheduler", "client_timeout", client=client_id, seconds=CLIENT_PROCESS_TIMEOUT_SECS)
        except Exception as e:
            log("scheduler", "client_error", client=client_id, error=str(e))


async def run_ingestion_batch():
    """Fetch all configs, then process only the next CLIENTS_PER_BATCH slice."""
    global _client_offset

    all_configs = await fetch_all_configs()
    if not all_configs:
        log("scheduler", "no_active_configs")
        return

    total = len(all_configs)
    _client_offset = _client_offset % total
    batch = all_configs[_client_offset: _client_offset + CLIENTS_PER_BATCH]

    if len(batch) < CLIENTS_PER_BATCH and total > len(batch):
        batch += all_configs[: CLIENTS_PER_BATCH - len(batch)]
    
    # Final safety: Ensure no duplicate client IDs in the SAME batch
    unique_batch = []
    seen_ids = set()
    for c in batch:
        if c["id"] not in seen_ids:
            unique_batch.append(c)
            seen_ids.add(c["id"])
    batch = unique_batch

    log(
        "scheduler", "batch_started",
        offset=_client_offset,
        batch_size=len(batch),
        total_clients=total,
        clients=[c["client_id"] for c in batch]
    )

    # Process batch with slight sequential jitter to further spread load
    tasks = []
    for conf in batch:
        tasks.append(process_client(conf))
        await asyncio.sleep(random.uniform(STAGGER_MIN_SECS, STAGGER_MAX_SECS))  # Staggered launch

    await asyncio.gather(*tasks, return_exceptions=True)

    _client_offset += CLIENTS_PER_BATCH
    log("scheduler", "batch_finished", next_offset=_client_offset % total)


def _start_health_server():
    """Start a minimal HTTP server for orchestrator health checks (background thread)."""
    port = int(os.getenv("WORKER_HEALTH_PORT", "9000"))

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_):
            pass  # Silence access logs

    server = HTTPServer(("0.0.0.0", port), _Handler, bind_and_activate=False)
    server.allow_reuse_address = True
    server.server_bind()
    server.server_activate()
    log("worker", "health_server_started", port=port)
    server.serve_forever()


async def main():
    threading.Thread(target=_start_health_server, daemon=True).start()

    log(
        "worker", "started",
        interval=POLL_INTERVAL_SECONDS,
        dry_run=DRY_RUN,
        clients_per_batch=CLIENTS_PER_BATCH,
        architecture="Hardened_No_Restart_v2"
    )

    while True:
        try:
            await run_ingestion_batch()
        except Exception as e:
            log("worker", "loop_exception", error=str(e))

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as fatal:
        log("worker", "fatal_crash", error=str(fatal))

