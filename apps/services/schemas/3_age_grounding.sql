BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;

LOAD 'age';
SET search_path = ag_catalog, "$user", public;

SELECT create_graph('memory_graph')
WHERE NOT EXISTS (
  SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'memory_graph'
);

ALTER TABLE chunks
  ADD COLUMN IF NOT EXISTS char_start int NULL,
  ADD COLUMN IF NOT EXISTS char_end   int NULL;

-- Map our stable entity keys to AGE vertex ids
CREATE TABLE IF NOT EXISTS graph_vertex_map (
  space_id   UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  entity_key text NOT NULL,
  ag_id      bigint NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (space_id, entity_key)
);

-- Map our stable edge keys
CREATE TABLE IF NOT EXISTS graph_edge_map (
  space_id   UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  edge_key   text NOT NULL,
  ag_id      bigint NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (space_id, edge_key)
);

-- Evidence for grounding
CREATE TABLE IF NOT EXISTS graph_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  space_id UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,

  entity_key text NULL,
  edge_key   text NULL,

  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_id    UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,

  quote text NULL,
  char_start int NOT NULL,
  char_end   int NOT NULL,
  confidence real NOT NULL DEFAULT 0.7,

  created_at timestamptz NOT NULL DEFAULT now(),

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