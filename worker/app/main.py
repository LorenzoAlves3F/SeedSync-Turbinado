import asyncio
import hashlib
import logging
import os
import random
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Any
from .config import POLL_INTERVAL_SECONDS, SUPABASE_URL, SUPABASE_HEADERS, DRY_RUN, ZAPI_BASE_URL, ZAPI_CLIENT_TOKEN
from .audit import log
from .ingestion.ingester import LeadIngester
from .ingestion.schema_manager import ensure_table_columns
from .integrations.sheets import fetch_new_rows, get_sheet_row_count
from .integrations.whatsapp import ZApiProvider
from .integrations.clickup import create_failure_task
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

# Directory scanned at startup for per-SA credential JSON files
CREDENTIALS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "credentials",
)

# ── WhatsApp retry backoff schedule ───────────────────────────────────────────
# Index 0 = after 1st failure (5 min), 1 = 2nd (30 min), 2 = 3rd (2 hr) → dead
RETRY_BACKOFF_SECS: list[int] = [300, 1800, 7200]

# Headers for public-schema tables (notification_queue, google_service_accounts).
# MUST NOT include Accept-Profile/Content-Profile — those force seed_sync schema.
_PUBLIC_HEADERS = {
    "apikey": SUPABASE_HEADERS["apikey"],
    "Authorization": SUPABASE_HEADERS["Authorization"],
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

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


async def fetch_all_credentials() -> dict[str, str]:
    """Fetch google_service_accounts and return {id: sa_file_path}. Empty dict on any error."""
    try:
        r = await http_client.get(
            f"{SUPABASE_URL}/rest/v1/google_service_accounts",
            headers=_PUBLIC_HEADERS,
            params={"select": "id,sa_file"},
        )
        if r.is_success:
            return {row["id"]: row["sa_file"] for row in r.json()}
        log("scheduler", "fetch_credentials_failed", error=r.text[:200])
        return {}
    except Exception as e:
        log("scheduler", "fetch_credentials_exception", error=str(e))
        return {}


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


async def fast_forward_new_clients(
    configs: list[dict],
    credentials: dict[str, str],
) -> list[dict]:
    """Fast-forward last_row_index for any client at 0 before the batch runs.

    Clients where the sheet is unreachable are excluded this cycle entirely
    rather than ingested from row 0 (which would notify on all historical leads).
    """
    new_clients = [c for c in configs if c.get("last_row_index", 0) == 0]
    if not new_clients:
        return configs

    failed_ids: set[str] = set()
    for conf in new_clients:
        sa_file = credentials.get(conf.get("google_sa_id") or "", "")
        try:
            row_count = await get_sheet_row_count(
                conf["sheet_id"], conf["worksheet_name"], sa_file=sa_file
            )
            await update_cursor(conf["id"], row_count)
            conf["last_row_index"] = row_count  # Keep in-memory consistent with DB
            log("scheduler", "cursor_fast_forwarded",
                client=conf["client_id"], new_index=row_count)
        except Exception as e:
            log("scheduler", "fast_forward_failed",
                client=conf["client_id"], error=str(e))
            failed_ids.add(conf["id"])

    return [c for c in configs if c["id"] not in failed_ids]


async def check_zapi_session() -> bool:
    """Return True if Z-API WhatsApp session is connected. Always True in DRY_RUN."""
    if DRY_RUN:
        return True
    try:
        r = await http_client.get(
            f"{ZAPI_BASE_URL}status",
            headers={"Client-Token": ZAPI_CLIENT_TOKEN},
        )
        if r.is_success:
            connected = r.json().get("connected", False)
            if not connected:
                log("worker", "zapi_session_disconnected", response=r.text[:200])
            return connected
        log("worker", "zapi_status_check_failed", status_code=r.status_code, error=r.text[:200])
        return False
    except Exception as e:
        log("worker", "zapi_status_check_exception", error=str(e))
        return False


async def process_client(conf: Dict[str, Any], credentials: dict[str, str], zapi_ok: bool = True):
    """Async task to sync a single client with strict internal timeout and concurrency control."""
    client_id = conf["client_id"]
    sheet_id = conf["sheet_id"]
    worksheet = conf["worksheet_name"]
    last_index = conf["last_row_index"]
    sa_file = credentials.get(conf.get("google_sa_id") or "", "")

    # Use semaphore to throttle concurrent Google Sheets requests
    async with _sheets_semaphore:
        try:
            # Wrap the actual ingestion in an internal timeout
            async def _run_sync():
                # 1. Fetch new rows strictly forward
                rows, header_sample = await fetch_new_rows(sheet_id, worksheet, last_index, sa_file=sa_file)
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
                ingester = LeadIngester(client_id, conf, notify=zapi_ok)
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


async def process_retry_queue() -> None:
    """
    Poll notification_queue for pending rows whose next_retry_at has passed,
    attempt resend, and update status or schedule next backoff.

    Backoff: 5 min → 30 min → 2 hr. After 3 failures the row is marked dead
    and a ClickUp task is created (only at this terminal state, not on first fail).
    """
    try:
        r = await http_client.get(
            f"{SUPABASE_URL}/rest/v1/notification_queue",
            headers=_PUBLIC_HEADERS,
            params={
                "status": "eq.pending",
                "next_retry_at": f"lte.{datetime.now(timezone.utc).isoformat()}",
                "order": "next_retry_at.asc",
                "limit": "50",
            },
        )
        if not r.is_success:
            log("scheduler", "retry_queue_fetch_failed", error=r.text[:200])
            return
        rows = r.json()
    except Exception as e:
        log("scheduler", "retry_queue_fetch_exception", error=str(e))
        return

    if not rows:
        return

    log("scheduler", "retry_queue_processing", count=len(rows))
    provider = ZApiProvider()

    for row in rows:
        row_id = row["id"]
        retry_count = row["retry_count"]
        client_id = row["client_id"]
        dest_phone = row["destination_phone"]
        message = row["message"]
        fingerprint = row["lead_fingerprint"]

        if DRY_RUN:
            log("scheduler", "DRY_RUN retry_skip", row_id=row_id, client=client_id)
            continue

        send_res = await provider.send_text(dest_phone, message)

        try:
            if send_res.success:
                await http_client.patch(
                    f"{SUPABASE_URL}/rest/v1/notification_queue",
                    headers=_PUBLIC_HEADERS,
                    params={"id": f"eq.{row_id}"},
                    json={"status": "sent"},
                )
                # Best-effort: sync ingestion_log status
                await http_client.patch(
                    f"{SUPABASE_URL}/rest/v1/ingestion_log",
                    headers=SUPABASE_HEADERS,
                    params={"row_fingerprint": f"eq.{fingerprint}", "client_id": f"eq.{client_id}"},
                    json={"whatsapp_status": "sent"},
                )
                log("scheduler", "retry_sent",
                    row_id=row_id, client=client_id, attempt=retry_count + 1)

            else:
                new_count = retry_count + 1

                if new_count >= len(RETRY_BACKOFF_SECS):
                    await http_client.patch(
                        f"{SUPABASE_URL}/rest/v1/notification_queue",
                        headers=_PUBLIC_HEADERS,
                        params={"id": f"eq.{row_id}"},
                        json={
                            "status": "dead",
                            "retry_count": new_count,
                            "last_error": (send_res.error or "")[:500],
                        },
                    )
                    log("scheduler", "retry_dead",
                        row_id=row_id, client=client_id, attempts=new_count)

                    # Fetch ClickUp config and fire task
                    cfg_r = await http_client.get(
                        f"{SUPABASE_URL}/rest/v1/source_configs",
                        headers=SUPABASE_HEADERS,
                        params={"client_id": f"eq.{client_id}",
                                "select": "clickup_enabled,clickup_list_id", "limit": "1"},
                    )
                    if cfg_r.is_success and cfg_r.json():
                        cfg = cfg_r.json()[0]
                        if cfg.get("clickup_enabled") and cfg.get("clickup_list_id"):
                            async def _safe_clickup(list_id: str, cid: str, phone: str, err: str) -> None:
                                try:
                                    await create_failure_task(
                                        list_id=list_id,
                                        title=f"Falha Notificação ({cid}) — todas as tentativas esgotadas",
                                        description=(
                                            f"Não foi possível entregar notificação para {phone} "
                                            f"após {len(RETRY_BACKOFF_SECS)} tentativas.\n"
                                            f"Último erro: {err}"
                                        ),
                                        assignees=[],
                                        priority=1,
                                    )
                                except Exception as cu_err:
                                    log("scheduler", "retry_clickup_exception",
                                        client=cid, error=str(cu_err))
                            asyncio.create_task(_safe_clickup(
                                cfg["clickup_list_id"], client_id,
                                dest_phone, send_res.error or "",
                            ))
                else:
                    next_wait = RETRY_BACKOFF_SECS[new_count]
                    next_retry_at = (
                        datetime.now(timezone.utc) + timedelta(seconds=next_wait)
                    ).isoformat()
                    await http_client.patch(
                        f"{SUPABASE_URL}/rest/v1/notification_queue",
                        headers=_PUBLIC_HEADERS,
                        params={"id": f"eq.{row_id}"},
                        json={
                            "retry_count": new_count,
                            "next_retry_at": next_retry_at,
                            "last_error": (send_res.error or "")[:500],
                        },
                    )
                    log("scheduler", "retry_rescheduled",
                        row_id=row_id, client=client_id,
                        retry_count=new_count, next_wait_secs=next_wait)

        except Exception as e:
            log("scheduler", "retry_row_exception",
                row_id=row_id, client=client_id, error=str(e))


async def run_ingestion_batch():
    """Fetch all configs, then process only the next CLIENTS_PER_BATCH slice."""
    global _client_offset

    # ── Z-API session check — gate all sends and retry processing ────────────
    zapi_ok = await check_zapi_session()

    # ── Retry queue pass (before new-lead ingestion) ─────────────────────────
    if zapi_ok:
        await process_retry_queue()
    else:
        log("worker", "retry_queue_skipped_session_down")

    all_configs = await fetch_all_configs()
    if not all_configs:
        log("scheduler", "no_active_configs")
        return

    # ── Credential map: fetched once per cycle ────────────────────────────────
    credentials = await fetch_all_credentials()

    all_configs = await fast_forward_new_clients(all_configs, credentials)
    if not all_configs:
        log("scheduler", "no_eligible_configs_after_fast_forward")
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
        tasks.append(process_client(conf, credentials, zapi_ok))
        await asyncio.sleep(random.uniform(STAGGER_MIN_SECS, STAGGER_MAX_SECS))  # Staggered launch

    await asyncio.gather(*tasks, return_exceptions=True)

    _client_offset += CLIENTS_PER_BATCH
    log("scheduler", "batch_finished", next_offset=_client_offset % total)


async def sync_credentials_from_disk() -> None:
    """
    Scan CREDENTIALS_DIR for *.json files and upsert each into google_service_accounts.
    Uses sa_file (absolute path) as the unique key — idempotent, safe on every startup.
    """
    import glob as _glob

    if not os.path.isdir(CREDENTIALS_DIR):
        log("worker", "credentials_dir_missing", path=CREDENTIALS_DIR)
        return

    files = _glob.glob(os.path.join(CREDENTIALS_DIR, "*.json"))
    if not files:
        log("worker", "no_credential_files_found", dir=CREDENTIALS_DIR)
        return

    registered = 0
    for path in files:
        try:
            with open(path) as f:
                data = json.load(f)
            email = data.get("client_email", "")
            name = os.path.splitext(os.path.basename(path))[0]
            r = await http_client.post(
                f"{SUPABASE_URL}/rest/v1/google_service_accounts",
                headers={**_PUBLIC_HEADERS, "Prefer": "resolution=merge-duplicates"},
                params={"on_conflict": "sa_file"},
                json={"name": name, "email": email, "sa_file": path},
            )
            if r.is_success:
                registered += 1
            else:
                log("worker", "credential_sync_failed", file=path, error=r.text[:200])
        except Exception as e:
            log("worker", "credential_sync_exception", file=path, error=str(e))

    log("worker", "credentials_synced", found=len(files), registered=registered)


def _start_health_server():
    """Start a minimal HTTP server for orchestrator health checks (background thread)."""
    import time as _time
    port = int(os.getenv("WORKER_HEALTH_PORT", "9000"))

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_):
            pass  # Silence access logs

    # Retry loop: previous process may still hold the port during a fast PM2 restart
    for attempt in range(15):
        try:
            server = HTTPServer(("0.0.0.0", port), _Handler, bind_and_activate=False)
            server.allow_reuse_address = True
            server.server_bind()
            server.server_activate()
            log("worker", "health_server_started", port=port)
            server.serve_forever()
            return
        except OSError:
            if attempt < 14:
                _time.sleep(2)

    log("worker", "health_server_failed", port=port)


async def main():
    threading.Thread(target=_start_health_server, daemon=True).start()

    log(
        "worker", "started",
        interval=POLL_INTERVAL_SECONDS,
        dry_run=DRY_RUN,
        clients_per_batch=CLIENTS_PER_BATCH,
        architecture="Hardened_No_Restart_v2"
    )

    await sync_credentials_from_disk()

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

