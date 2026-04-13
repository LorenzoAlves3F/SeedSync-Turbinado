"""
Pilot Mode — Activate only BVK_PREV
=====================================
Run from the worker/ directory:

    python scripts/set_pilot_mode.py            # preview: show what would change
    python scripts/set_pilot_mode.py --apply    # deactivate all except BVK_PREV

This is safe to run multiple times (idempotent).
"""

import asyncio
import sys
import os
import httpx
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
PILOT_CLIENT = "BVK_PREV"

HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
    "Accept-Profile": "seed_sync",
    "Content-Profile": "seed_sync",
}


async def main():
    dry_run = "--apply" not in sys.argv

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing in .env")
        return

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/source_configs",
            headers=HEADERS,
            params={"order": "client_id.asc"},
        )
        if not r.is_success:
            print(f"ERROR: failed to fetch configs: {r.status_code} {r.text[:100]}")
            return

        all_configs = r.json()
        to_deactivate = [c for c in all_configs if c["client_id"] != PILOT_CLIENT and c.get("active")]
        to_activate   = [c for c in all_configs if c["client_id"] == PILOT_CLIENT and not c.get("active")]

        print(f"\n  Pilot mode: only {PILOT_CLIENT} stays active.\n")
        print(f"  Total configs : {len(all_configs)}")
        print(f"  Will deactivate: {len(to_deactivate)}")
        print(f"  Will activate  : {len(to_activate)}")

        if to_deactivate:
            print("\n  To be DEACTIVATED:")
            for c in to_deactivate:
                print(f"    - {c['client_id']}  ({c.get('name', '')})")

        if to_activate:
            print(f"\n  To be ACTIVATED: {PILOT_CLIENT}")

        if dry_run:
            print("\n  [DRY RUN] Pass --apply to make changes.\n")
            return

        print()
        for c in to_deactivate:
            res = await client.patch(
                f"{SUPABASE_URL}/rest/v1/source_configs",
                headers=HEADERS,
                params={"id": f"eq.{c['id']}"},
                json={"active": False},
            )
            status = "OK" if res.is_success else f"FAIL {res.status_code}"
            print(f"  Deactivate {c['client_id']}: {status}")

        for c in to_activate:
            res = await client.patch(
                f"{SUPABASE_URL}/rest/v1/source_configs",
                headers=HEADERS,
                params={"id": f"eq.{c['id']}"},
                json={"active": True},
            )
            status = "OK" if res.is_success else f"FAIL {res.status_code}"
            print(f"  Activate {c['client_id']}: {status}")

        print("\n  Done. Restart the worker for changes to take effect.\n")


if __name__ == "__main__":
    asyncio.run(main())
