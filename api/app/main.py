import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
from .config import SUPABASE_URL, SUPABASE_HEADERS
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

# Allowed origins from env or default to all for local dev
origins = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
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
        f"{SUPABASE_URL}/rest/v1/ingestion_logs",
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


# ──────────────────── Configs by ID ────────────────────

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
