import os
from dotenv import load_dotenv

# Env resolution order (first found wins):
#   1. worker/.env   — Orchestrator with app_path=worker/ (or local dev)
#   2. root .env     — Orchestrator with app_path='' (combined backend project)
_worker_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_worker_env = os.path.join(_worker_dir, ".env")
_root_env   = os.path.join(os.path.dirname(_worker_dir), ".env")
load_dotenv(dotenv_path=_worker_env if os.path.exists(_worker_env) else _root_env, override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# Cloud deployments inject credentials as JSON string via GOOGLE_SERVICE_ACCOUNT_JSON.
# Local dev uses a file path (GOOGLE_SERVICE_ACCOUNT_PATH).
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

GOOGLE_SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "").strip()
# Always resolve the path so it can be used as fallback when JSON env var is truncated
if not GOOGLE_SERVICE_ACCOUNT_PATH or not os.path.isabs(GOOGLE_SERVICE_ACCOUNT_PATH):
    # If path is relative or missing, resolve relative to the worker root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fallback_path = os.path.join(base_dir, "google-service-account.json")

    if GOOGLE_SERVICE_ACCOUNT_PATH:
        GOOGLE_SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(base_dir, GOOGLE_SERVICE_ACCOUNT_PATH))
    else:
        GOOGLE_SERVICE_ACCOUNT_PATH = fallback_path

GOOGLE_SERVICE_ACCOUNT_PATH = GOOGLE_SERVICE_ACCOUNT_PATH.replace("\\", "/")

ZAPI_INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID", "").strip()
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN", "").strip()
ZAPI_BASE_URL = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/"

CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN", "").strip()

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
DRY_RUN = os.getenv("DRY_RUN", "false").strip().lower() == "true"
# Max new leads per client per cycle before flood protection kicks in.
# Exceeding this advances the cursor silently instead of sending notifications.
# Prevents mass-sends when a cursor gets stuck (e.g. after a DB schema issue).
FLOOD_PROTECTION_THRESHOLD = int(os.getenv("FLOOD_PROTECTION_THRESHOLD", "5"))
NOTIFY_OVERRIDE_PHONE = os.getenv("NOTIFY_OVERRIDE_PHONE", "").strip()
NOTIFY_OVERRIDE_LIST = [p.strip() for p in NOTIFY_OVERRIDE_PHONE.split(",") if p.strip()] if NOTIFY_OVERRIDE_PHONE else []

SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
    "Accept-Profile": "seed_sync",
    "Content-Profile": "seed_sync"
}

# ── Startup Validation ──────────────────────────────────────────────────────
def validate_config():
    missing = []
    if not SUPABASE_URL: missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY: missing.append("SUPABASE_SERVICE_ROLE_KEY")
    
    if missing:
        print(f"❌ CRITICAL ERROR: Missing environment variables: {', '.join(missing)}")
        print("Please check your .env file or environment configuration.")
        
    if not GOOGLE_SERVICE_ACCOUNT_JSON and not os.path.exists(GOOGLE_SERVICE_ACCOUNT_PATH):
        print(f"⚠️ WARNING: Google Service Account file not found at: {GOOGLE_SERVICE_ACCOUNT_PATH}")
        print("Set GOOGLE_SERVICE_ACCOUNT_JSON (cloud) or fix GOOGLE_SERVICE_ACCOUNT_PATH (local).")

validate_config()
