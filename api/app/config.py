import os
from dotenv import load_dotenv

# Production: Orchestrator places .env inside api/ (app_path = api/).
# Local dev legacy: .env lives in worker/ — fall back to that if api/.env missing.
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_api_env = os.path.join(_api_dir, ".env")
_worker_env = os.path.join(os.path.dirname(_api_dir), "worker", ".env")
load_dotenv(dotenv_path=_api_env if os.path.exists(_api_env) else _worker_env)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
JWT_PUBLIC_KEY = os.getenv("VITE_JWT_PUBLIC_KEY", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

# Common headers for internal service role calls
SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
    "Accept-Profile": "seed_sync",
    "Content-Profile": "seed_sync"
}
