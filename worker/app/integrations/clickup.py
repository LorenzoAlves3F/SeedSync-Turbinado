from ..config import CLICKUP_API_TOKEN, DRY_RUN
from ..http_client import http_client
from ..config import CLICKUP_API_TOKEN, DRY_RUN
from ..audit import log

CLICKUP_BASE = "https://api.clickup.com/api/v2"
CLICKUP_HEADERS = {"Authorization": CLICKUP_API_TOKEN, "Content-Type": "application/json"}


async def create_failure_task(
    list_id: str,
    title: str,
    description: str,
    assignees: list[int],
    priority: int = 1,
) -> bool:
    """
    Creates a ClickUp task to alert the team of a WhatsApp send failure.
    Async version.
    """
    if DRY_RUN:
        log("clickup", "DRY_RUN create_failure_task", list_id=list_id, title=title)
        return True

    if not CLICKUP_API_TOKEN:
        return False

        try:
            payload = {
                "name": title,
                "description": description,
                "assignees": assignees,
                "priority": priority,
                "status": "pendente",
                "notify_all": True,
            }
            r = await http_client.post(
                f"{CLICKUP_BASE}/list/{list_id}/task",
                headers=CLICKUP_HEADERS,
                json=payload,
            )
            if r.is_success:
                log("clickup", "Task created", list_id=list_id, task_id=r.json().get("id"))
                return True
            log("clickup", "Task creation failed", status=r.status_code, body=r.text[:200])
            return False
        except Exception as e:
            log("clickup", "Exception creating task", error=str(e))
            return False
