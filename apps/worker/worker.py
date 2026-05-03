from __future__ import annotations

import os
import time
import json
import logging
import socket
import datetime
import uuid
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func, delete

from .db import SessionLocal
from .models import IngestionJob, Document, Chunk
from .ingestion.extractors import extract_text_from_url, extract_text_from_pdf
from .ingestion.chunking import chunk_text_smart_with_offsets
from .ingestion.embeddings import embed_text
from .graph.persist import persist_chunk_graph
from .graph.extract_hybrid import extract_hybrid
from .evolution.consolidate import consolidate_document
from .evolution.infer_engine import run_inference_rules
from .rules.discovery import discover_relations
from .rules.generator import generate_rules
from .rules.storage import store_rules
from .metrics import inc as metrics_inc

GRAPH_ENABLED = os.getenv("GRAPH_ENABLED", "1") == "1"

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


START_TIME = time.time()

import threading
import http.server
import socketserver
import urllib.parse


class WorkerDetails:
    """Collect runtime details about this worker and queue counts."""

    def __init__(self) -> None:
        self.worker_id = WORKER_ID
        self.poll_seconds = POLL_SECONDS
        self.max_attempts = MAX_ATTEMPTS
        self.lock_stale_minutes = LOCK_STALE_MINUTES
        self.graph_enabled = GRAPH_ENABLED
        self.host = socket.gethostname()
        self.pid = os.getpid()
        self.start_time = START_TIME

    def _counts(self, db: Session) -> dict:
        queued = db.execute(select(func.count()).select_from(IngestionJob).where(IngestionJob.status == "queued")).scalar() or 0
        processing = db.execute(select(func.count()).select_from(IngestionJob).where(IngestionJob.status == "processing")).scalar() or 0
        failed = db.execute(select(func.count()).select_from(IngestionJob).where(IngestionJob.status == "failed")).scalar() or 0
        done = db.execute(select(func.count()).select_from(IngestionJob).where(IngestionJob.status == "done")).scalar() or 0
        return {"queued": int(queued), "processing": int(processing), "failed": int(failed), "done": int(done)}

    def to_dict(self) -> dict:
        db = SessionLocal()
        try:
            counts = self._counts(db)
        finally:
            db.close()

        uptime_seconds = int(time.time() - self.start_time)
        return {
            "worker_id": self.worker_id,
            "host": self.host,
            "pid": self.pid,
            "uptime_seconds": uptime_seconds,
            "poll_seconds": self.poll_seconds,
            "max_attempts": self.max_attempts,
            "lock_stale_minutes": self.lock_stale_minutes,
            "graph_enabled": self.graph_enabled,
            "queue": counts,
        }


class WorkerHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """A tiny HTTP handler exposing /worker/status and /worker/run-once endpoints."""

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/worker/status":
            wd = WorkerDetails()
            self._send_json(wd.to_dict())
            return

        if path == "/worker/run-once":
            # Run one processing cycle synchronously and return result.
            try:
                ran = run_once()
                msg = "processed a job" if ran else "no job processed"
                self._send_json({"ran": bool(ran), "message": msg})
            except Exception as e:
                log.exception("run-once endpoint error")
                self._send_json({"ran": False, "error": str(e)}, status=500)
            return

        # Not found
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        # Route HTTP logs to our logger
        log.info("%s - - %s", self.client_address[0], format % args)


def start_http_api(host: str = "0.0.0.0", port: int = 8000) -> threading.Thread:
    """Start a simple HTTP server in a background thread. Returns the Thread."""
    def _serve() -> None:
        with socketserver.ThreadingTCPServer((host, port), WorkerHTTPRequestHandler) as httpd:
            log.info("worker http api listening on %s:%d", host, port)
            try:
                httpd.serve_forever()
            except Exception:
                log.exception("http server stopped")

    t = threading.Thread(target=_serve, daemon=True, name="worker-http-api")
    t.start()
    return t

def claim_next_job(db: Session) -> Optional[IngestionJob]:
    """Atomically claims one job. Also rescues stale locks via row-level locking."""
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
        )
        .scalars()
        .first()
    )
    if not job:
        return None

    job.status = "processing"
    job.locked_at = datetime.datetime.now(datetime.timezone.utc)
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
    if job.attempts < MAX_ATTEMPTS:
        job.status = "queued"
        job.run_after = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=retry_after_seconds)
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


def enqueue_memory_consolidation(db: Session, *, space_id: str, document_id: str) -> None:
    """Enqueue a consolidation job after ingestion. Idempotent."""
    existing = (
        db.execute(
            select(IngestionJob).where(
                IngestionJob.job_type == "memory_consolidation",
                IngestionJob.document_id == document_id,
                IngestionJob.status.in_(["queued", "processing"]),
            ).limit(1)
        )
        .scalars()
        .first()
    )
    if existing:
        log.info("memory_consolidation already exists doc=%s job=%s", document_id, existing.id)
        return

    payload = {"scope": "document", "document_id": document_id}
    j = IngestionJob(
        id=uuid.uuid4(),
        job_type="memory_consolidation",
        space_id=space_id,
        document_id=document_id,
        payload=json.dumps(payload),
        status="queued",
        attempts=0,
        run_after=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(j)
    db.commit()
    log.info("enqueued memory_consolidation job=%s doc=%s", j.id, document_id)


def process_document_ingest(db: Session, job: IngestionJob) -> None:
    if not job.document_id:
        raise RuntimeError("Job has no document_id")

    doc = db.execute(
        select(Document).where(Document.id == job.document_id)
    ).scalar_one_or_none()

    if not doc:
        raise RuntimeError(f"document not found: {job.document_id}")

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

    full_text = ""
    kind = (payload.get("kind") or "").lower()

    if kind == "url":
        url = payload.get("source_url") or doc.source_url
        if not url:
            raise RuntimeError("source_url is required for url ingestion")
        full_text = extract_text_from_url(url)
    elif kind == "text":
        txt = (payload.get("text") or "").strip()
        if not txt:
            raise RuntimeError("text is required for text ingestion")
        full_text = txt
    else:
        local_path = payload.get("file_path") or payload.get("local_path")
        if not local_path:
            raise RuntimeError("file_path is required for pdf ingestion")
        full_text = extract_text_from_pdf(local_path)

    chunks = chunk_text_smart_with_offsets(full_text, chunk_size=800, overlap=120)
    if not chunks:
        raise RuntimeError("No chunks extracted")

    db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    db.commit()

    for ch in chunks:
        vec = embed_text(ch.text)
        db.add(
            Chunk(
                document_id=doc.id,
                space_id=doc.space_id,
                chunk_index=ch.chunk_index,
                text=ch.text,
                embeddings=vec,
                char_start=ch.char_start,
                char_end=ch.char_end,
            )
        )
    db.commit()

    if GRAPH_ENABLED:
        saved_chunks = db.execute(
            select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index.asc())
        ).scalars().all()

        for sc in saved_chunks:
            try:
                extraction = extract_hybrid(sc.text)
                persist_chunk_graph(
                    db=db,
                    space_id=str(doc.space_id),
                    document_id=str(doc.id),
                    chunk_id=str(sc.id),
                    chunk_text=sc.text,
                    extraction=extraction,
                )
            except Exception as e:
                log.warning("graph build failed for doc=%s chunk=%s err=%s", doc.id, sc.id, str(e)[:200])

        db.commit()

    doc.status = "ready"
    db.commit()

    metrics_inc(db, name="worker.document_ingest.done", space_id=str(doc.space_id))
    db.commit()

    enqueue_memory_consolidation(db, space_id=str(doc.space_id), document_id=str(doc.id))


def run_once() -> bool:
    """Run one claim/process cycle. Return True if a job was processed."""
    db = SessionLocal()
    try:
        job = claim_next_job(db)
        if not job:
            return False

        try:
            if job.job_type == "document_ingest":
                process_document_ingest(db, job)

            elif job.job_type == "memory_consolidation":
                if not job.document_id:
                    raise RuntimeError("memory_consolidation job has no document_id")
                consolidate_document(db, space_id=str(job.space_id), document_id=str(job.document_id))
                metrics_inc(db, name="worker.consolidation.done", space_id=str(job.space_id))
                db.commit()

                db.add(
                    IngestionJob(
                        id=uuid.uuid4(),
                        job_type="memory_inference",
                        space_id=job.space_id,
                        document_id=job.document_id,
                        payload=json.dumps({"reason": "post_consolidation"}),
                        status="queued",
                        attempts=0,
                        run_after=datetime.datetime.now(datetime.timezone.utc),
                    )
                )
                db.commit()

            elif job.job_type == "memory_inference":
                space = str(job.space_id)
                run_inference_rules(db, space_id=space)

                if GRAPH_ENABLED and os.getenv("OPENAI_API_KEY"):
                    try:
                        rels = discover_relations(db, space)
                        if rels:
                            suggested = generate_rules(rels)
                            new_rules = suggested.get("rules") or []
                            if new_rules:
                                store_rules(db, space, new_rules)
                                log.info("stored %d suggested rules for space=%s", len(new_rules), space)
                    except Exception as e:
                        log.warning("rule suggestion failed for space=%s: %s", space, str(e)[:200])

                metrics_inc(db, name="worker.inference.done", space_id=space)
                db.commit()

            else:
                raise RuntimeError(f"unknown job type: {job.job_type}")

            mark_job_done(db, job)
            return True
        except Exception as e:
            log.exception("error processing job %s", job.id)
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
    # Optionally start the HTTP API in the background when enabled via env var.
    if os.getenv("WORKER_HTTP_API", "0") == "1":
        host = os.getenv("WORKER_HTTP_HOST", "0.0.0.0")
        port = int(os.getenv("WORKER_HTTP_PORT", "8000"))
        start_http_api(host=host, port=port)
    while True:
        did = run_once()
        if not did:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
