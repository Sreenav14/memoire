from __future__ import annotations
import os
import time
import json
import logging
import socket
import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func, delete

from .db import SessionLocal
from .models import IngestionJob, Document, Chunk
from .extractors import extract_text_from_url, extract_text_from_pdf
from .chunking import chunk_text_smart_with_offsets

# todo: replace this with bedrock embeddings later
from .embeddings import embed_text

log = logging.getLogger("memoire.worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

POLL_SECONDS = int(os.getenv("WORKER_POLL_SECONDS", "2"))
MAX_ATTEMPTS = int(os.getenv("WORKER_MAX_ATTEMPTS", "5"))
LOCK_STALE_MINUTES = int(os.getenv("WORKER_LOCK_STALE_MINUTES", "15"))

WORKER_ID = os.getenv("WORKER_ID") or f"{socket.gethostname()}-{os.getpid()}"

def claim_next_job(db: Session) -> Optional[IngestionJob]:
    """ 
    Atomically claims one job for processing. Also rescues stale locks
    Uses  row-level locking to prevent duplicates
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    stale_cutoff = now - datetime.timedelta(minutes=LOCK_STALE_MINUTES)   
    
    job = (
        db.execute(
            select(IngestionJob)
            .where(
                IngestionJob.attempts < MAX_ATTEMPTS,
                or_(
                    and_(
                        IngestionJob.status == "queued",
                        IngestionJob.run_after <= func.now(),
                    ),
                    and_(
                        IngestionJob.status == "processing",
                        IngestionJob.locked_at.is_not(None),
                        IngestionJob.locked_at < stale_cutoff,
                    ),
                ),
            )
        .order_by(IngestionJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
        ).scalars().first()
    )
    if not job:
        return None
    
    job.status = "processing"
    job.locked_at = datetime.datetime.utcnow()
    job.locked_by = WORKER_ID
    job.attempts = (job.attempts or 0) + 1
    job.error = None
    
    db.commit()
    db.refresh(job)
    log.info("claimed job %s  type=%s  attempt=%d", job.id, job.job_type, job.attempts)
    return job

def mark_job_done(db: Session, job: IngestionJob):
    job.status = "done"
    job.locked_at = None
    job.locked_by = None
    job.error = None
    db.commit()
    log.info("job %s  DONE", job.id)


def mark_job_failed(db: Session, job: IngestionJob, err: str, retry_after_seconds: int = 60) -> None:
    job.error = err[:2000]
    # retry with backoff until max_attempts
    if job.attempts < MAX_ATTEMPTS:
        job.status = "queued"
        job.run_after = datetime.datetime.utcnow() + datetime.timedelta(seconds = retry_after_seconds)
        job.locked_at = None
        job.locked_by = None
    else:
        job.status = "failed"
        job.locked_at = None
        job.locked_by = None
    db.commit()
    if job.status == "queued":
        log.warning("job %s  RETRY  attempt=%d  retry_in=%ds  err=%s", job.id, job.attempts, retry_after_seconds, err[:120])
    else:
        log.error("job %s  FAILED permanently  err=%s", job.id, err[:200])

def process_document_ingest(db: Session, job: IngestionJob) -> None:
    if not job.document_id:
        raise RuntimeError("Job has no document_id")
    
    doc =  db.execute(
        select(Document).where(Document.id == job.document_id)
    ).scalar_one_or_none()
    
    if not doc:
        raise RuntimeError(f"document not found: {job.document_id}")
    
    # mark document as processing
    doc.status = "processing"
    db.commit()
    
    payload = {}
    try:
        payload = job.payload or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
    except Exception:
        payload = {}
        
    # determine source type and extract text
    full_text = ""
    
    if doc.source_type == "link" and doc.source_url:
        full_text = extract_text_from_url(doc.source_url)
    else:
        # mvp local path
        local_path = payload.get("local_path") or payload.get("file_path")
        if not local_path:
            raise RuntimeError("local_path is required for local files")
        full_text = extract_text_from_pdf(local_path)
        
    # chunk with offsets
    chunks = chunk_text_smart_with_offsets(full_text, chunk_size=800, overlap=120)
    if not chunks:
        raise RuntimeError("No chunks extracted")
    
    # clear old chunks
    db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    db.commit()
    
    # embed + insert
    for ch in chunks:
        vec = embed_text(ch.text)
        db.add(
            Chunk(
                document_id=doc.id,
                space_id = doc.space_id,
                chunk_index = ch.chunk_index,
                text = ch.text,
                embeddings = vec,
                char_start = ch.char_start,
                char_end = ch.char_end,
            )
        )
    db.commit()
    
    doc.status = "ready"
    db.commit()
    
def run_once() -> bool:
    """
    Run one claim/process cycle. Return True if a job was processed.
    """
    db = SessionLocal()
    try:
        job = claim_next_job(db)
        if not job:
            return False

        try:
            if job.job_type == "document_ingest":
                process_document_ingest(db, job)
            else:
                raise RuntimeError(f"unknown job type: {job.job_type}")

            mark_job_done(db, job)
            return True
        except Exception as e:
            log.exception("error processing job %s", job.id)
            # mark the document as failed if applicable
            if job.document_id:
                doc = db.execute(
                    select(Document).where(Document.id == job.document_id)
                ).scalar_one_or_none()
                if doc:
                    doc.status = "failed"
                    db.commit()

            backoff = min(900, 30 * (job.attempts or 1))
            mark_job_failed(db, job, str(e), retry_after_seconds=backoff)
            return False
    finally:
        db.close()


def main():
    log.info("worker started  id=%s  poll=%ds", WORKER_ID, POLL_SECONDS)
    while True:
        did = run_once()
        if not did:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
    
    