from uuid import UUID
from fastapi import FastAPI, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy import Float

from ..deps import get_db
from ..models import MemoryItem, UserSpace
from ..auth_deps import get_current_user
from ..utils.embeddings import generate_stub_embedding

router = APIRouter(prefix="/search", tags=["memory"])

@router.get("")
def search_memory(
    space_id: UUID,
    q: str,
    k: int = 10,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    q = (q or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Search query is required")
    
    if k < 1:
        k = 1
    if k > 50:
        k = 50
        
    # verify access
    membership = db.execute(
        select(UserSpace).where(UserSpace.user_id == UUID(user_id),
                                UserSpace.space_id == space_id)
    ).scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")
    
    # embed query
    q_vec = generate_stub_embedding(q)
    
    
    # vector search
    rows = db.execute(
        select(
            MemoryItem.id,
            MemoryItem.content,
            MemoryItem.created_at,
            (MemoryItem.embeddings.op("<=>")(q_vec)).cast(Float).label("distance"),
        )
        .where(
            MemoryItem.space_id == space_id,
            MemoryItem.type == "note",
            MemoryItem.embeddings.is_not(None),
        )
        .order_by((MemoryItem.embeddings.op("<=>")(q_vec))).limit(k)
        ).all()
    results = []
    for r in rows:
        distance = float(r.distance)
        # convert distance to a friendly similarity score
        score = 1.0 / (1.0 + distance)
        
        results.append(
            {
                
                "id": str(r.id),
                "content": r.content,
                "created_at": r.created_at,
                "score": score,
            }
        )
        
    return {"query": q, "k": k, "results": results}
        