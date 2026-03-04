-- Memoire: User profiles per space (static + dynamic + individual facts)

BEGIN;

CREATE TABLE IF NOT EXISTS profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id        UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    static_profile  JSONB NOT NULL DEFAULT '{}'::jsonb,
    dynamic_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(space_id, user_id)
);

CREATE TABLE IF NOT EXISTS profile_facts (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id   UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fact_key   TEXT NOT NULL,
    value      TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.8,
    state      TEXT NOT NULL DEFAULT 'active'
                    CHECK (state IN ('active','deprecated')),
    source     TEXT NOT NULL DEFAULT 'manual',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_profiles_space_user
    ON profiles(space_id, user_id);

CREATE INDEX IF NOT EXISTS idx_profile_facts_space_user
    ON profile_facts(space_id, user_id);

CREATE INDEX IF NOT EXISTS idx_profile_facts_space_user_key
    ON profile_facts(space_id, user_id, fact_key);

COMMIT;
