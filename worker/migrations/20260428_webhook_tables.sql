-- Migration: Webhook lead ingestion tables + source_configs evolution
-- Run in Supabase SQL editor (seed_sync schema)
-- Tables must be created in this order due to FK dependencies.

-- 1. contas (client accounts — no deps)
CREATE TABLE IF NOT EXISTS seed_sync.contas (
  id   bigint NOT NULL,
  conta character varying NOT NULL,
  mql  boolean,
  CONSTRAINT contas_pkey PRIMARY KEY (id),
  CONSTRAINT contas_id_key UNIQUE (id)
);

-- 2. forms (Facebook lead forms — no deps)
CREATE TABLE IF NOT EXISTS seed_sync.forms (
  id         bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  nome       text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  page       text,
  CONSTRAINT forms_pkey PRIMARY KEY (id)
);

-- 3. pages (Facebook pages — no deps)
CREATE TABLE IF NOT EXISTS seed_sync.pages (
  id           text NOT NULL,
  name         text,
  acess_token  text,
  created_at   timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT pages_pkey PRIMARY KEY (id)
);

-- 4. access_token (Facebook access tokens — no deps)
CREATE TABLE IF NOT EXISTS seed_sync.access_token (
  token      text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT access_token_pkey PRIMARY KEY (token)
);

-- 5. campaigns (FK → contas)
CREATE TABLE IF NOT EXISTS seed_sync.campaigns (
  campaign_id text   NOT NULL,
  conta_id    bigint NOT NULL,
  nome        text   NOT NULL,
  CONSTRAINT campaigns_pkey PRIMARY KEY (campaign_id),
  CONSTRAINT campaigns_conta_id_fkey FOREIGN KEY (conta_id) REFERENCES seed_sync.contas(id)
);

-- 6. form_fields (FK → forms; unique on form_id+field_raw for upsert support)
CREATE TABLE IF NOT EXISTS seed_sync.form_fields (
  id         integer NOT NULL DEFAULT nextval('seed_sync.form_fields_id_seq'::regclass),
  form_id    bigint  NOT NULL,
  field_raw  character varying NOT NULL,
  field_type character varying NOT NULL,
  created_at timestamp without time zone NOT NULL DEFAULT now(),
  CONSTRAINT form_fields_pkey PRIMARY KEY (id),
  CONSTRAINT form_fields_form_id_field_raw_key UNIQUE (form_id, field_raw),
  CONSTRAINT form_fields_form_id_fkey FOREIGN KEY (form_id) REFERENCES seed_sync.forms(id)
);

-- sequence needed by form_fields
CREATE SEQUENCE IF NOT EXISTS seed_sync.form_fields_id_seq
  AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE seed_sync.form_fields_id_seq OWNED BY seed_sync.form_fields.id;

-- 7. leads (FK → forms, contas, campaigns)
CREATE SEQUENCE IF NOT EXISTS seed_sync.leads_id_seq
  AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE TABLE IF NOT EXISTS seed_sync.leads (
  id          integer   NOT NULL DEFAULT nextval('seed_sync.leads_id_seq'::regclass),
  form_id     bigint,
  conta       bigint,
  campaign_id text      NOT NULL,
  adset_id    text,
  ad_id       text,
  created_at  timestamp without time zone NOT NULL,
  raw_payload json,
  mql         boolean   NOT NULL DEFAULT false,
  CONSTRAINT leads_pkey PRIMARY KEY (id),
  CONSTRAINT leads_form_id_fkey    FOREIGN KEY (form_id)     REFERENCES seed_sync.forms(id),
  CONSTRAINT leads_conta_fkey      FOREIGN KEY (conta)       REFERENCES seed_sync.contas(id),
  CONSTRAINT leads_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES seed_sync.campaigns(campaign_id)
);
ALTER SEQUENCE seed_sync.leads_id_seq OWNED BY seed_sync.leads.id;

-- 8. lead_answers (FK → leads, form_fields)
CREATE SEQUENCE IF NOT EXISTS seed_sync.lead_answers_id_seq
  AS bigint START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE TABLE IF NOT EXISTS seed_sync.lead_answers (
  id         bigint  NOT NULL DEFAULT nextval('seed_sync.lead_answers_id_seq'::regclass),
  lead_id    bigint  NOT NULL,
  field_id   integer NOT NULL,
  value      text    NOT NULL,
  created_at timestamp without time zone NOT NULL DEFAULT now(),
  CONSTRAINT lead_answers_pkey PRIMARY KEY (id),
  CONSTRAINT lead_answers_lead_id_fkey  FOREIGN KEY (lead_id)  REFERENCES seed_sync.leads(id),
  CONSTRAINT lead_answers_field_id_fkey FOREIGN KEY (field_id) REFERENCES seed_sync.form_fields(id)
);
ALTER SEQUENCE seed_sync.lead_answers_id_seq OWNED BY seed_sync.lead_answers.id;

-- ── Evolve source_configs ──────────────────────────────────────────────────
-- ingestion_mode: 'sheet' (default, existing behaviour) | 'webhook' (new)
-- conta_id: links webhook pipelines to seed_sync.contas
ALTER TABLE seed_sync.source_configs
  ADD COLUMN IF NOT EXISTS ingestion_mode text NOT NULL DEFAULT 'sheet'
    CHECK (ingestion_mode IN ('sheet', 'webhook')),
  ADD COLUMN IF NOT EXISTS conta_id bigint
    REFERENCES seed_sync.contas(id) ON DELETE SET NULL;

-- Ensures one active webhook pipeline per conta
CREATE UNIQUE INDEX IF NOT EXISTS source_configs_conta_id_uniq
  ON seed_sync.source_configs(conta_id)
  WHERE conta_id IS NOT NULL;
