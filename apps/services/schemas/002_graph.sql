-- Memoire: Knowledge graph (Apache AGE) + evidence grounding

BEGIN;

CREATE EXTENSION IF NOT EXISTS age;

LOAD 'age';
SET search_path = ag_catalog, "$user", public;

SELECT create_graph('memory_graph')
WHERE NOT EXISTS (
    SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'memory_graph'
);

-- ── Stable key -> AGE id mappings ──

CREATE TABLE IF NOT EXISTS graph_vertex_map (
    space_id   UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    entity_key TEXT NOT NULL,
    ag_id      BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (space_id, entity_key)
);

CREATE TABLE IF NOT EXISTS graph_edge_map (
    space_id   UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    edge_key   TEXT NOT NULL,
    ag_id      BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (space_id, edge_key)
);

-- ── Evidence grounding (every fact traced to a source quote) ──

CREATE TABLE IF NOT EXISTS graph_evidence (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id    UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    entity_key  TEXT NULL,
    edge_key    TEXT NULL,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id    UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    quote       TEXT NULL,
    char_start  INT NOT NULL,
    char_end    INT NOT NULL,
    confidence  REAL NOT NULL DEFAULT 0.7,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT graph_evidence_target_chk CHECK (
        ((entity_key IS NOT NULL)::int + (edge_key IS NOT NULL)::int) = 1
    )
);

CREATE INDEX IF NOT EXISTS idx_graph_evidence_space_entity
    ON graph_evidence(space_id, entity_key);

CREATE INDEX IF NOT EXISTS idx_graph_evidence_space_edge
    ON graph_evidence(space_id, edge_key);

CREATE INDEX IF NOT EXISTS idx_graph_evidence_space_doc
    ON graph_evidence(space_id, document_id);

COMMIT;
