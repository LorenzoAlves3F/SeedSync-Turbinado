import asyncio
import os
import httpx
from datetime import datetime
from dotenv import load_dotenv

# Load env from worker root
load_dotenv()

ZAPI_BASE_URL = f"https://api.z-api.io/instances/{os.getenv('ZAPI_INSTANCE_ID')}/token/{os.getenv('ZAPI_TOKEN')}/"
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

async def send_test(target_phone: str):
    print(f"🚀 Sending test lead to {target_phone}...")
    
    # Dummy lead data
    lead = {
        "NOME": "Lead de Teste",
        "WHATSAPP": "5511999999999",
        "CIDADE": "Porto Alegre",
        "ORIGEM": "Google Ads",
        "PRODUTO": "Sincronizador SeedSync"
    }
    
    # Format message exactly like LeadIngester
    msg = f"*🔥 NOVO LEAD CAPTURADO!* 🔥\n\n"
    for k, v in lead.items():
        msg += f"*{k}*: {v}\n"
    msg += "\n-------------------------\nEnvie uma mensagem agora para o cliente! ⚡"

    headers = {"Client-Token": ZAPI_CLIENT_TOKEN}
    
    async with httpx.AsyncClient() as client:
        # 1. Send Text
        print("Sending text...")
        r_text = await client.post(
            f"{ZAPI_BASE_URL}send-text",
            headers=headers,
            json={"phone": target_phone, "message": msg},
            timeout=15
        )
        print(f"Result: {r_text.status_code} - {r_text.text}")
        
        # 2. Send Contact Card
        print("Sending contact card...")
        r_contact = await client.post(
            f"{ZAPI_BASE_URL}send-contact",
            headers=headers,
            json={
                "phone": target_phone, 
                "contactName": lead["NOME"], 
                "contactPhone": "5511999999999"
            },
            timeout=15
        )
        print(f"Result: {r_contact.status_code} - {r_contact.text}")

if __name__ == "__main__":
    phone = "5554991474643"
    asyncio.run(send_test(phone))
