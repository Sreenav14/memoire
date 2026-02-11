-- memoire core schema (local dev)

-- for pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- UUID Generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

BEGIN;

-- Users
CREATE TABLE IF NOT EXISTS users (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name TEXT NOT NULL,
    last_name  TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

--  Email/password credentials (only for user who signs up with password)
CREATE TABLE IF NOT EXISTS user_passwords (
    user_id        UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    password_hash  TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- OAUTH Identification (one user can have multiple oauth providers)
CREATE TABLE IF NOT EXISTS user_oauth_identities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider    TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    provider_email TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE   (provider, provider_user_id)
);

-- Index for lookup by provider email if needed
CREATE INDEX IF NOT EXISTS idx_oauth_provider_email 
    ON user_oauth_identities(provider_email);

-- SPACES membership (multi-tenant boundaries)
CREATE TABLE IF NOT EXISTS spaces (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Space membership (teams later)
CREATE TABLE IF NOT EXISTS user_spaces (
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    space_id    UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    role        TEXT NOT NULL DEFAULT 'owner', -- owner, admin, viewer
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, space_id)
);

CREATE INDEX IF NOT EXISTS idx_user_spaces_space_id ON user_spaces(space_id);

-- MEMORY ITEMS (notes + decisions)
CREATE TABLE IF NOT EXISTS memory_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id    UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
    type        TEXT NOT NULL CHECK (type IN ('note', 'decision')),
    title       TEXT,
    content     TEXT NOT NULL,
    embeddings  VECTOR(1536),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_items_space_id ON memory_items(space_id);

-- will add vector index later

-- Decision Graph (edges)
CREATE TABLE IF NOT EXISTS decision_supersedes (
    newer_decision_id UUID NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    older_decision_id UUID NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (newer_decision_id, older_decision_id)
);
-- DOCUMENTS + CHUNKS (ingestion layer)

CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id    UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
    source_type TEXT NOT NULL DEFAULT 'upload', -- upload/link/connector
    title       TEXT,
    source_url  TEXT, -- s3
    status      TEXT NOT NULL DEFAULT 'pending', -- pending/processing/ready/failed
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
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index),
    char_start INT,
    char_end   INT
);

CREATE INDEX IF NOT EXISTS idx_chunks_space_id ON chunks(space_id);

-- MCP/API TOKENS
CREATE TABLE IF NOT EXISTS api_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    space_id    UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,
    name        TEXT ,
    last_used_at TIMESTAMP,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id ON api_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_space_id ON api_tokens(space_id);

COMMIT;


