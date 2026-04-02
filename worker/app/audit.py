import json
import logging
from datetime import datetime, timezone
from typing import Any
from .config import LOG_LEVEL

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(message)s",
)
_logger = logging.getLogger("seedsync")

# Silence noisy external request logs globally
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def log(component: str, event: str, **kwargs: Any) -> None:
    """
    Structured JSON log line. All worker events go through here.
    
    Example output:
    {"ts": "2026-03-27T10:00:00Z", "component": "sheets", "event": "row_fetched", "client": "geotech", "row": 5}
    """
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "component": component,
        "event": event,
        **kwargs,
    }
    _logger.info(json.dumps(record, ensure_ascii=False, default=str))
