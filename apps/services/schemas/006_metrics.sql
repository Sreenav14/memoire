-- Memoire: Operational metrics counters

BEGIN;

CREATE TABLE IF NOT EXISTS metrics_counters (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id   UUID NULL,
    name       TEXT NOT NULL,
    value      BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Two partial unique indexes to handle NULL space_id correctly in upserts
CREATE UNIQUE INDEX IF NOT EXISTS idx_metrics_space_name
    ON metrics_counters(space_id, name)
    WHERE space_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_metrics_global_name
    ON metrics_counters(name)
    WHERE space_id IS NULL;

COMMIT;
