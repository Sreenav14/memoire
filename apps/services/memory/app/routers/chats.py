import os
from uuid import UUID
from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select, text as sql_text

from ..deps import get_db
from ..models import UserSpace
from ..auth_deps import get_current_user
from ..schema import ChatRequest, ChatResponse, MemoryCitation

from ..utils.vector_retrieve import vector_recall_chunks
from ..utils.seed_builder import edge_keys_from_chunks, entity_seeds_from_edges
from ..utils.graph_retrieve import graph_expand

from ..utils.limits import GLOBAL_RATE_LIMITER, GLOBAL_CONCURRENCY, RateLimit
from ..utils.llm_gateway import chat_completion


from openai import OpenAI
from groq import Groq

router = APIRouter(prefix="/chats", tags=["chats"])

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
DEFAULT_GROQ_MODEL = os.getenv("GROQ_CHAT_MODEL", "llama-3.1-8b-instant")


def call_openai_chat(model: str, system_prompt: str, user_prompt: str) -> str:
    resp = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    return resp.choices[0].message.content or ""


def call_groq_chat(model: str, system_prompt: str, user_prompt: str) -> str:
    resp = groq_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    return resp.choices[0].message.content or ""


def fetch_evidence_rows(db: Session, *, space_id: str, edge_keys: list[str], limit_total: int = 12) -> list[dict]:
    if not edge_keys:
        return []
    rows = db.execute(
        sql_text(
            """
            SELECT edge_key, quote, confidence, created_at
            FROM graph_evidence
            WHERE space_id = :space_id
              AND edge_key = ANY(:edge_keys)
            ORDER BY confidence DESC, created_at DESC
            LIMIT :limit_total
            """
        ),
        {"space_id": space_id, "edge_keys": edge_keys, "limit_total": limit_total},
    ).fetchall()

    out = []
    for edge_key, quote, conf, created_at in rows:
        out.append(
            {
                "edge_key": str(edge_key),
                "quote": (quote or "").strip(),
                "confidence": float(conf),
                "created_at": created_at,
            }
        )
    return out


def build_graph_context(evidence_rows: list[dict]) -> str:
    lines = []
    for i, ev in enumerate(evidence_rows, start=1):
        cite_id = f"{ev['edge_key']}:{i}"
        lines.append(f"[{cite_id}] {ev['quote']}")
    return "\n".join(lines)


def build_vector_context(chunks: list[dict], max_chunks: int = 6) -> str:
    lines = []
    for c in chunks[:max_chunks]:
        lines.append(f"[chunk:{c['chunk_id']}] {c['text'][:450]}")
    return "\n".join(lines)


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message is required")

    k = max(5, min(getattr(payload, "k", 12), 30))

    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == payload.space_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")
    
    
    # Rate limits
    user_key = f"chat:user:{user_id}"
    space_key = f"chat:space:{payload.space_id}"
    
    if not GLOBAL_RATE_LIMITER.allow(user_key, RateLimit(max_requests=10, window_seconds=60)):
        raise HTTPException(status_code=429, detail="Rate limit exceeded (user)")
    
    if not GLOBAL_RATE_LIMITER.allow(space_key, RateLimit(max_requests=50, window_seconds=60)):
        return HTTPException(status_code=429, detail = "Rate limit exceeded (space)")
    
    # concurrency limit (3 active chats per user)
    GLOBAL_CONCURRENCY.acquire(user_key, max_concurrent=3)
    try:
        try:
            db.execute(sql_text("SET LOCAL hnsw.ef_search = :v"), {"v": 80})
        except Exception:
            pass

        # 1) Vector recall
        chunks = vector_recall_chunks(db, space_id=str(payload.space_id), question=msg, top_k=k)
        chunk_ids = [c["chunk_id"] for c in chunks]

        # 2) Seeds
        seed_edge_keys = edge_keys_from_chunks(db, space_id=str(payload.space_id), chunk_ids=chunk_ids, limit=80)
        seed_entities = entity_seeds_from_edges(db, space_id=str(payload.space_id), edge_keys=seed_edge_keys, limit=60)

        # 3) Graph expand
        graph_edges = graph_expand(
            db,
            space_id=str(payload.space_id),
            seed_entity_keys=seed_entities,
            max_hops=2,
            limit=60,
        )
        graph_edge_keys = [e["edge_key"] for e in graph_edges]

        # 4) Evidence for citations (what we return to user)
        evidence_rows = fetch_evidence_rows(db, space_id=str(payload.space_id), edge_keys=graph_edge_keys, limit_total=12)

        graph_ctx = build_graph_context(evidence_rows)
        vector_ctx = build_vector_context(chunks, max_chunks=6)

        system_prompt = (
            "You are a grounded memory assistant.\n"
            "Use the provided evidence as the source of truth.\n"
            "When stating a fact, cite it as [id] exactly.\n"
            "If evidence does not support the answer, say you don't know.\n"
        )

        user_prompt = (
            f"Graph Evidence:\n{graph_ctx}\n\n"
            f"Vector Context:\n{vector_ctx}\n\n"
            f"User: {msg}\n\n"
            "Answer:"
        )

        # LLM call via gateway
        answer = chat_completion(
            provider = payload.provider,
            model = payload.model,
            system_prompt = system_prompt,
            user_prompt = user_prompt,
            max_tokens = 1500,
        )

        memory_used = []
        for i, ev in enumerate(evidence_rows, start=1):
            cite_id = f"{ev['edge_key']}:{i}"
            memory_used.append(
                MemoryCitation(
                    id=cite_id,
                    score=ev["confidence"],
                    created_at=ev["created_at"],
                    snippet=ev["quote"][:300],
                )
            )

        return ChatResponse(answer=answer, memory_used=memory_used)
    finally: 
        GLOBAL_CONCURRENCY.release(user_key)