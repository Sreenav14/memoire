-- Memoire: Declarative inference rules

BEGIN;

CREATE TABLE IF NOT EXISTS inference_rules (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id   UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    rule_json  JSONB NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(space_id, name)
);

CREATE INDEX IF NOT EXISTS idx_inference_rules_space_enabled
    ON inference_rules(space_id, is_enabled);

COMMIT;
