from ..http_client import http_client
from typing import Any
from ..config import SUPABASE_URL, SUPABASE_HEADERS, DRY_RUN
from ..audit import log
from .validator import sanitize_identifier


async def reload_pgrst_schema() -> None:
    """Signal PostgREST to reload its schema cache.

    Must be called after any DDL change (ALTER TABLE, CREATE TABLE) so that
    PostgREST's in-memory schema cache reflects the new columns immediately.
    Requires the seed_sync.reload_pgrst_schema() SQL function to exist in Supabase:

        CREATE OR REPLACE FUNCTION seed_sync.reload_pgrst_schema()
        RETURNS void LANGUAGE sql SECURITY DEFINER AS $$
          SELECT pg_notify('pgrst', 'reload schema');
        $$;
    """
    try:
        res = await http_client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/reload_pgrst_schema",
            headers=SUPABASE_HEADERS,
            json={},
        )
        if not res.is_success:
            log("schema", "reload_pgrst_failed", hint="create seed_sync.reload_pgrst_schema() in Supabase SQL editor")
    except Exception as e:
        log("schema", "reload_pgrst_exception", error=str(e))


async def ensure_table_columns(table_name: str, sample_row: dict[str, Any]) -> bool:
    """
    Check if the target table exists and has all required columns.
    Uses the existing Supabase RPCs (mirrors the n8n logic).
    Returns True if table is ready, False on failure.

    NOTE: table_name is passed to RPCs as-is (preserving original case from
    source_configs) because the tables in Supabase are case-sensitive (e.g.
    "RURALTECH", "AGROLIVEIRA"). Only column names are sanitized via
    sanitize_identifier since they come from untrusted Google Sheet headers.
    """
    if DRY_RUN:
        return True

    # Table name: preserve original case (trusted value from source_configs DB)
    # Column names: sanitize (untrusted values from Google Sheet headers)
    safe_row = {sanitize_identifier(k): v for k, v in sample_row.items() if sanitize_identifier(k)}

    try:
        # Step 1: Check if table exists
        check_res = await http_client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/check_table_seed_sync",
            headers=SUPABASE_HEADERS,
            json={"table_name": table_name},
        )
        exists = check_res.is_success and check_res.json() is True

        if not exists:
            log("schema", "table_missing", table=table_name)
            columns = {k: "text" for k in safe_row.keys() if k}
            create_res = await http_client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/create_table_with_defaults",
                headers=SUPABASE_HEADERS,
                json={"schema_name": "seed_sync", "table_name": table_name, "columns": columns},
            )
            if not create_res.is_success:
                log("schema", "create_failed", table=table_name, error=create_res.text[:200])
                return False
            log("schema", "table_created", table=table_name)
            await reload_pgrst_schema()
            return True

        # Step 2: Sync columns
        cols_res = await http_client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/get_table_columns",
            headers=SUPABASE_HEADERS,
            json={"p_schema": "seed_sync", "p_table": table_name},
        )
        if not cols_res.is_success:
            return False

        existing_cols = {row["column_name"] for row in cols_res.json()}
        incoming_cols = [k for k in safe_row.keys() if k and k not in existing_cols]

        if incoming_cols:
            log("schema", "new_columns_detected", table=table_name, columns=incoming_cols)
            add_res = await http_client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/add_missing_columns",
                headers=SUPABASE_HEADERS,
                json={"p_schema": "seed_sync", "p_table": table_name, "p_columns": incoming_cols},
            )
            if not add_res.is_success:
                log("schema", "alter_failed", table=table_name, error=add_res.text[:200])
                return False
            log("schema", "columns_added", table=table_name, count=len(incoming_cols))
            await reload_pgrst_schema()

        return True

    except Exception as e:
        log("schema", "exception", table=table_name, error=str(e))
        return False
