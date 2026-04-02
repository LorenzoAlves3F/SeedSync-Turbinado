import httpx
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

def check():
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Accept-Profile": "seed_sync"
    }
    try:
        r = httpx.get(f"{SUPABASE_URL}/rest/v1/source_configs", headers=headers)
        print(f"New Table Count: {len(r.json())}")
        
        r_legacy = httpx.get(f"{SUPABASE_URL}/rest/v1/clients", headers=headers)
        print(f"Legacy Table Count: {len(r_legacy.json())}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == '__main__':
    check()
