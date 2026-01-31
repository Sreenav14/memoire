from uuid import UUID
from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select, Float, text as sql_text

from ..deps import get_db
from ..models import MemoryItem, UserSpace, Chunk, Document
from ..auth_deps import get_current_user
from ..utils.embeddings import embed_text

router = APIRouter(prefix="/search", tags=["memory"])

@router.get("")
def search_memory(
    space_id: UUID,
    q: str,
    k: int = 10,
    scope: str = "all", # all/notes/documents
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = (q or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Search query is required")

    k = max(1, min(k, 50))

    # verify access
    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == space_id
        )
    ).scalar_one_or_none()

    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")

    # embed query (OpenAI text-embedding-3-small -> 1536 dims)
    try:
        q_vec = embed_text(q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

    # tune HNSW recall (higher = better recall, slower)
    try:
        db.execute(sql_text("SET LOCAL hnsw.ef_search = :v"), {"v": 80})
    except Exception:
        pass
    results = []
    # vector search (use emb_text 1536)
    if scope in ["all", "notes"]:
        note_rows = db.execute(
            select(
                MemoryItem.id,
                MemoryItem.content,
                MemoryItem.created_at,
                (MemoryItem.emb_text.op("<=>")(q_vec)).cast(Float).label("distance"),
            )
            .where(
                MemoryItem.space_id == space_id,
                MemoryItem.type == "note",
                MemoryItem.emb_text.is_not(None),
            )
            .order_by(MemoryItem.emb_text.op("<=>")(q_vec))
            .limit(k)
        ).all()

       
        for r in note_rows:
            distance = float(r.distance)
            score = 1.0 / (1.0 + distance)
            results.append(
                {
                    "id": str(r.id),
                    "content": r.content,
                    "created_at": r.created_at,
                    "score": score,
                }
            )
        
        # for documnets
        if scope in ["all", "documents"]:
            chunk_rows = db.execute(
                select(
                    Chunk.id.label("chunk_id"),
                    Chunk.document_id.label("documnet_id"),
                    Chunk.chunk_index.label("chunk_index"),
                    Chunk.text.label("chunk_text"),
                    (Chunk.embeddings.op("<=>")(q_vec)).cast(Float).label("distance"),
                    
                    Document.title.label("doc_title"),
                    Document.source_type.label("Doc_source_type"),
                    Document.source_url.label("Doc_source_url"),
                    Document.status.label("Doc_status"),
                )
                .join(Document, Document.id == Chunk.document_id)
                .where(
                    Chunk.space_id == space_id,
                    Chunk.embeddings.is_not(None),
                    Document.status == "ready",
                )
                .order_by(Chunk.embeddings.op("<=>")(q_vec)).limit(k)
            ).all
        
        for r in chunk_rows:
            distance = float(r.distance)
            score = 1.0/(1.0+distance)
            results.append(
                {
                    "kind": "document",
                    "id": str(r.chunk_id),
                    "text": r.chunk_text,
                    "score": score,
                    "document": {
                        "document_id": str(r.document_id),
                        "chunk_index": int(r.chunk_index),
                        "title": r.doc_title,
                        "source_type": r.doc_source_type,
                        "source_url": r.doc_source_url,
                        "status": r.doc_status,
                    },
                }
            )

    # merge if all
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:k]
    
    return {"query": q, "k": k, "results": results}
