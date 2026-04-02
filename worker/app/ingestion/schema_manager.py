from ..http_client import http_client
from typing import Any
from ..config import SUPABASE_URL, SUPABASE_HEADERS, DRY_RUN
from ..audit import log
from .validator import sanitize_identifier


async def ensure_table_columns(table_name: str, sample_row: dict[str, Any]) -> bool:
    """
    Check if the target table exists and has all required columns.
    Uses the existing Supabase RPCs (mirrors the n8n logic).
    Returns True if table is ready, False on failure.
    """
    if DRY_RUN:
        return True

    # Sanitize inputs for SQL safety before calling database
    safe_table = sanitize_identifier(table_name)
    safe_row = {sanitize_identifier(k): v for k, v in sample_row.items() if sanitize_identifier(k)}

    try:
        # Step 1: Check if table exists
        check_res = await http_client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/check_table_seed_sync",
            headers=SUPABASE_HEADERS,
            json={"table_name": safe_table},
        )
        exists = check_res.is_success and check_res.json() is True

        if not exists:
            log("schema", "table_missing", table=safe_table)
            # Build columns payload e.g. {"col1": "text", "col2": "text"}
            columns = {k: "text" for k in safe_row.keys() if k}
            create_res = await http_client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/create_table_with_defaults",
                headers=SUPABASE_HEADERS,
                json={"schema_name": "seed_sync", "table_name": safe_table, "columns": columns},
            )
            if not create_res.is_success:
                log("schema", "create_failed", table=safe_table, error=create_res.text[:200])
                return False
            log("schema", "table_created", table=safe_table)
            return True

        # Step 2: Sync columns
        cols_res = await http_client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/get_table_columns",
            headers=SUPABASE_HEADERS,
            json={"p_schema": "seed_sync", "p_table": safe_table},
        )
        if not cols_res.is_success:
            return False

        existing_cols = {row["column_name"] for row in cols_res.json()}
        incoming_cols = [k for k in safe_row.keys() if k and k not in existing_cols]

        if incoming_cols:
            log("schema", "new_columns_detected", table=safe_table, columns=incoming_cols)
            add_res = await http_client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/add_missing_columns",
                headers=SUPABASE_HEADERS,
                json={"p_schema": "seed_sync", "p_table": safe_table, "p_columns": incoming_cols},
            )
            if not add_res.is_success:
                log("schema", "alter_failed", table=safe_table, error=add_res.text[:200])
                return False
            log("schema", "columns_added", table=safe_table, count=len(incoming_cols))

        return True

    except Exception as e:
        log("schema", "exception", table=safe_table, error=str(e))
        return False
