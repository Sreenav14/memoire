import os
from uuid import UUID
from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select, Float, text as sql_text

from ..deps import get_db
from ..models import MemoryItem, UserSpace
from ..auth_deps import get_current_user
from ..schema import ChatRequest, ChatResponse
from ..utils.embeddings import embed_text

from openai import OpenAI
from groq import Groq

router = APIRouter(prefix="/chats", tags=["chat"])

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
DEFAULT_GROQ_MODEL = os.getenv("GROQ_CHAT_MODEL", "llama-3.1-8b-instant")


def build_context(memories: list[dict])-> str:
    # just return cite by [id]
    
    return "\n\n".join([f"[{m["id"]}] {m['snippet']}" for m in memories])


def call_openai_chat(model:str,system_prompt:str, user_prompt:str)-> str:
    resp = openai_client.chat.completions.create(
        model = model,
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature = 0.2,
        max_tokens = 500,
        top_p = 1.0,
        presence_penalty = 0.0,
        frequency_penalty = 0.0,
    )
    return resp.choices[0].message.content or ""

def call_groq_chat(model:str, system_prompt:str, user_prompt:str)-> str:
    resp = groq_client.chat.completions.create(
        model = model,
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature = 0.2,
        max_tokens = 500,
    )
    return resp.choices[0].message.content or ""

@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    msg = (payload.message or "").strip()
    if not msg: 
        raise HTTPException(status_code=400, detail="Message is required")
    
    k = max(1, min(payload.k, 20))
    
    # verify access
    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == payload.space_id
        )
    ).scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")
    
    # embed query for retrival
    try:
        q_vec = embed_text(msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")
    
    # HNSW tuning
    try:
        db.exeute(sql_text("SET LOCAL hnsw.ef_search =:v"), {"v":80})
    except Exception:
        pass
    
    # Vector Search
    rows = db.execute(
        select(
            MemoryItem.id,
            MemoryItem.content,
            MemoryItem.created_at,
            (MemoryItem.emb_text.op("<=>")(q_vec)).cast(Float).label("distance"),
        ).where(
            MemoryItem.space_id == payload.space_id,
            MemoryItem.emb_text.is_not(None),
        ).order_by(MemoryItem.emb_text.op("<=>")(q_vec)).limit(k)
    ).all()
    
    memories = []
    
    for r in rows:
        distance = float(r.distance)
        score = 1.0 / (1.0 + distance)
        snippet = (r.content or "")[:300]
        memories.append({
            "id": str(r.id),
            "score": score,
            "created_at": r.created_at,
            "snippet": snippet,
        })
        
    context = build_context(memories)
    
    system_prompt = (
        "You are a super memory, a second brain.\n"
        "Use the provided memory context when relevant.\n"
        "If the context does not contain the answer, say you don't know.\n"
        "When you use a memory item, cite it as [id] exactly.\n"
    )
    
    user_prompt = (
        f"Memory Context:\n{context}\n"
        f"User: {msg}\n\n"
        "Answer:"
    )
    
    provider = payload.provider 
    if provider == "openai":
        model = payload.model or DEFAULT_OPENAI_MODEL
        if not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")
        answer = call_openai_chat(model, system_prompt, user_prompt)
        
    elif provider == "groq":
        model = payload.model or DEFAULT_GROQ_MODEL
        if not os.getenv("GROQ_API_KEY"):
            raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set")
        answer = call_groq_chat(model, system_prompt, user_prompt)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")
    
    return {
        "answer": answer,
        "memory_used": memories,
        "model": model,
        "memory_used": memories,
    }