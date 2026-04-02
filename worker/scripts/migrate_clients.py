import httpx
import re
import os
from dotenv import load_dotenv

# Manual config load for script-level execution
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation, resolution=merge",
    "Accept-Profile": "seed_sync",
    "Content-Profile": "seed_sync"
}


def extract_sheet_id(url: str) -> str:
    """Extract ID from https://docs.google.com/spreadsheets/d/ID/edit#gid=0"""
    match = re.search(r"/d/([a-zA-Z0-9-_]{20,})", url)
    return match.group(1) if match else ""


def migrate():
    print("--- Starting migration from seed_sync.clients to source_configs ---")
    print(f"Targeting: {SUPABASE_URL}")
    
    # 1. Fetch legacy clients
    try:
        r = httpx.get(f"{SUPABASE_URL}/rest/v1/clients", headers=SUPABASE_HEADERS)
        if not r.is_success:
            print(f"Failed to fetch legacy clients: {r.status_code} - {r.text}")
            return
        legacy_clients = r.json()
    except Exception as e:
        print(f"Exception fetching legacy clients: {e}")
        return

    print(f"Found {len(legacy_clients)} legacy clients.")

    # 2. Iterate and transform
    new_configs = []
    for c in legacy_clients:
        name = c.get("name", "Unknown")
        link = c.get("link", "")
        phone = c.get("phone", "")
        
        sheet_id = extract_sheet_id(link)
        if not sheet_id:
            print(f"Warning: Could not extract sheet_id for {name} from link: {link}")
            continue

        # Clean client_id (slugify)
        client_id = re.sub(r"[^a-zA-Z0-9]", "_", name).upper()

        config = {
            "client_id": client_id,
            "name": name,
            "sheet_id": sheet_id,
            "worksheet_name": "Página1",
            "target_table": name,
            "legacy_phone": phone,
            "destination_phones": [phone] if phone else [],
            "active": True
        }
        new_configs.append(config)

    # 3. Deduplicate (in case names in old table are not unique)
    unique_configs = {c['client_id']: c for c in new_configs}.values()
    new_configs = list(unique_configs)

    # 4. Batch insert into source_configs
    if not new_configs:
        print("No valid configs to migrate.")
        return

    print(f"Migrating {len(new_configs)} records...")
    try:
        r = httpx.post(
            f"{SUPABASE_URL}/rest/v1/source_configs", 
            headers=SUPABASE_HEADERS, 
            json=new_configs
        )
        if r.is_success:
            print("Successfully migrated all clients to seed_sync.source_configs!")
        elif r.status_code == 409:
            print("Some clients already exist. Retrying one by one to migrate missing ones...")
            for config in new_configs:
                resp = httpx.post(f"{SUPABASE_URL}/rest/v1/source_configs", headers=SUPABASE_HEADERS, json=config)
                if resp.is_success:
                    print(f"Migrated: {config['client_id']}")
                elif resp.status_code == 409:
                    pass # Already exists
                else:
                    print(f"Failed to migrate {config['client_id']}: {resp.status_code}")
        else:
            print(f"Migration insertion failed: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Exception during insertion: {e}")


if __name__ == "__main__":
    migrate()
