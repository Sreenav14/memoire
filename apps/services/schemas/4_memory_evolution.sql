BEGIN;

-- Allow a new ingestion job type for consolidation
ALTER TABLE ingestion_jobs
    DROP CONSTRAINT IF EXISTS ingestion_jobs_job_type_check;

ALTER TABLE ingestion_jobs  
    ADD CONSTRAINT ingestion_jobs_job_type_check
    CHECK (job_type IN ('document_ingest', 'profile_update', 'memory_consolidation'));

-- EVENT log for auditable 'living memory' changes
CREATE TABLE IF NOT EXISTS memory_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,

    event_type TEXT NOT NULL 
        CHECK (event_type IN ('update', 'delete','contradict','deprecate','merge','split')),
    
    target_entity_key TEXT NULL,
    target_edge_key TEXT NULL,

    new_entity_key TEXT NULL,
    new_edge_key TEXT NULL,

    reason TEXT NULL,
    created_by_doc_id UUID NULL REFERENCES documents(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT memory_events_target_chk CHECK(
        ((target_entity_key IS NOT NULL)::int + (target_edge_key IS NOT NULL)::int) >= 1
    )
);

CREATE INDEX IF NOT EXISTS  idx_memory_events_space_time
    ON memory_events(space_id, created_at DESC);
    
CREATE INDEX IF NOT EXISTS idx_memory_events_space_edge
    ON memory_events(space_id, target_edge_key);

COMMIT;