import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
from .config import SUPABASE_URL, SUPABASE_HEADERS, ZAPI_CLIENT_TOKEN
from .utils.sheets_utils import list_worksheets, get_sheet_columns

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    if not SUPABASE_URL or not SUPABASE_URL.startswith("http"):
        print("❌ CRITICAL: SUPABASE_URL is missing or invalid!")
    if not SUPABASE_HEADERS.get("apikey"):
        print("❌ CRITICAL: SUPABASE_SERVICE_ROLE_KEY is missing!")
    yield

app = FastAPI(title="Seed Sync API", lifespan=lifespan)

# CORS — allow all origins by default since the API has no auth.
# Override by setting CORS_ORIGINS=https://example.com,https://other.com
_cors_env = os.getenv("CORS_ORIGINS", "").strip()
origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=origins != ["*"],  # credentials require specific origins
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global client for connection pooling
http_client = httpx.AsyncClient(limits=httpx.Limits(max_connections=50, max_keepalive_connections=20), timeout=20.0)


class ClientConfig(BaseModel):
    client_id: str = ""
    name: str
    sheet_id: str
    worksheet_name: str
    target_table: str = ""
    phone_column: str = "WHATSAPP"
    name_column: str = "NOME"
    required_columns: List[str] = ["NOME", "WHATSAPP"]
    destination_phones: List[str] = []
    clickup_list_id: Optional[str] = None
    clickup_enabled: bool = True
    active: bool = True
    google_sa_id: Optional[str] = None


class ClientConfigPatch(BaseModel):
    name: Optional[str] = None
    sheet_id: Optional[str] = None
    worksheet_name: Optional[str] = None
    phone_column: Optional[str] = None
    name_column: Optional[str] = None
    required_columns: Optional[List[str]] = None
    destination_phones: Optional[List[str]] = None
    clickup_list_id: Optional[str] = None
    clickup_enabled: Optional[bool] = None
    active: Optional[bool] = None
    google_sa_id: Optional[str] = None


class GoogleServiceAccount(BaseModel):
    name: str
    email: str
    sa_file: str  # Absolute path on VPS, e.g. /opt/apps/seedsync/worker/credentials/agro.json


class ResetCursorRequest(BaseModel):
    row_index: int


# ──────────────────── Health ────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "seed-sync-api"}


# ──────────────────── Configs CRUD ────────────────────

@app.get("/configs")
async def get_configs():
    r = await http_client.get(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=SUPABASE_HEADERS,
        params={"order": "created_at.desc"},
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@app.get("/configs/stats")
async def get_config_stats():
    """Dashboard summary: total, active, inactive counts."""
    r = await http_client.get(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=SUPABASE_HEADERS,
        params={"select": "client_id,active,name"},
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    configs = r.json()
    total = len(configs)
    active = sum(1 for c in configs if c.get("active"))
    return {"total": total, "active": active, "inactive": total - active}


@app.get("/configs/{client_id}")
async def get_config(client_id: str):
    r = await http_client.get(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=SUPABASE_HEADERS,
        params={"client_id": f"eq.{client_id}", "limit": "1"},
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    data = r.json()
    if not data:
        raise HTTPException(status_code=404, detail="Client not found")
    return data[0]


@app.post("/configs")
async def create_config(config: ClientConfig):
    config.client_id = re.sub(r"[^A-Z0-9]", "_", config.name.upper().strip())
    config.target_table = config.client_id

    r = await http_client.post(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=SUPABASE_HEADERS,
        json=config.model_dump(),
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@app.patch("/configs/{client_id}")
async def update_config(client_id: str, patch: ClientConfigPatch):
    payload = patch.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    headers = {**SUPABASE_HEADERS, "Prefer": "return=representation"}
    r = await http_client.patch(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=headers,
        params={"client_id": f"eq.{client_id}"},
        json=payload,
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    data = r.json()
    if not data:
        raise HTTPException(status_code=404, detail="Client not found")
    return data[0]


@app.post("/configs/{client_id}/reset-cursor")
async def reset_cursor(client_id: str, body: ResetCursorRequest):
    """Move last_row_index to the given row, causing the worker to re-ingest from that point."""
    if body.row_index < 0:
        raise HTTPException(status_code=400, detail="row_index must be >= 0")
    headers = {**SUPABASE_HEADERS, "Prefer": "return=representation"}
    r = await http_client.patch(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=headers,
        params={"client_id": f"eq.{client_id}"},
        json={"last_row_index": body.row_index},
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    data = r.json()
    if not data:
        raise HTTPException(status_code=404, detail="Client not found")
    return data[0]


@app.delete("/configs/{client_id}")
async def delete_config(client_id: str):
    r = await http_client.delete(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=SUPABASE_HEADERS,
        params={"client_id": f"eq.{client_id}"},
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"deleted": client_id}


# ──────────────────── Logs ────────────────────

@app.get("/logs")
async def get_logs(
    limit: int = 50,
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    whatsapp_status: Optional[str] = None,
):
    params: dict = {"order": "processed_at.desc", "limit": str(limit)}
    if client_id:
        params["client_id"] = f"eq.{client_id}"
    if status:
        params["status"] = f"eq.{status}"
    if whatsapp_status:
        params["whatsapp_status"] = f"eq.{whatsapp_status}"

    headers = {**SUPABASE_HEADERS, "Accept-Profile": "seed_sync"}
    r = await http_client.get(
        f"{SUPABASE_URL}/rest/v1/ingestion_log",
        headers=headers,
        params=params,
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


# ──────────────────── Bulk Operations ────────────────────

@app.post("/configs/sync-reset")
async def reset_all_cursors():
    """Safety Protocol: Roll back all active cursors by 50 rows to force a re-scan."""
    r = await http_client.get(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=SUPABASE_HEADERS,
        params={"active": "eq.true"},
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail="Failed to fetch cluster state")
    
    configs = r.json()
    count = 0
    
    for conf in configs:
        old_idx = conf.get("last_row_index", 0)
        new_idx = max(0, old_idx - 50)
        
        await http_client.patch(
            f"{SUPABASE_URL}/rest/v1/source_configs",
            headers=SUPABASE_HEADERS,
            params={"client_id": f"eq.{conf['client_id']}"},
            json={"last_row_index": new_idx}
        )
        count += 1
        
    return {"status": "reset_initiated", "cluster_size": count, "buffer_size": 50}



# ──────────────────── Credentials (Google Service Accounts) ────────────────

# public-schema tables must NOT receive Accept-Profile/Content-Profile headers
_PUBLIC_HEADERS = {
    "apikey": SUPABASE_HEADERS["apikey"],
    "Authorization": SUPABASE_HEADERS["Authorization"],
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


@app.get("/credentials")
async def list_credentials():
    """List all registered Google Service Accounts."""
    r = await http_client.get(
        f"{SUPABASE_URL}/rest/v1/google_service_accounts",
        headers=_PUBLIC_HEADERS,
        params={"order": "created_at.desc"},
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@app.post("/credentials", status_code=201)
async def create_credential(body: GoogleServiceAccount):
    """Register a new Google Service Account (credentials file must already be on VPS)."""
    r = await http_client.post(
        f"{SUPABASE_URL}/rest/v1/google_service_accounts",
        headers=_PUBLIC_HEADERS,
        json=body.model_dump(),
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()


@app.delete("/credentials/{credential_id}")
async def delete_credential(credential_id: str):
    """
    Remove a Google Service Account record. Associated source_configs rows will have
    google_sa_id set to NULL (ON DELETE SET NULL) and fall back to the global default SA.
    """
    r = await http_client.delete(
        f"{SUPABASE_URL}/rest/v1/google_service_accounts",
        headers=_PUBLIC_HEADERS,
        params={"id": f"eq.{credential_id}"},
    )
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return {"deleted": credential_id}


# ──────────────────── Sheets Exploration ────────────────────

@app.get("/sheets/{sheet_id}/worksheets")
async def get_worksheets(sheet_id: str):
    try:
        return list_worksheets(sheet_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/sheets/{sheet_id}/worksheets/{worksheet_name}/columns")
async def get_columns(sheet_id: str, worksheet_name: str):
    try:
        return get_sheet_columns(sheet_id, worksheet_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ──────────────────── Z-API Delivery Webhook ────────────────────

@app.post("/webhook/zapi", status_code=200)
async def zapi_delivery_webhook(request: Request):
    """
    Receive Z-API delivery callbacks and update delivery status in ingestion_log
    and notification_queue.

    Configure in Z-API dashboard:
      Webhook URL = https://api-seedsync.3fventure.tech/webhook/zapi
      Event: DeliveryCallback (or MessageStatusCallback)
    """
    try:
        payload = await request.json()
    except Exception:
        return {"ok": False, "error": "invalid_json"}

    # Z-API sends different event shapes depending on version/plan.
    # Extract the common fields we care about.
    message_id = (
        payload.get("messageId")
        or payload.get("zaapId")
        or payload.get("momentsId")
    )
    is_delivered = (
        payload.get("isDelivered") is True
        or payload.get("status") in ("DELIVERED", "READ")
    )

    if not message_id or not is_delivered:
        return {"ok": True, "action": "ignored"}

    public_headers = {
        "apikey": SUPABASE_HEADERS["apikey"],
        "Authorization": SUPABASE_HEADERS["Authorization"],
        "Content-Type": "application/json",
    }

    # Best-effort updates — don't raise on individual failures
    await http_client.patch(
        f"{SUPABASE_URL}/rest/v1/notification_queue",
        headers=public_headers,
        params={"zapi_message_id": f"eq.{message_id}"},
        json={"status": "delivered"},
    )
    await http_client.patch(
        f"{SUPABASE_URL}/rest/v1/ingestion_log",
        headers={**SUPABASE_HEADERS},
        params={"zapi_message_id": f"eq.{message_id}"},
        json={"whatsapp_status": "delivered"},
    )

    return {"ok": True, "messageId": message_id}
