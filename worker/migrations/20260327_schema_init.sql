-- 1. Create schema
CREATE SCHEMA IF NOT EXISTS seed_sync;

-- 2. Configuration for each client/source
CREATE TABLE IF NOT EXISTS seed_sync.source_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT UNIQUE NOT NULL, -- Short name e.g. 'GEOTECH'
    name TEXT NOT NULL,             -- Friendly name
    sheet_id TEXT NOT NULL,         -- Google Spreadsheet ID
    worksheet_name TEXT NOT NULL DEFAULT 'Página1',
    target_table TEXT NOT NULL,     -- Destination table in seed_sync schema
    last_row_index INT NOT NULL DEFAULT 0, -- Current sync cursor
    
    -- Ingestion logic settings
    active BOOLEAN DEFAULT true,
    phone_column TEXT DEFAULT 'WHATSAPP',
    name_column TEXT DEFAULT 'NOME',
    required_columns TEXT[] DEFAULT ARRAY['NOME', 'WHATSAPP'], -- Minimal fields to consider a valid lead
    dedup_columns TEXT[] DEFAULT ARRAY['NOME', 'WHATSAPP'],     -- Columns to hash for fingerprinting
    
    -- Notification settings
    legacy_phone TEXT,              -- In case destination_phones is empty
    destination_phones TEXT[],      -- List of phones to receive notifications
    clickup_enabled BOOLEAN DEFAULT true,
    clickup_list_id TEXT,
    clickup_assignees INT[],
    clickup_priority INT DEFAULT 1,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- 3. Audit trail and idempotency log
CREATE TABLE IF NOT EXISTS seed_sync.ingestion_log (
    id BIGSERIAL PRIMARY KEY,
    client_id TEXT NOT NULL,
    row_fingerprint TEXT NOT NULL,  -- SHA256 of the lead data
    status TEXT NOT NULL,           -- 'inserted', 'duplicate', 'error'
    whatsapp_status TEXT,           -- 'sent', 'failed', 'skipped'
    raw_payload JSONB,              -- Content of the row at that time
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_log_fingerprint ON seed_sync.ingestion_log(row_fingerprint);
CREATE INDEX IF NOT EXISTS idx_log_client ON seed_sync.ingestion_log(client_id);
CREATE INDEX IF NOT EXISTS idx_configs_active ON seed_sync.source_configs(active);

-- Enable RLS
ALTER TABLE seed_sync.source_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE seed_sync.ingestion_log ENABLE ROW LEVEL SECURITY;

-- Note: In Phase 0-3, we rely on service role access from the worker.
-- Public/Authenticated policies will be added when building the React Admin UI.
