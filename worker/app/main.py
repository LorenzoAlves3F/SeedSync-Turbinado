import asyncio
import logging
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
# With 10 clients/min and ~60 clients => full cycle every ~6 minutes.
# Keeps well under Google's 60 requests/min quota.
CLIENTS_PER_BATCH = 10

# Global rotating offset — persists across job cycles within the same process
_client_offset = 0


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
        await http_client.patch(
            f"{SUPABASE_URL}/rest/v1/source_configs",
            headers=SUPABASE_HEADERS,
            params={"id": "eq." + config_id},
            json={"last_row_index": new_index}
        )
    except Exception:
        pass


async def process_client(conf: Dict[str, Any]):
    """Async task to sync a single client with strict internal timeout protection."""
    client_id = conf["client_id"]
    sheet_id = conf["sheet_id"]
    worksheet = conf["worksheet_name"]
    last_index = conf["last_row_index"]

    try:
        # Wrap the actual ingestion in an internal timeout to prevent hangs
        # within individual spreadsheet reads.
        async def _run_sync():
            # 1. Fetch new rows with overlap (buffered check)
            # The fetcher now starts 5 rows back automatically.
            rows, header_sample = await fetch_new_rows(sheet_id, worksheet, last_index)
            if not rows:
                return 0

            # 2. Ensure schema exists
            is_ready = await ensure_table_columns(conf["target_table"], header_sample)
            if not is_ready:
                return 0

            # 3. Process batch (dedup will safely handle the 5 overlap rows)
            ingester = LeadIngester(client_id, conf)
            success_count = await ingester.process_batch(rows)

            # 4. Calculate new High-Water Mark
            # Since fetcher looked at 'max(2, last_row_index + 2 - 5)', we shift forward.
            # If we found 5 overlap rows + 7 new rows = 12 total, then:
            # new_index = original_last + 7 new ones.
            start_row_actual = max(2, last_index + 2 - 5)
            # Row index is (row_relative_to_sheet - 1)
            highest_row_now = start_row_actual + len(rows) - 2 # -2 to convert back to index
            
            # Ensure we only ever move the pointer FORWARD
            new_index = max(last_index, highest_row_now)
            
            if new_index > last_index:
                await update_cursor(conf["id"], new_index)
                return (new_index - last_index) # return true new count
            return 0

        # Apply a 20-second hard limit to this individual client's processing
        new_count = await asyncio.wait_for(_run_sync(), timeout=20.0)
        if new_count > 0:
            log("scheduler", "client_finished", client=client_id, new_rows=new_count)

    except asyncio.TimeoutError:
        log("scheduler", "client_timeout", client=client_id, seconds=20, note="Moved to next client to prevent freeze.")
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

    # Wrap around the offset so it cycles forever
    _client_offset = _client_offset % total
    batch = all_configs[_client_offset: _client_offset + CLIENTS_PER_BATCH]

    # If we're near the end of the list, wrap around to fill the batch
    if len(batch) < CLIENTS_PER_BATCH:
        batch += all_configs[: CLIENTS_PER_BATCH - len(batch)]

    log(
        "scheduler", "batch_started",
        offset=_client_offset,
        batch_size=len(batch),
        total_clients=total,
        clients=[c["client_id"] for c in batch]
    )

    # Process the batch concurrently (up to 10 simultaneous Sheet reads)
    # Using return_exceptions=True to ensure one failure doesn't stop the whole batch
    await asyncio.gather(*[process_client(conf) for conf in batch], return_exceptions=True)

    _client_offset += CLIENTS_PER_BATCH
    log("scheduler", "batch_finished", next_offset=_client_offset % total)


async def main():
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
        logging.error(f"FATAL WORKER ERROR: {fatal}")
