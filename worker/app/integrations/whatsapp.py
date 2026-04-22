from dataclasses import dataclass
from typing import Optional
from ..config import ZAPI_BASE_URL, ZAPI_CLIENT_TOKEN, DRY_RUN
from ..http_client import http_client
from ..audit import log


@dataclass
class SendResult:
    success: bool
    provider: str = "zapi"
    status_code: Optional[int] = None
    error: Optional[str] = None
    message_id: Optional[str] = None


class ZApiProvider:
    """Z-API WhatsApp provider. Async version."""

    HEADERS = {"Client-Token": ZAPI_CLIENT_TOKEN}

    async def send_text(self, phone: str, message: str) -> SendResult:
        if DRY_RUN:
            log("whatsapp", "DRY_RUN send_text", phone=phone)
            return SendResult(success=True, provider="zapi_dry_run")
        try:
            r = await http_client.post(
                f"{ZAPI_BASE_URL}send-text",
                headers=self.HEADERS,
                json={"phone": phone, "message": message},
            )
            if r.is_success:
                data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                return SendResult(success=True, status_code=r.status_code,
                                  message_id=data.get("zaapId") or data.get("messageId"))
            return SendResult(success=False, status_code=r.status_code,
                              error=r.text[:200])
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def send_contact(self, phone: str, contact_name: str, contact_phone: str) -> SendResult:
        if DRY_RUN:
            log("whatsapp", "DRY_RUN send_contact", phone=phone)
            return SendResult(success=True, provider="zapi_dry_run")
        try:
            r = await http_client.post(
                f"{ZAPI_BASE_URL}send-contact",
                headers=self.HEADERS,
                json={"phone": phone, "contactName": contact_name, "contactPhone": contact_phone},
            )
            if r.is_success:
                return SendResult(success=True, status_code=r.status_code)
            return SendResult(success=False, status_code=r.status_code,
                              error=r.text[:200])
        except Exception as e:
            return SendResult(success=False, error=str(e))


# Default provider instance
whatsapp = ZApiProvider()
