import json
import uuid
from uuid import UUID
from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional
from fastapi import UploadFile
from fastapi.params import Form, File
import os
from dotenv import load_dotenv

load_dotenv()

from ..deps import get_db
from ..models import UserSpace, Document, IngestionJob
from ..auth_deps import get_current_user
from ..schema import DocumentCreate, DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))

def require_space_access(db: Session, space_id: UUID, user_id: str):
    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id==space_id
        )
    ).scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")
    
@router.post("", response_model=DocumentOut)
def create_document(
    req: DocumentCreate,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    
    # 1. access check
    require_space_access(db, req.space_id, user_id)
    
    # 2. validate payload
    if not (req.text and req.text.strip() and not (req.source_url and req.source_url.strip())):
        raise HTTPException(status_code=400, detail= "provide either text or source_url")
    
    # 3. create document
    doc = Document(
        id = uuid.uuid4(),
        space_id = req.space_id,
        user_id = UUID(user_id),
        source_type = req.source_type,
        title = req.title,
        source_url = req.source_url,
        status = "pending",
    )
    
    db.add(doc)
    db.flush()
    
    payload = {
        "text": req.text,             # for pasted text ingestion
        "source_url": req.source_url, # for url ingestion
        "title": req.title,
        "source_type": req.source_type,
    }
    
    job = IngestionJob(
       id = uuid.uuid4(),
       job_type = "document_ingest",
       space_id = req.space_id,
       document_id = doc.id,
       payload = json.dumps(payload),
       status = "queued",
       
   )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return DocumentOut(
        id = doc.id,
        space_id = doc.space_id,
        user_id = doc.user_id,
        source_type = doc.source_type,
        title = doc.title,
        source_url = doc.source_url,
        status = doc.status,
        created_at = doc.created_at.isoformat(),
    )
    
@router.get("", response_model=list[DocumentOut])
def list_documents(
    space_id: UUID,
    user_id: str = Depends(get_current_user),
    db:Session = Depends(get_db)
):
    
    # 1. access check
    require_space_access(db, space_id, user_id)
    
    # 2. return docs newest first
    docs = db.execute(
        select(Document).where(
            Document.space_id == space_id.order_by(Document.created_at.desc())).scalars().all()
        )
    return [
        DocumentOut(
            id = d.id,
            space_id = d.space_id,
            user_id = d.user_id,
            source_type = d.source_type,
            title = d.title,
            source_url = d.source_url,
            status = d.status,
            created_at = d.created_at.isoformat(),
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

    # Access check (doc.space_id)
    require_space_access(db, doc.space_id, user_id)

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
    require_space_access(db, space_id, user_id)
    
    # 1. validate file
    filename = file.filename or "upload.pdf"
    content_type = file.content_type or ContentType.PDF
    
    if not (filename.lower().endswith(".pdf") or content_type == "application/pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PDF file.")
    
    # 2. check file size
    data = file.file.read()
    size_mb = len(data) / (1024*1024)
    if size_mb > MAX_MB:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_MB}MB")
    
    # 3. save file
    os.makedirs(UPLOAD_DIR, exists_ok = True)
    doc_id = uuid.uuid4()
    safe_name = f"{doc_id}.pdf"
    path = os.path.join(UPLOAD_DIR, safe_name)
    
    with open(path, "wb") as f:
        f.write(data)
        
    # 4. create document
    doc = Document(
        id = doc_id,
        space_id = space_id,
        user_id = UUID(user_id),
        source_type = "upload",
        title = title or filename,
        source_url = path,
        status = "pending",
    )
    db.add(doc)
    db.flsuh()
    
    # 5. create ingestion job (worker will extract pdf)
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
        payload=json.dumps(payload),
        status="queued",
    )
    db.add(job)
    
    db.commit()
    db.refresh(job)
    
    return DocumentOut(
        id=doc.id,
        space_id=doc.space_id,
        user_id = doc.user_id,
        source_type = doc.source_type,
        title = doc.title,
        source_url = doc.source_url,
        status = doc.status,
        created_at = doc.created_at.isoformat(),
    )