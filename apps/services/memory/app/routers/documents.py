from __future__ import annotations

import os
import uuid
from uuid import UUID
from typing import Optional

from fastapi import HTTPException, Depends, APIRouter, UploadFile
from fastapi.params import Form, File
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..deps import get_db
from ..models import UserSpace, Document, IngestionJob
from ..auth_deps import get_current_user
from ..schema import DocumentCreate, DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))


def _require_space_access(db: Session, space_id: UUID, user_id: str) -> None:
    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == space_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")


@router.post("", response_model=DocumentOut)
def create_document(
    req: DocumentCreate,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_space_access(db, req.space_id, user_id)

    has_text = bool(req.text and req.text.strip())
    has_url = bool(req.source_url and req.source_url.strip())

    if has_text and has_url:
        raise HTTPException(status_code=400, detail="Provide exactly one of text or source_url")

    if not has_text and not has_url:
        raise HTTPException(status_code=400, detail="Provide at least one of text or source_url")

    doc = Document(
        id=uuid.uuid4(),
        space_id=req.space_id,
        user_id=UUID(user_id),
        source_type=req.source_type,
        title=req.title,
        source_url=req.source_url,
        status="pending",
    )

    db.add(doc)
    db.flush()

    payload = {
        "kind": "text" if has_text else "url",
        "text": req.text if has_text else None,
        "source_url": req.source_url if has_url else None,
        "title": req.title,
        "source_type": req.source_type,
    }

    job = IngestionJob(
        id=uuid.uuid4(),
        job_type="document_ingest",
        space_id=req.space_id,
        document_id=doc.id,
        payload=payload,
        status="queued",
    )

    db.add(job)
    db.commit()
    db.refresh(doc)

    return DocumentOut(
        id=doc.id,
        space_id=doc.space_id,
        user_id=doc.user_id,
        source_type=doc.source_type,
        title=doc.title,
        source_url=doc.source_url,
        status=doc.status,
        created_at=doc.created_at.isoformat(),
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    space_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_space_access(db, space_id, user_id)

    docs = db.execute(
        select(Document)
        .where(Document.space_id == space_id)
        .order_by(Document.created_at.desc())
    ).scalars().all()

    return [
        DocumentOut(
            id=d.id,
            space_id=d.space_id,
            user_id=d.user_id,
            source_type=d.source_type,
            title=d.title,
            source_url=d.source_url,
            status=d.status,
            created_at=d.created_at.isoformat(),
        )
        for d in docs
    ]


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    _require_space_access(db, doc.space_id, user_id)

    return DocumentOut(
        id=doc.id,
        space_id=doc.space_id,
        user_id=doc.user_id,
        source_type=doc.source_type,
        title=doc.title,
        source_url=doc.source_url,
        status=doc.status,
        created_at=doc.created_at.isoformat(),
    )


@router.post("/upload", response_model=DocumentOut)
def upload_pdf(
    space_id: UUID = Form(...),
    title: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_space_access(db, space_id, user_id)

    filename = file.filename or "upload.pdf"
    content_type = file.content_type or "application/pdf"

    if not (filename.lower().endswith(".pdf") or content_type == "application/pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PDF file.")

    data = file.file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_MB:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_MB}MB")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    doc_id = uuid.uuid4()
    safe_name = f"{doc_id}.pdf"
    path = os.path.join(UPLOAD_DIR, safe_name)

    with open(path, "wb") as f:
        f.write(data)

    doc = Document(
        id=doc_id,
        space_id=space_id,
        user_id=UUID(user_id),
        source_type="upload",
        title=title or filename,
        source_url=path,
        status="pending",
    )
    db.add(doc)
    db.flush()

    payload = {
        "kind": "pdf",
        "file_path": path,
        "filename": filename,
        "content_type": content_type,
        "title": doc.title,
    }

    job = IngestionJob(
        id=uuid.uuid4(),
        job_type="document_ingest",
        space_id=space_id,
        document_id=doc.id,
        payload=payload,
        status="queued",
    )
    db.add(job)

    db.commit()
    db.refresh(doc)

    return DocumentOut(
        id=doc.id,
        space_id=doc.space_id,
        user_id=doc.user_id,
        source_type=doc.source_type,
        title=doc.title,
        source_url=doc.source_url,
        status=doc.status,
        created_at=doc.created_at.isoformat(),
    )
