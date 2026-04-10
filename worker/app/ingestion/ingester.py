import hashlib
import json
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


class LeadIngester:
    """Core logic for lead processing: async and batch optimized."""

    def __init__(self, client_id: str, config: dict):
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

                ins_res = await http_client.post(
                    f"{SUPABASE_URL}/rest/v1/{self.target_table}",
                    headers=SUPABASE_HEADERS,
                    json=sanitized_leads
                )
                if not ins_res.is_success:
                    log("ingester", "batch_insert_failed", client=self.client_id, error=ins_res.text[:200])
                    # RAISE: This stops the scheduler from advancing the last_row_index
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
        """Helper to handle notification and logging for one lead within a batch."""
        # Step A: Notify
        notify_status = await self._notify(row)
        
        # Step B: Log
        await self._log_ingestion(row, fingerprint, "inserted", notify_status)
        return "inserted"

    async def _check_duplicates_bulk(self, fingerprints: list[str]) -> set[str] | None:
        """Check which fingerprints already exist. Returns None on error to trigger fail-safe."""
        try:
            existing = set()
            chunk_size = 50
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
                    log("ingester", "bulk_check_http_error", error=r.text[:200])
                    return None
            return existing
        except Exception as e:
            log("ingester", "bulk_check_failed", error=str(e) or type(e).__name__)
            return None

    async def _notify(self, row: dict[str, Any]) -> str:
        """Async notification logic. Modified for Pilot Test Override."""
        phone_raw = row.get(self.config.get("phone_column", "WHATSAPP"), "")
        name_raw = row.get(self.config.get("name_column", "NOME"), "")
        
        res = normalizer.normalize(str(phone_raw))
        if not res.valid:
            return "phone_invalid"
        
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
            if not dest: continue
            send_res = await whatsapp.send_text(dest, msg)
            if send_res.success:
                await whatsapp.send_contact(dest, name_raw or "Lead", res.phone)
                statuses.append("sent")
            else:
                statuses.append("failed")
                
                # Create ClickUp failure task if enabled
                if self.config.get("clickup_enabled") and self.config.get("clickup_list_id"):
                    # Use a background task for clickup to avoid blocking
                    asyncio.create_task(create_failure_task(
                        list_id=self.config.get("clickup_list_id"),
                        title=f"Falha Notificação ({self.client_id})",
                        description=f"Falha ao enviar mensagem para {dest} do lead {name_raw}: {send_res.error}",
                        assignees=[],
                        priority=1
                    ))
                else:
                    log("ingester", "clickup_alert_disabled", client=self.client_id)

        return "sent" if "sent" in statuses else "failed"

    async def _log_ingestion(self, row: dict, fingerprint: str, status: str, whatsapp_status: str):
        """Async logging using the correct schema."""
        try:
            log_entry = {
                "client_id": self.client_id,
                "row_fingerprint": fingerprint,
                "raw_payload": row,
                "status": status,
                "whatsapp_status": whatsapp_status,
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
            # Async write using standard public profile
            headers = {**SUPABASE_HEADERS}
            r = await http_client.post(f"{SUPABASE_URL}/rest/v1/ingestion_log", headers=headers, json=log_entry)
            if not r.is_success:
                log("ingester", "log_write_failed", client=self.client_id, error=r.text[:200])
        except Exception as e:
            log("ingester", "log_write_exception", client=self.client_id, error=str(e))
