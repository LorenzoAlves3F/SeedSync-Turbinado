import sys
import os
import asyncio
import httpx
from google.oauth2.service_account import Credentials
import gspread

# Add parent directory to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.config import SUPABASE_URL, SUPABASE_HEADERS, GOOGLE_SERVICE_ACCOUNT_PATH

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def get_gspread_client():
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_PATH, scopes=SCOPES)
    return gspread.authorize(creds)

async def main():
    print("Fetching configs...")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/source_configs",
            headers=SUPABASE_HEADERS,
            params={"select": "client_id,sheet_id,worksheet_name", "order": "client_id.asc"}
        )
        if not r.is_success:
            print("Failed to fetch configs:", r.text)
            return
        configs = r.json()

    suspicious = [c for c in configs if c.get("worksheet_name") in ('Página1', 'Sheet1', 'Página 1', 'Sheet 1')]
    print(f"Found {len(suspicious)} clients with suspicious worksheet names.")

    if not suspicious:
        return

    gclient = get_gspread_client()
    updates = []
    
    print("\nScanning Google Sheets...")
    for c in suspicious:
        client_id = c["client_id"]
        sheet_id = c["sheet_id"]
        old_name = c["worksheet_name"]
        
        try:
            sh = gclient.open_by_key(sheet_id)
            ws = sh.get_worksheet(0)
            await asyncio.sleep(2.5) # Avoid strictly 60 per min
            if not ws:
                print(f"[{client_id}] Failed: Workspace empty.")
                continue
                
            true_name = ws.title
            
            if true_name != old_name:
                print(f"[{client_id}] Must update '{old_name}' -> '{true_name}'")
                updates.append((client_id, true_name))
            else:
                print(f"[{client_id}] Keeping '{old_name}' (it's correct)")
                
        except Exception as e:
            print(f"[{client_id}] Gspread error: {e}")

    print(f"\nTotal clients to update in database: {len(updates)}")
    
    if not updates:
        print("Nothing to patch.")
        return
        
    print("Patching Supabase...")
    async with httpx.AsyncClient() as client:
        for cid, tname in updates:
            print(f"Patching {cid}...", end=" ")
            r = await client.patch(
                f"{SUPABASE_URL}/rest/v1/source_configs",
                headers={**SUPABASE_HEADERS, "Prefer": "return=minimal"},
                params={"client_id": f"eq.{cid}"},
                json={"worksheet_name": tname}
            )
            if r.is_success:
                print("OK")
            else:
                print("FAIL:", r.text)

    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())
