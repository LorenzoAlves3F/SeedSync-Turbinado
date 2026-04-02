import gspread
from google.oauth2.service_account import Credentials
import os
from typing import List, Dict, Any

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Path to the same service account used by the worker
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SERVICE_ACCOUNT_PATH = os.path.join(BASE_DIR, "worker", "google-service-account.json")

def get_sheets_client():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH, scopes=SCOPES)
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
