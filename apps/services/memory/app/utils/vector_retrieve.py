from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from .embeddings import embed_text

def vector_recall_chunks(
    db: Session,
    *,
    space_id: str,
    question: str,
    top_k: int = 12,
) -> list[dict]:
    """ 
    Fast semantic recall using pgvector
    Returns top-k chunks with similarity scores
    """
    qvec = embed_text(question)
    
    # NOTE: order by distance: smaller is more similar
    
    rows = db.execute(
        text(
            """ 
            SELECT id, document_id, chunk_index, text, (embeddings <-> :qvec) AS distance
            FROM chunks
            WHERE space_id = :space_id
            ORDER BY embeddings <-> :qvec
            LIMIT :top_k
            """
        ),
        {"space_id": space_id, "qvec": qvec, "top_k": top_k}
    ).fetchall()
    
    out = []
    for r in rows:
        out.append({
            "chunk_id": str(r[0]),
            "document_id": str(r[1]),
            "chunk_index": int(r[2]),
            "text": r[3],
            "distance": float(r[4]),
        })
    return out