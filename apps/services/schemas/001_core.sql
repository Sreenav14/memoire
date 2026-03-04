-- Memoire: Core tables
-- Users, auth, spaces, documents, chunks, memory items, ingestion jobs, API tokens

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Users & Auth ──

CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name     TEXT NOT NULL,
    last_name      TEXT NOT NULL,
    email          TEXT NOT NULL UNIQUE,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_passwords (
    user_id        UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    password_hash  TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_oauth_identities (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider         TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    provider_email   TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_user_id)
);

CREATE INDEX IF NOT EXISTS idx_oauth_provider_email
    ON user_oauth_identities(provider_email);

-- ── Spaces (multi-tenant boundaries) ──

CREATE TABLE IF NOT EXISTS spaces (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_spaces (
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    space_id   UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    role       TEXT NOT NULL DEFAULT 'owner',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, space_id)
);

CREATE INDEX IF NOT EXISTS idx_user_spaces_space_id ON user_spaces(space_id);

-- ── Documents & Chunks ──

CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id    UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL DEFAULT 'upload',
    title       TEXT,
    source_url  TEXT,
    status      TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','processing','ready','failed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_space_id ON documents(space_id);

CREATE TABLE IF NOT EXISTS chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    space_id    UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    text        TEXT NOT NULL,
    embeddings  VECTOR(1536),
    char_start  INT,
    char_end    INT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_space_id ON chunks(space_id);

-- ── Memory Items (notes + decisions) ──

CREATE TABLE IF NOT EXISTS memory_items (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id   UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       TEXT NOT NULL CHECK (type IN ('note', 'decision')),
    title      TEXT,
    content    TEXT NOT NULL,
    embeddings VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_items_space_id ON memory_items(space_id);

-- ── Decision Graph (supersedes edges) ──

CREATE TABLE IF NOT EXISTS decision_supersedes (
    newer_decision_id UUID NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    older_decision_id UUID NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (newer_decision_id, older_decision_id)
);

-- ── Ingestion Jobs (all job types defined upfront) ──

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type    TEXT NOT NULL
                     CHECK (job_type IN (
                         'document_ingest',
                         'profile_update',
                         'memory_consolidation',
                         'memory_inference'
                     )),
    space_id    UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    document_id UUID NULL REFERENCES documents(id) ON DELETE CASCADE,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    status      TEXT NOT NULL DEFAULT 'queued'
                     CHECK (status IN ('queued','processing','done','failed')),
    attempts    INT NOT NULL DEFAULT 0,
    error       TEXT NULL,
    run_after   TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_at   TIMESTAMPTZ NULL,
    locked_by   TEXT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_run_after
    ON ingestion_jobs(status, run_after);

-- ── API Tokens (MCP / external integrations) ──

CREATE TABLE IF NOT EXISTS api_tokens (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    space_id     UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    token_hash   TEXT NOT NULL,
    name         TEXT,
    last_used_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id  ON api_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_space_id ON api_tokens(space_id);

COMMIT;
