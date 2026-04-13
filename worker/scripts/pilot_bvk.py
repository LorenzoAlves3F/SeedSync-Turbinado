"""
BVK Pilot Setup & Diagnostics
==============================
Run from the worker/ directory:

    python scripts/pilot_bvk.py              # show current state + log count
    python scripts/pilot_bvk.py --reset      # roll BVK_PREV cursor back 5 rows to re-trigger test sends
    python scripts/pilot_bvk.py --reset N    # roll back N rows (e.g. --reset 10)
    python scripts/pilot_bvk.py --peek       # show what rows FORMS Prev would fetch right now
    python scripts/pilot_bvk.py --zero       # reset cursor ALL the way to 0 (re-process everything)

After --reset, start the worker and you will receive test notifications at NOTIFY_OVERRIDE_PHONE.
"""

import asyncio
import sys
import os
import httpx
from dotenv import load_dotenv

# ── Load env ──────────────────────────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
NOTIFY_OVERRIDE_PHONE = os.getenv("NOTIFY_OVERRIDE_PHONE", "").strip()

HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
    "Accept-Profile": "seed_sync",
    "Content-Profile": "seed_sync",
}

TARGET_CLIENT_ID = "BVK_PREV"
TARGET_WORKSHEET = "FORMS Prev"


# ── Helpers ───────────────────────────────────────────────────────────────────

def sep(char="-", n=60):
    print(char * n)


async def get_bvk_prev(client: httpx.AsyncClient) -> dict | None:
    r = await client.get(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=HEADERS,
        params={"client_id": f"eq.{TARGET_CLIENT_ID}", "limit": "1"},
    )
    if r.is_success and r.json():
        return r.json()[0]
    return None


async def get_log_count(client: httpx.AsyncClient) -> tuple[int, list]:
    """Return (total_entries, last_5_entries) for BVK_PREV in ingestion_log."""
    count_r = await client.get(
        f"{SUPABASE_URL}/rest/v1/ingestion_log",
        headers={**HEADERS, "Prefer": "count=exact"},
        params={"client_id": f"eq.{TARGET_CLIENT_ID}", "select": "id"},
    )
    total = 0
    if count_r.is_success:
        content_range = count_r.headers.get("content-range", "0/0")
        try:
            total = int(content_range.split("/")[-1])
        except Exception:
            total = len(count_r.json())

    recent_r = await client.get(
        f"{SUPABASE_URL}/rest/v1/ingestion_log",
        headers=HEADERS,
        params={
            "client_id": f"eq.{TARGET_CLIENT_ID}",
            "order": "processed_at.desc",
            "limit": "3",
            "select": "row_fingerprint,whatsapp_status,processed_at",
        },
    )
    recent = recent_r.json() if recent_r.is_success else []
    return total, recent


# ── Commands ──────────────────────────────────────────────────────────────────

async def show_state(client: httpx.AsyncClient):
    sep("=")
    print("  BVK_PREV PILOT STATUS")
    sep("=")

    override = NOTIFY_OVERRIDE_PHONE
    if override:
        print(f"\n  Notifications override  : {override}  (ALL active clients -> this phone)")
    else:
        print("\n  Notifications override  : NOT SET  (each client uses its own destination_phones)")

    conf = await get_bvk_prev(client)
    if not conf:
        print(f"\n  ERROR: {TARGET_CLIENT_ID} not found in source_configs.")
        return

    status = "ACTIVE" if conf.get("active") else "INACTIVE - worker ignores it"
    ws = conf.get("worksheet_name", "")
    ws_ok = "OK" if ws == TARGET_WORKSHEET else f"WRONG - got '{ws}' expected '{TARGET_WORKSHEET}'"
    idx = conf.get("last_row_index", 0)

    sep()
    print(f"  client_id        : {conf.get('client_id')}")
    print(f"  status           : {status}")
    print(f"  worksheet        : {ws}  [{ws_ok}]")
    print(f"  last_row_index   : {idx}  (next fetch starts at sheet row {max(2, idx + 2)})")
    print(f"  destination_phones: {conf.get('destination_phones')}")
    print(f"  sheet_id         : {conf.get('sheet_id')}")

    log_total, log_recent = await get_log_count(client)
    sep()
    print(f"  ingestion_log entries for BVK_PREV: {log_total}")
    if log_recent:
        print("  Most recent 3:")
        for e in log_recent:
            fp = e.get("row_fingerprint", "")[:12]
            wa = e.get("whatsapp_status", "?")
            ts = e.get("processed_at", "?")[:19]
            print(f"    [{ts}] fp={fp}... whatsapp={wa}")
    else:
        print("  No log entries found for BVK_PREV.")
        print("  => Either no leads were processed yet, or log writes were failing (old bug).")

    sep("=")
    # Recommendations
    print("\n  NEXT STEPS:")
    if not conf.get("active"):
        print("  1. BVK_PREV is INACTIVE. Run:  python scripts/pilot_bvk.py --activate")
    elif ws != TARGET_WORKSHEET:
        print(f"  1. Worksheet is wrong. Update via admin dashboard to '{TARGET_WORKSHEET}'.")
    elif log_total == 0 and idx > 0:
        print("  1. No log entries despite cursor being at", idx)
        print("     Old bug (silent log failure) was likely active. The fix is now applied.")
        print("     Run:  python scripts/pilot_bvk.py --reset")
        print("     Then restart the worker. 5 rows will be re-processed and sent to your phone.")
    elif idx == 0 or log_total == 0:
        print("  1. No rows processed yet. Start the worker:")
        print("     cd worker && venv/Scripts/python -m app.main")
    else:
        print(f"  1. System looks healthy. Cursor at {idx}.")
        print("     To re-trigger a test send, roll back the cursor:")
        print("     python scripts/pilot_bvk.py --reset")
        print("     Then restart the worker.")
    print()


async def peek_sheet(client: httpx.AsyncClient):
    conf = await get_bvk_prev(client)
    if not conf:
        print(f"  ERROR: {TARGET_CLIENT_ID} not found.")
        return

    sheet_id = conf["sheet_id"]
    worksheet_name = conf["worksheet_name"]
    last_index = conf.get("last_row_index", 0)

    print(f"\n  Sheet    : {sheet_id}")
    print(f"  Worksheet: {worksheet_name}")
    print(f"  Cursor   : {last_index}  (fetching from sheet row {max(2, last_index + 2)})\n")

    # Import from app package (run from worker/ directory)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, base)
    try:
        from app.integrations.sheets import _fetch_sync
        rows, _ = _fetch_sync(sheet_id, worksheet_name, last_index)
        if not rows:
            print("  No new rows found from this cursor position.")
            print("  To re-test, run: python scripts/pilot_bvk.py --reset")
        else:
            print(f"  {len(rows)} unprocessed row(s) available. First 3:\n")
            for i, row in enumerate(rows[:3]):
                print(f"  Row {i+1}: {row}\n")
            if len(rows) > 3:
                print(f"  ... and {len(rows) - 3} more")
    except Exception as e:
        print(f"  Sheet read failed: {e}")


async def reset_cursor(client: httpx.AsyncClient, rollback: int):
    conf = await get_bvk_prev(client)
    if not conf:
        print(f"  ERROR: {TARGET_CLIENT_ID} not found.")
        return

    old_idx = conf.get("last_row_index", 0)
    new_idx = max(0, old_idx - rollback)

    r = await client.patch(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=HEADERS,
        params={"id": f"eq.{conf['id']}"},
        json={"last_row_index": new_idx},
    )
    if r.is_success:
        print(f"  OK: {TARGET_CLIENT_ID} cursor {old_idx} -> {new_idx}")
        print(f"  Worker will now fetch ~{rollback} rows from 'FORMS Prev' on next cycle.")
        print(f"  Restart the worker and watch for notifications at: {NOTIFY_OVERRIDE_PHONE or conf.get('destination_phones')}")
    else:
        print(f"  FAILED: {r.status_code} {r.text[:100]}")


async def zero_cursor(client: httpx.AsyncClient):
    await reset_cursor(client, rollback=10_000)  # effectively sets to 0 via max(0, ...)


async def activate(client: httpx.AsyncClient):
    conf = await get_bvk_prev(client)
    if not conf:
        print(f"  ERROR: {TARGET_CLIENT_ID} not found.")
        return
    if conf.get("active"):
        print(f"  {TARGET_CLIENT_ID} is already active.")
        return
    r = await client.patch(
        f"{SUPABASE_URL}/rest/v1/source_configs",
        headers=HEADERS,
        params={"id": f"eq.{conf['id']}"},
        json={"active": True},
    )
    print("  Activated." if r.is_success else f"  FAILED: {r.text[:100]}")


# ── Entry Point ───────────────────────────────────────────────────────────────

async def main():
    args = sys.argv[1:]
    arg_set = set(args)

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing in .env")
        return

    async with httpx.AsyncClient(timeout=15.0) as client:
        if "--reset" in arg_set:
            # Optional numeric arg after --reset (default 5)
            rollback = 5
            idx = args.index("--reset")
            if idx + 1 < len(args):
                try:
                    rollback = int(args[idx + 1])
                except ValueError:
                    pass
            print(f"\n  Rolling BVK_PREV cursor back {rollback} rows...")
            await reset_cursor(client, rollback)
        elif "--zero" in arg_set:
            print("\n  Resetting BVK_PREV cursor to 0 (re-process all rows)...")
            await zero_cursor(client)
        elif "--peek" in arg_set:
            await peek_sheet(client)
        elif "--activate" in arg_set:
            await activate(client)
        else:
            await show_state(client)
        print()


if __name__ == "__main__":
    asyncio.run(main())
