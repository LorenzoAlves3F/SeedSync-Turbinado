import gspread
import asyncio
import json
from google.oauth2.service_account import Credentials
from typing import Any
from ..config import GOOGLE_SERVICE_ACCOUNT_PATH, GOOGLE_SERVICE_ACCOUNT_JSON
from ..audit import log

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
QUOTA_BACKOFF_SECS = [5, 10, 20]  # Exponential wait times on Google API 429 errors

# ── Multi-SA client cache ────────────────────────────────────────────────────
# Key: absolute sa_file path. Special key "" = global default SA.
# Each entry is a lazily-initialized gspread.Client; google-auth refreshes
# expired OAuth2 tokens transparently, so the cache never needs invalidation.
_clients: dict[str, gspread.Client] = {}


def _get_client(sa_file: str = "") -> gspread.Client:
    """
    Return a cached gspread.Client for the given SA file path.
    sa_file="" uses the global default SA (GOOGLE_SERVICE_ACCOUNT_JSON env var
    with file fallback). Any other value loads that absolute path directly.
    """
    if sa_file in _clients:
        return _clients[sa_file]

    if sa_file == "":
        # Default SA — preserve existing cloud JSON-env-var / truncation-fallback logic
        if GOOGLE_SERVICE_ACCOUNT_JSON:
            try:
                info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
                creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            except (json.JSONDecodeError, ValueError):
                log("sheets", "json_env_corrupted_using_file", path=GOOGLE_SERVICE_ACCOUNT_PATH)
                creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_PATH, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_PATH, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(sa_file, scopes=SCOPES)

    client = gspread.authorize(creds)
    _clients[sa_file] = client
    log("sheets", "client_created", sa_file=sa_file or "<default>")
    return client


async def fetch_new_rows(
    sheet_id: str,
    worksheet_name: str,
    last_row_index: int,
    sa_file: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Async wrapper for gspread with exponential backoff for quota resilience.
    sa_file: absolute path to SA JSON on VPS. Empty string = global default SA.
    """
    for wait_time in QUOTA_BACKOFF_SECS + [0]:  # Last attempt has no wait
        try:
            return await asyncio.to_thread(
                _fetch_sync, sheet_id, worksheet_name, last_row_index, sa_file
            )
        except Exception as e:
            err_msg = str(e).lower()
            is_quota = "quota" in err_msg or "429" in err_msg or "rate limit" in err_msg

            if is_quota and wait_time > 0:
                log("sheets", "quota_backoff", sheet_id=sheet_id, wait=wait_time)
                await asyncio.sleep(wait_time)
                continue

            raise e

    return [], {}  # Fallback


async def get_sheet_row_count(
    sheet_id: str,
    worksheet_name: str,
    sa_file: str = "",
) -> int:
    """Return current data row count (header excluded). Used to initialize new client cursors."""
    def _count_sync() -> int:
        client = _get_client(sa_file)
        sh = client.open_by_key(sheet_id)
        try:
            ws = sh.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            log("sheets", "worksheet_not_found_fallback",
                sheet_id=sheet_id, missing=worksheet_name)
            ws = sh.get_worksheet(0)
            if not ws:
                return 0
        all_v = ws.get_all_values()
        return max(0, len(all_v) - 1)

    return await asyncio.to_thread(_count_sync)


def _fetch_sync(
    sheet_id: str,
    worksheet_name: str,
    last_row_index: int,
    sa_file: str = "",
):
    try:
        client = _get_client(sa_file)
        sh = client.open_by_key(sheet_id)

        try:
            ws = sh.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            log("sheets", "worksheet_not_found_fallback", sheet_id=sheet_id, missing=worksheet_name)
            ws = sh.get_worksheet(0)
            if not ws:
                return [], {}
            worksheet_name = ws.title

        # Optimization: Avoid get_all_values() memory blowout
        try:
            # 1. Fetch only row 1 for headers
            headers_raw = ws.row_values(1)
            if not headers_raw:
                return [], {}
            headers = [str(h).strip() for h in headers_raw]

            # Convert column count to letter (e.g. 5 -> E, 27 -> AA)
            def col_letter(n: int) -> str:
                res = ""
                while n > 0:
                    n, rem = divmod(n - 1, 26)
                    res = chr(65 + rem) + res
                return res

            max_col = col_letter(len(headers))

            # 2. Fetch strictly forward from the cursor
            start_row = max(2, last_row_index + 2)
            new_raw = ws.get(f"A{start_row}:{max_col}")

            log("sheets", "scanning_range", range=f"A{start_row}:{max_col}", buffer=0)

        except gspread.exceptions.APIError as e:
            if "exceeds grid limits" in str(e):
                return [], {}
            log("sheets", "get_range_api_error", sheet_id=sheet_id, error=str(e))
            return [], {}
        except Exception as e:
            log("sheets", "get_range_error", sheet_id=sheet_id, error=str(e))
            return [], {}

        if not new_raw:
            return [], {}

        new_rows = []
        for raw_row in new_raw:
            row_dict: dict[str, Any] = {}
            for i, header in enumerate(headers):
                if header:
                    row_dict[header] = raw_row[i] if i < len(raw_row) else ""
            new_rows.append(row_dict)

        header_sample = {h: "" for h in headers if h}
        log("sheets", "rows_fetched",
            sheet_id=sheet_id, worksheet=worksheet_name,
            from_index=last_row_index, new_count=len(new_rows))
        return new_rows, header_sample

    except Exception as e:
        log("sheets", "fetch_error", sheet_id=sheet_id, error=str(e) or type(e).__name__)
        return [], {}
