"""
Standalone cursor reset - no app module imports needed.
Resets last_row_index to current sheet length for clients still at 0.
"""
import os
import time
import httpx
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
GOOGLE_SA_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "./google-service-account.json").strip()

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Accept-Profile": "seed_sync",
    "Content-Profile": "seed_sync",
}

def get_gs_client():
    creds = Credentials.from_service_account_file(
        GOOGLE_SA_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    return gspread.authorize(creds)

def reset_remaining():
    print("🔍 Checking which clients still need a cursor reset...")
    
    r = httpx.get(f"{SUPABASE_URL}/rest/v1/source_configs", headers=HEADERS, params={"active": "eq.true"})
    all_configs = r.json()
    
    # Only reset clients still at 0
    needs_reset = [c for c in all_configs if c.get("last_row_index", 0) == 0]
    already_done = len(all_configs) - len(needs_reset)
    
    print(f"✅ Already reset: {already_done}  |  ⏳ Still need reset: {len(needs_reset)}")
    
    if not needs_reset:
        print("\n🎉 All clients are already fast-forwarded! You can start the worker now.")
        return
    
    gs = get_gs_client()
    
    for conf in needs_reset:
        name = conf["name"]
        sheet_id = conf["sheet_id"]
        worksheet_name = conf["worksheet_name"]
        conf_id = conf["id"]
        
        print(f"   ⏳ {name}...")
        try:
            sh = gs.open_by_key(sheet_id)
            try:
                ws = sh.worksheet(worksheet_name)
            except Exception:
                ws = sh.get_worksheet(0)
            
            all_v = ws.get_all_values()
            total_rows = max(0, len(all_v) - 1)
            
            res = httpx.patch(
                f"{SUPABASE_URL}/rest/v1/source_configs",
                headers=HEADERS,
                params={"id": f"eq.{conf_id}"},
                json={"last_row_index": total_rows}
            )
            if res.is_success:
                print(f"   ✅ Set to index {total_rows}")
            else:
                print(f"   ❌ DB error: {res.status_code} - {res.text[:80]}")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
        
        time.sleep(2.5)  # Stay within Google Sheets rate limits
    
    print("\n🎉 Done! All cursors are at the present. Restart the worker when ready.")

if __name__ == "__main__":
    reset_remaining()
