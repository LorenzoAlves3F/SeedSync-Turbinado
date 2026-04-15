import hashlib
import json
import re
import asyncio
from datetime import datetime, timezone
from typing import Any
from ..config import SUPABASE_URL, SUPABASE_HEADERS, DRY_RUN, NOTIFY_OVERRIDE_LIST
from ..phone import normalizer
from ..integrations.whatsapp import whatsapp
from ..integrations.clickup import create_failure_task
from ..http_client import http_client
from ..audit import log
from .validator import sanitize_identifier
from .schema_manager import reload_pgrst_schema


DEDUP_CHUNK_SIZE = 50  # Max fingerprints per PostgREST IN() filter call
ERROR_TEXT_MAX_LEN = 200  # Max characters captured from error response bodies


class LeadIngester:
    """Core logic for lead processing: async and batch optimized."""

    def __init__(self, client_id: str, config: dict):
        """
        Args:
            client_id: Unique identifier for this client (e.g. "GEOTECH").
            config: A source_configs row from Supabase. Required keys:
                - target_table (str): Supabase table to insert leads into.
                - phone_column (str): Sheet column header for the phone number.
                - name_column (str): Sheet column header for the lead name.
                - destination_phones (list[str]): WhatsApp numbers to notify.
                Optional keys:
                - clickup_enabled (bool), clickup_list_id (str): ClickUp alerts.
                - legacy_phone (str): Fallback destination if destination_phones is empty.
        """
        self.client_id = client_id
        self.config = config
        self.target_table = config["target_table"]

    async def process_batch(self, rows: list[dict[str, Any]]) -> int:
        """
        Process a list of rows efficiently.
        Returns the number of successfully inserted rows.
        """
        if not rows: return 0

        # 1. Generate fingerprints for the batch (Hardened Fuzzy Matching)
        # get_fuzzy is defined ONCE outside the loop for correct closure & performance
        def get_fuzzy(target: str, row: dict) -> str:
            for k in row.keys():
                if str(target).lower() == str(k).lower().strip():
                    return row[k]
            return ""

        row_data = []
        for row in rows:
            # Build identity string from cleaned data
            name = str(get_fuzzy("NOME", row)).strip().lower()
            phone = str(get_fuzzy("WHATSAPP", row)).strip().lower()
            
            # If both are empty, use a full row hash as safety fallback
            if not name and not phone:
                payload_str = json.dumps(row, sort_keys=True)
            else:
                payload_str = f"{name}|{phone}"

            fp = hashlib.sha256(payload_str.encode()).hexdigest()
            row_data.append({"row": row, "fp": fp})

        # 2. Bulk Deduplication Check
        all_fps = [rd["fp"] for rd in row_data]
        existing_fps = await self._check_duplicates_bulk(all_fps)
        
        # FAIL-SAFE: If duplicate check fails (returns None), abort batch to prevent re-processing
        if existing_fps is None:
            log("ingester", "batch_aborted_safety", client=self.client_id, reason="duplication_check_failed")
            return 0

        new_leads = [rd for rd in row_data if rd["fp"] not in existing_fps]
        if not new_leads:
            log("ingester", "batch_all_duplicates", client=self.client_id, count=len(rows))
            return 0

        log("ingester", "batch_processing", client=self.client_id, new=len(new_leads), total=len(rows))

        # 3. Batch DB Insert (into client table)
        if not DRY_RUN:
            try:
                # Sanitize all row keys to match DB schema (e.g. 'Atendido?' -> 'atendido')
                sanitized_leads = []
                for rd in new_leads:
                    sanitized_leads.append({sanitize_identifier(k): v for k, v in rd["row"].items() if k})

                ins_res = await self._insert_with_schema_recovery(sanitized_leads)
                if not ins_res.is_success:
                    log("ingester", "batch_insert_failed", client=self.client_id, error=ins_res.text[:ERROR_TEXT_MAX_LEN])
                    raise Exception(f"Database insertion failed: {ins_res.text[:100]}")
            except Exception as e:
                if "Database insertion failed" in str(e):
                    raise e
                log("ingester", "batch_insert_exception", client=self.client_id, error=str(e))
                raise Exception(f"Ingestion failed: {type(e).__name__}")

        # 4. Concurrent Notifications & Individual Logging
        # We process notifications concurrently to speed up but still record individual results
        tasks = [self._process_single_lead_lifecycle(rd["row"], rd["fp"]) for rd in new_leads]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r == "inserted")
        return success_count

    async def _process_single_lead_lifecycle(self, row: dict, fingerprint: str) -> str:
        """
        Handle notification and logging for one lead.

        Order matters: log the fingerprint BEFORE notifying.
        If the log write fails this coroutine raises, which causes asyncio.gather
        to propagate the error, process_batch catches it, and the cursor does NOT
        advance — so the same rows are retried next cycle. Once the log write
        finally succeeds, the dedup check on the next cycle will catch the
        fingerprint and skip re-notification. This is the primary guard against
        the duplicate-send loop.
        """
        # Step A: Record fingerprint first — raises on failure so cursor stays back
        await self._log_ingestion(row, fingerprint, "inserted", "pending")

        # Step B: Notify (fingerprint already in log — safe even if notification fails)
        notify_status = await self._notify(row)

        # Step C: Update whatsapp_status (best-effort — notification already sent, don't abort)
        await self._patch_log_whatsapp_status(fingerprint, notify_status)

        return "inserted"

    async def _insert_with_schema_recovery(self, sanitized_leads: list[dict]):
        """
        POST the batch to Supabase with automatic PGRST204 recovery.

        PGRST204 means PostgREST's in-memory schema cache doesn't know about a
        column that exists in the database (e.g. added after PostgREST started).
        When detected, the missing column is force-added via RPC and the schema
        cache is reloaded, then the insert is retried. Loops until success or a
        non-PGRST204 error — handles batches with multiple unknown columns.
        """
        _PGRST204_RE = re.compile(r"'(\w+)' column of '(\w+)'")
        max_retries = 10

        for attempt in range(max_retries):
            res = await http_client.post(
                f"{SUPABASE_URL}/rest/v1/{self.target_table}",
                headers=SUPABASE_HEADERS,
                json=sanitized_leads,
            )
            if res.is_success:
                return res

            error_text = res.text
            if "PGRST204" not in error_text or attempt >= max_retries - 1:
                return res  # Let caller handle the failure

            # Parse the missing column and table from the error message
            m = _PGRST204_RE.search(error_text)
            if not m:
                return res

            col, table = m.group(1), sanitize_identifier(m.group(2))
            log("ingester", "pgrst204_recovery", client=self.client_id,
                column=col, table=table, attempt=attempt + 1)

            # Force-add the column (IF NOT EXISTS — safe to call even if it exists)
            add_res = await http_client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/add_missing_columns",
                headers=SUPABASE_HEADERS,
                json={"p_schema": "seed_sync", "p_table": table, "p_columns": [col]},
            )
            if not add_res.is_success:
                log("ingester", "pgrst204_add_failed", client=self.client_id,
                    column=col, error=add_res.text[:ERROR_TEXT_MAX_LEN])

            await reload_pgrst_schema()

        return res  # type: ignore[return-value]  # unreachable but satisfies type checker

    async def _check_duplicates_bulk(self, fingerprints: list[str]) -> set[str] | None:
        """Check which fingerprints already exist. Returns None on error to trigger fail-safe."""
        try:
            existing = set()
            chunk_size = DEDUP_CHUNK_SIZE
            headers = {**SUPABASE_HEADERS} # Uses default public schema
            
            for i in range(0, len(fingerprints), chunk_size):
                chunk = fingerprints[i:i + chunk_size]
                fp_filter = ",".join(chunk)
                r = await http_client.get(
                    f"{SUPABASE_URL}/rest/v1/ingestion_log",
                    headers=headers,
                    params={
                        "row_fingerprint": f"in.({fp_filter})",
                        "status": "eq.inserted",
                        "select": "row_fingerprint"
                    }
                )
                if r.is_success:
                    existing.update(item["row_fingerprint"] for item in r.json())
                else:
                    log("ingester", "bulk_check_http_error", error=r.text[:ERROR_TEXT_MAX_LEN])
                    return None
            return existing
        except Exception as e:
            log("ingester", "bulk_check_failed", error=str(e) or type(e).__name__)
            return None

    async def _notify(self, row: dict[str, Any]) -> str:
        """Async notification logic. Modified for Pilot Test Override."""
        phone_raw = row.get(self.config.get("phone_column", "WHATSAPP"), "")
        name_raw = row.get(self.config.get("name_column", "NOME"), "")

        # Normalize lead phone for contact card — invalid phone skips card only, not the text
        lead_res = normalizer.normalize(str(phone_raw))

        # Format message - Smart Filter (Removes {{technical}} metadata)
        msg = f"*🔥 NOVO LEAD CAPTURADO!* 🔥\n\n"
        for k, v in row.items():
            k_clean = str(k).strip()
            v_clean = str(v).strip()

            # Filter Logic:
            # 1. Skip system/internal keys
            if k_clean.lower() in ("id", "created_at", "status", "last_row_index", "sync_at"):
                continue

            # 2. Skip {{technical_placeholders}} from spreadsheet
            if "{{" in k_clean or "}}" in k_clean:
                continue

            # Note: Null values are allowed for now as requested
            msg += f"*{k_clean}*: {v_clean}\n"

        msg += "\n-------------------------\nEnvie uma mensagem agora para o cliente! ⚡"

        # ── DESTINATION RESOLUTION ──
        if NOTIFY_OVERRIDE_LIST:
            dests = NOTIFY_OVERRIDE_LIST
        else:
            dests = self.config.get("destination_phones", [])
            if not dests and self.config.get("legacy_phone"):
                dests = [self.config.get("legacy_phone")]

        if not dests:
            log("ingester", "no_destinations_configured", client=self.client_id)
            return "failed"

        statuses = []

        for dest in dests:
            if not dest:
                continue
            # Normalize destination phone — ensures correct international format (e.g. adds 55 prefix)
            dest_res = normalizer.normalize(str(dest))
            if not dest_res.valid:
                log("ingester", "invalid_dest_phone", client=self.client_id,
                    phone=dest, flags=dest_res.flags)
                statuses.append("failed")
                continue
            dest_phone = dest_res.phone

            send_res = await whatsapp.send_text(dest_phone, msg)
            if send_res.success:
                # Only send contact card if the lead's own phone is a valid mobile
                if lead_res.valid:
                    await whatsapp.send_contact(dest_phone, name_raw or "Lead", lead_res.phone)
                statuses.append("sent")
            else:
                statuses.append("failed")

                # Create ClickUp failure task if enabled (background — must log its own errors)
                if self.config.get("clickup_enabled") and self.config.get("clickup_list_id"):
                    async def _safe_clickup(list_id: str, title: str, desc: str) -> None:
                        try:
                            await create_failure_task(list_id=list_id, title=title, description=desc, assignees=[], priority=1)
                        except Exception as cu_err:
                            log("ingester", "clickup_task_exception", client=self.client_id, error=str(cu_err))
                    asyncio.create_task(_safe_clickup(
                        list_id=self.config.get("clickup_list_id"),
                        title=f"Falha Notificação ({self.client_id})",
                        desc=f"Falha ao enviar mensagem para {dest_phone} do lead {name_raw}: {send_res.error}",
                    ))
                else:
                    log("ingester", "clickup_alert_disabled", client=self.client_id)

        return "sent" if "sent" in statuses else "failed"

    async def _log_ingestion(self, row: dict, fingerprint: str, status: str, whatsapp_status: str):
        """
        Write to ingestion_log. RAISES on failure.

        Callers depend on this raising so that asyncio.gather propagates the
        error, process_batch aborts, and the cursor does not advance. This is
        the mechanism that prevents the duplicate-send loop.
        """
        log_entry = {
            "client_id": self.client_id,
            "row_fingerprint": fingerprint,
            "raw_payload": row,
            "status": status,
            "whatsapp_status": whatsapp_status,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        headers = {**SUPABASE_HEADERS}
        r = await http_client.post(
            f"{SUPABASE_URL}/rest/v1/ingestion_log",
            headers=headers,
            json=log_entry
        )
        if not r.is_success:
            log("ingester", "log_write_failed", client=self.client_id,
                http_status=r.status_code, error=r.text[:ERROR_TEXT_MAX_LEN])
            raise Exception(f"ingestion_log write failed ({r.status_code}): {r.text[:80]}")

    async def _patch_log_whatsapp_status(self, fingerprint: str, whatsapp_status: str):
        """Best-effort update of whatsapp_status after notification. Does NOT raise."""
        try:
            headers = {**SUPABASE_HEADERS}
            await http_client.patch(
                f"{SUPABASE_URL}/rest/v1/ingestion_log",
                headers=headers,
                params={
                    "row_fingerprint": f"eq.{fingerprint}",
                    "client_id": f"eq.{self.client_id}",
                },
                json={"whatsapp_status": whatsapp_status},
            )
        except Exception as e:
            log("ingester", "log_status_patch_failed", client=self.client_id,
                fp_prefix=fingerprint[:8], error=str(e))
