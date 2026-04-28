import os
from dotenv import load_dotenv

# Env resolution order (first found wins):
#   1. api/.env        — Orchestrator with app_path=api/
#   2. root .env       — Orchestrator with app_path='' (combined backend project)
#   3. worker/.env     — local dev legacy
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_root_dir = os.path.dirname(_api_dir)
_api_env    = os.path.join(_api_dir,  ".env")
_root_env   = os.path.join(_root_dir, ".env")
_worker_env = os.path.join(_root_dir, "worker", ".env")
_env_path = _api_env if os.path.exists(_api_env) else _root_env if os.path.exists(_root_env) else _worker_env
load_dotenv(dotenv_path=_env_path, override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
JWT_PUBLIC_KEY = os.getenv("VITE_JWT_PUBLIC_KEY", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

# Common headers for internal service role calls
SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
    "Accept-Profile": "seed_sync",
    "Content-Profile": "seed_sync"
}
