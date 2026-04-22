-- ============================================================
-- Migration: Z-API messageId tracking for delivery webhooks
-- 2026-04-25
-- ============================================================

-- Track Z-API messageId so delivery webhooks can find the right queue row
ALTER TABLE public.notification_queue
    ADD COLUMN IF NOT EXISTS zapi_message_id TEXT;

-- Track messageId for first-attempt sends (stored in ingestion_log)
ALTER TABLE seed_sync.ingestion_log
    ADD COLUMN IF NOT EXISTS zapi_message_id TEXT;

-- Fast lookup when webhook arrives with a messageId
CREATE INDEX IF NOT EXISTS idx_nq_zapi_msgid
    ON public.notification_queue (zapi_message_id)
    WHERE zapi_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_il_zapi_msgid
    ON seed_sync.ingestion_log (zapi_message_id)
    WHERE zapi_message_id IS NOT NULL;
