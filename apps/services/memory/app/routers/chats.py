from __future__ import annotations

import os
from uuid import UUID

from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select, text as sql_text

from ..deps import get_db
from ..models import UserSpace
from ..auth_deps import get_current_user
from ..schema import ChatRequest, ChatResponse, MemoryCitation

from ..utils.retrieval.vector import vector_recall_chunks
from ..utils.retrieval.seeds import edge_keys_from_chunks, entity_seeds_from_edges
from ..utils.retrieval.graph_expand import graph_expand
from ..utils.retrieval.evidence import build_grounded_evidence, build_graph_context
from ..utils.infra.limits import GLOBAL_RATE_LIMITER, GLOBAL_CONCURRENCY, RateLimit
from ..utils.infra.metrics import inc as metrics_inc
from ..utils.llm.gateway import chat_completion

router = APIRouter(prefix="/chats", tags=["chats"])

MIN_EXPLICIT_EDGES = 12


def _build_vector_context(chunks: list[dict], max_chunks: int = 6) -> str:
    lines = []
    for c in chunks[:max_chunks]:
        lines.append(f"[chunk:{c['chunk_id']}] {c['text'][:450]}")
    return "\n".join(lines)


def _load_profile_about(db: Session, *, space_id: str, user_id: str) -> str:
    row = db.execute(
        sql_text(
            """
            SELECT static_profile
            FROM profiles
            WHERE space_id = :space_id AND user_id = :user_id
            """
        ),
        {"space_id": space_id, "user_id": user_id},
    ).fetchone()

    if not row:
        return ""
    static_profile = row[0] or {}
    if isinstance(static_profile, dict):
        return (static_profile.get("about") or "").strip()
    return ""


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message is required")

    k = max(5, min(payload.k, 30))

    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == payload.space_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")

    about = _load_profile_about(db, space_id=str(payload.space_id), user_id=user_id)
    about_block = about if about else "(no profile provided)"

    # --- Rate / concurrency limits ---
    user_key = f"chat:user:{user_id}"
    space_key = f"chat:space:{payload.space_id}"

    if not GLOBAL_RATE_LIMITER.allow(user_key, RateLimit(max_requests=10, window_seconds=60)):
        raise HTTPException(status_code=429, detail="Rate limit exceeded (user)")

    if not GLOBAL_RATE_LIMITER.allow(space_key, RateLimit(max_requests=50, window_seconds=60)):
        raise HTTPException(status_code=429, detail="Rate limit exceeded (space)")

    GLOBAL_CONCURRENCY.acquire(user_key, max_concurrent=3)
    try:
        try:
            db.execute(sql_text("SET LOCAL hnsw.ef_search = :v"), {"v": 80})
        except Exception:
            pass

        # 1) Vector recall
        chunks = vector_recall_chunks(db, space_id=str(payload.space_id), question=msg, top_k=k)
        chunk_ids = [c["chunk_id"] for c in chunks]

        # 2) Seeds from chunks -> edges -> entities
        seed_edge_keys = edge_keys_from_chunks(db, space_id=str(payload.space_id), chunk_ids=chunk_ids, limit=80)
        seed_entities = entity_seeds_from_edges(db, space_id=str(payload.space_id), edge_keys=seed_edge_keys, limit=60)

        # 3) Graph expand (2-pass: explicit first, inferred fallback)
        graph_edges = graph_expand(
            db,
            space_id=str(payload.space_id),
            seed_entity_keys=seed_entities,
            max_hops=2,
            limit=60,
            include_inferred=False,
        )

        if len(graph_edges) < MIN_EXPLICIT_EDGES:
            graph_edges = graph_expand(
                db,
                space_id=str(payload.space_id),
                seed_entity_keys=seed_entities,
                max_hops=2,
                limit=60,
                include_inferred=True,
            )

        graph_edge_keys = [e["edge_key"] for e in graph_edges]

        # 4) Evidence pack (grounded citations)
        evidence_rows = build_grounded_evidence(
            db,
            space_id=str(payload.space_id),
            graph_edge_keys=graph_edge_keys,
            limit_total=12,
        )
        graph_ctx = build_graph_context(evidence_rows)
        vector_ctx = _build_vector_context(chunks, max_chunks=6)

        # 5) System + user prompts
        system_prompt = (
            "You are a grounded memory assistant.\n"
            "Use ONLY the provided Graph Evidence as factual support.\n"
            "Cite every factual claim as [id].\n"
            "Some citations support inferred facts, but the quotes are still real evidence.\n"
            "If evidence does not support the answer, say you don't know.\n\n"
            f"User Profile (About / Context for this space):\n{about_block}\n"
        )

        user_prompt = (
            f"Graph Evidence:\n{graph_ctx}\n\n"
            f"Vector Context:\n{vector_ctx}\n\n"
            f"User: {msg}\n\n"
            "Answer:"
        )

        # 6) LLM call via gateway
        try:
            answer = chat_completion(
                provider=payload.provider,
                model=payload.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=f"LLM service error: {str(e)[:200]}")

        # 7) Build citations from cite_for (not raw edge_key)
        memory_used: list[MemoryCitation] = []
        counts: dict[str, int] = {}
        for ev in evidence_rows:
            cite_key = ev["cite_for"]
            counts[cite_key] = counts.get(cite_key, 0) + 1
            cite_id = f"{cite_key}:{counts[cite_key]}"
            memory_used.append(
                MemoryCitation(
                    id=cite_id,
                    score=ev["confidence"],
                    created_at=ev["created_at"],
                    snippet=ev["quote"][:300],
                )
            )

        metrics_inc(db, name="api.chat.calls", space_id=str(payload.space_id))
        db.commit()

        return ChatResponse(answer=answer, memory_used=memory_used)
    finally:
        GLOBAL_CONCURRENCY.release(user_key)
