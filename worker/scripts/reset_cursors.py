import asyncio
import os
import httpx
from app.config import SUPABASE_URL, SUPABASE_HEADERS
from app.integrations.sheets import _get_client
import time

async def reset_all_cursors():
    print("🚀 Starting Fresh Start: Resetting all cursors to present...")
    
    # 1. Fetch all active configs
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/source_configs", 
            headers=SUPABASE_HEADERS,
            params={"active": "eq.true"}
        )
        configs = r.json()
    
    print(f"Found {len(configs)} active clients.")
    
    # 2. Google Sheets client
    gs = _get_client()
    for conf in configs:
        client_name = conf['name']
        client_id = conf['client_id']
        sheet_id = conf['sheet_id']
        worksheet_name = conf['worksheet_name']
        
        # 3. FAST-FORWARD only if index is 0 (first run or failed previous)
        if conf.get('last_row_index', 0) > 0:
            print(f"   ⏩ Skipping {client_name} (already at index {conf['last_row_index']})")
            continue

        print(f"   ⏳ Checking {client_name} ({client_id})...")
        try:
            sh = gs.open_by_key(sheet_id)
            try:
                ws = sh.worksheet(worksheet_name)
            except:
                ws = sh.get_worksheet(0)
            
            all_v = ws.get_all_values()
            total_rows = len(all_v) - 1 if all_v else 0
            
            # 4. Update cursor
            async with httpx.AsyncClient() as client:
                res = await client.patch(
                    f"{SUPABASE_URL}/rest/v1/source_configs",
                    headers=SUPABASE_HEADERS,
                    params={"id": "eq." + conf['id']},
                    json={"last_row_index": total_rows}
                )
                if res.is_success:
                    print(f"   ✅ Reset to index {total_rows}")
                else:
                    print(f"   ❌ DB error: {res.status_code}")
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
        
        # Rate limit safety
        time.sleep(2.5)

    print("\n🎉 All cursors fast-forwarded to present. Start the worker when ready!")

if __name__ == "__main__":
    asyncio.run(reset_all_cursors())
