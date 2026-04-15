# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is SeedSync

SeedSync is a **lead ingestion and WhatsApp notification system** for Brazilian real estate clients. It monitors Google Sheets for new leads, stores them in Supabase, and sends WhatsApp notifications via Z-API in real time.

Three processes run independently:
- **worker/** — Python background scheduler that polls sheets and ingests leads
- **api/** — FastAPI backend that exposes CRUD for configs and logs
- **admin/** — React/Vite dashboard for monitoring and config management

## Commands

### Worker (background lead processor)
```bash
cd worker
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m app.main
```

### API (FastAPI)
```bash
cd api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Admin dashboard (React)
```bash
cd admin
npm install
npm run dev       # dev server on :5173
npm run build     # production build
npm run lint      # ESLint
```

### Running test scripts
```bash
cd worker
python scripts/send_one_test.py   # send a manual WhatsApp test message
python check_db.py                # verify Supabase connectivity
```

### Resetting sync cursors
```bash
cd worker
python scripts/reset_cursors.py   # reset last_row_index for all clients
```

## Environment Setup

**worker/.env** (required):
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
GOOGLE_SERVICE_ACCOUNT_PATH=./google-service-account.json
ZAPI_INSTANCE_ID=
ZAPI_TOKEN=
ZAPI_CLIENT_TOKEN=
CLICKUP_API_TOKEN=          # optional
POLL_INTERVAL_SECONDS=120
DRY_RUN=false
NOTIFY_OVERRIDE_PHONE=      # comma-separated phones for pilot testing
```

**api/.env** — same `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.

**admin/.env.local**:
```
VITE_API_URL=http://localhost:8000
```

`worker/google-service-account.json` is required for Google Sheets access and is gitignored.

## Architecture: How the Parts Connect

### Worker pipeline (the core logic)

`worker/app/main.py` runs an APScheduler job every `POLL_INTERVAL_SECONDS`. Each cycle picks a **rotating batch of 5 clients** from `source_configs` (offset advances each cycle so all clients get processed fairly). For each client, `ingester.py` orchestrates:

1. **Fetch** — `integrations/sheets.py` reads new rows starting from `last_row_index`, using exponential backoff `[5s, 10s, 20s]` on HTTP 429 quota errors. A semaphore limits concurrent sheet reads to 2.
2. **Schema evolution** — `schema_manager.py` calls Supabase RPC functions (`check_table_seed_sync`, `create_table_with_defaults`, `add_missing_columns`) to auto-create/extend the client's target table.
3. **Deduplication** — SHA256 fingerprint of `name|phone` is bulk-checked against `ingestion_log`. If the check itself fails (network error), the batch **aborts entirely** — the cursor does NOT advance. This is the primary fail-safe.
4. **Insert** — New leads are batch-inserted into the client's Supabase table. Column names pass through `validator.py`'s `sanitize_identifier()` to prevent SQL injection.
5. **Notify** — Concurrent WhatsApp sends to all `destination_phones` via Z-API. `phone/normalizer.py` validates and normalizes Brazilian phone numbers (DDD validation, 8→9 digit detection, landline detection).
6. **ClickUp** — If a WhatsApp send fails, `integrations/clickup.py` creates a task in the configured list.
7. **Cursor advance** — `last_row_index` is updated in Supabase **only if all DB insertions succeeded**. Notification failure does NOT block cursor advancement.

### Supabase schema

All client lead tables live in the `seed_sync` schema. The `ingestion_log` table is in the `public` schema. The API and worker both write directly via Supabase's PostgREST REST API (no ORM); requests use `SUPABASE_SERVICE_ROLE_KEY` with `Prefer: return=representation` headers for insert-and-return patterns.

### API ↔ Admin

The admin frontend (`admin/src/lib/api.ts`) calls the FastAPI backend for all data. The API has no authentication currently — it is assumed to run on an internal network. The API also proxies Google Sheets exploration (listing worksheets and columns) so the admin can help users configure new clients without direct Sheets access.

## Key Design Decisions

**Cursor only advances on full DB success, not on notification success.** This means a lead is never double-ingested even if WhatsApp fails. ClickUp tasks are created for notification failures so they can be retried manually.

**Schema is auto-evolved at runtime.** When a Google Sheet gains new columns, the worker detects them and adds matching columns to the Supabase table automatically via RPC. No migrations needed.

**Phone normalization is Brazil-specific.** `phone/normalizer.py` encodes Brazilian DDD rules and the 9-digit mobile number requirement. Extending to other countries requires modifying this module.

**The `DRY_RUN` env var** makes the worker log everything but skip actual DB writes and WhatsApp sends — useful for testing new client configs before going live.

**PGRST204 auto-recovery** — when PostgREST's schema cache is stale (column exists in DB but not in cache), `ingester.py:_insert_with_schema_recovery` detects the error, force-adds the column via `add_missing_columns` RPC, reloads the cache via `reload_pgrst_schema` RPC, and retries. Handles up to 10 missing columns per batch.

## Production Deployment

### Infrastructure
- **VPS**: `root@72.60.247.133` — Ubuntu, PM2 managed
- **App root**: `/opt/apps/seedsync/`
- **PM2 process**: `seedsync-backend` (runs `run.py` which spawns worker + api)
- **Admin frontend**: separate PM2 process via Orchestrator
- **Domain**: `seedsync.3fventure.tech`

### Orchestrator (3F Deploy)
Custom PM2 + Nginx + Certbot deployer. Contract files live in `ops/`:
- `ops/backend.yml` — `start_cmd: "./venv/bin/python run.py"`, deploys worker+api as one process
- `ops/admin.yml` — Vite preview server; all commands prefixed with `cd admin &&`

**Known Orchestrator bug**: injects spaces or newlines into long env var values (JWTs, JSON blobs) every redeploy. `run.py:_repair_env()` auto-repairs the `.env` file on every startup before spawning subprocesses.

### Google Service Account credentials
The Orchestrator truncates `GOOGLE_SERVICE_ACCOUNT_JSON` to ~133 chars (unusable). Solution already deployed:
- Full credentials file lives at `/opt/apps/seedsync/worker/google-service-account.json` (placed manually via `scp`, gitignored, survives redeploys)
- `sheets.py` catches `JSONDecodeError` on the truncated env var and falls back to the file automatically

### Required Supabase SQL functions
These must exist in the Supabase project (run once in the SQL editor):

```sql
-- Lets the worker reload PostgREST's schema cache after adding columns
CREATE OR REPLACE FUNCTION seed_sync.reload_pgrst_schema()
RETURNS void LANGUAGE sql SECURITY DEFINER AS $$
  SELECT pg_notify('pgrst', 'reload schema');
$$;
```

All other schema RPCs (`check_table_seed_sync`, `create_table_with_defaults`, `get_table_columns`, `add_missing_columns`) should already exist.

### Useful VPS commands
```bash
pm2 logs seedsync-backend --lines 40 --nostream   # view recent logs
pm2 restart seedsync-backend                        # manual restart
cat /opt/apps/seedsync/.env | grep SUPABASE        # verify env after deploy
```

### Active clients (source_configs table)
| client_id | sheet | target_table |
|---|---|---|
| AGROLIVEIRA | Crédito Rural - 2026 | AGROLIVEIRA |
| BVK | FORMS Licitações | BVK |
| BVK_PREV | FORMS Prev | BVK_PREV |
| RURALTECH | PRODUTORES - 2026 | RURALTECH |

### Pilot testing
Set `NOTIFY_OVERRIDE_PHONE=<your_number>` in Orchestrator secrets to redirect all WhatsApp notifications to a single number. Remove to go live.
