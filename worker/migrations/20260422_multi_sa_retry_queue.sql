-- ============================================================
-- Migration: Multi-SA credential routing + WhatsApp retry queue
-- 2026-04-22
-- ============================================================

-- ── FEATURE 1: Google Service Account registry ──────────────────────────────
-- Lives in public (not seed_sync) — cross-cutting infra, not per-client data.

CREATE TABLE IF NOT EXISTS public.google_service_accounts (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT        NOT NULL,           -- Human label, e.g. "Setor Agro - Rafael"
    email      TEXT        NOT NULL,           -- SA client_email for display/audit
    sa_file    TEXT        NOT NULL UNIQUE,    -- Absolute path on VPS, e.g. /opt/apps/seedsync/worker/credentials/agro.json
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- NULL = fall back to global default SA; ON DELETE SET NULL so removing a SA
-- record doesn't orphan configs — they gracefully revert to the default.
ALTER TABLE seed_sync.source_configs
    ADD COLUMN IF NOT EXISTS google_sa_id UUID
        REFERENCES public.google_service_accounts(id)
        ON DELETE SET NULL;

-- ── FEATURE 2: WhatsApp notification retry queue ─────────────────────────────

CREATE TABLE IF NOT EXISTS public.notification_queue (
    id                BIGSERIAL    PRIMARY KEY,
    client_id         TEXT         NOT NULL,
    destination_phone TEXT         NOT NULL,
    message           TEXT         NOT NULL,
    lead_fingerprint  TEXT         NOT NULL,   -- links back to ingestion_log.row_fingerprint
    retry_count       INT          NOT NULL DEFAULT 0,
    next_retry_at     TIMESTAMPTZ  NOT NULL,
    status            TEXT         NOT NULL DEFAULT 'pending',  -- pending | sent | dead
    last_error        TEXT,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Worker polls this on every cycle — must be a fast index scan.
CREATE INDEX IF NOT EXISTS idx_notification_queue_poll
    ON public.notification_queue (status, next_retry_at);

CREATE INDEX IF NOT EXISTS idx_notification_queue_fingerprint
    ON public.notification_queue (lead_fingerprint);
