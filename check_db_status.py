import asyncio
import httpx
import os
from dotenv import load_dotenv

async def check_configs():
    env_path = r"c:\Users\Lorenzo\Desktop\SeedSync\worker\.env"
    load_dotenv(dotenv_path=env_path)
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "seed_sync"
    }
    
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{url}/rest/v1/source_configs",
            headers=headers,
            params={"select": "client_id,name,active,destination_phones"}
        )
        
        if r.is_success:
            configs = r.json()
            print("--- Current Configurations ---")
            for c in configs:
                status = "ACTIVE" if c.get("active") else "INACTIVE"
                print(f"ID: {c.get('client_id')} | Name: {c.get('name')} | Status: {status} | Dests: {c.get('destination_phones')}")
        else:
            print(f"Error: {r.status_code} - {r.text}")

if __name__ == "__main__":
    asyncio.run(check_configs())
