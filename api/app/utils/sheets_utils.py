import gspread
import json
import os
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Cloud: credentials passed as JSON string. Local: file path.
_SA_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

# Resolve file path: api/.env -> api/ dir; fall back to sibling worker/ dir for local dev.
_api_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SA_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "").strip() or os.path.join(
    os.path.dirname(_api_dir), "worker", "google-service-account.json"
)


def get_sheets_client():
    if _SA_JSON:
        info = json.loads(_SA_JSON)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(_SA_PATH, scopes=SCOPES)
    return gspread.authorize(creds)


def list_worksheets(sheet_id: str) -> List[Dict[str, str]]:
    """List all worksheets (tabs) in a spreadsheet."""
    client = get_sheets_client()
    sh = client.open_by_key(sheet_id)
    return [{"id": str(ws.id), "title": ws.title} for ws in sh.worksheets()]


def get_sheet_columns(sheet_id: str, worksheet_name: str) -> List[str]:
    """Get the first row (headers) of a worksheet."""
    client = get_sheets_client()
    sh = client.open_by_key(sheet_id)
    ws = sh.worksheet(worksheet_name)
    rows = ws.get_all_values()
    if not rows:
        return []
    return [h.strip() for h in rows[0] if h.strip()]
