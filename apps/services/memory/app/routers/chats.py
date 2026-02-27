import os
from uuid import UUID
from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select, text as sql_text
from sqlalchemy.orm.writeonly import relationships

from ..deps import get_db
from ..models import UserSpace
from ..auth_deps import get_current_user
from ..schema import ChatRequest, ChatResponse

from ..utils.vector_retrieve import vector_recall_chunks
from ..utils.seed_builder import edge_keys_from_chunks, entity_seeds_from_edges
from ..utils.graph_retrieve import graph_expand, evidence_pack
from ..utils.embeddings import embed_text

from openai import OpenAI
from groq import Groq

router = APIRouter(prefix="/chats", tags=["chats"])

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
DEFAULT_GROQ_MODEL = os.getenv("GROQ_CHAT_MODEL","llama-3.1-8b-instant")

def build_vector_context(chunks: list[dict], max_chunks: int = 6) -> str:
    """ 
    Small amount of semantic context from pgvector recall
    """
    lines: list[str] = []
    for c in chunks[:max_chunks]:
        lines.append(f"[CHUNK {c['chunk_id']}] {c['text'][:450]}")
    return "\n".join(lines)

def build_graph_context(graph_edges: list[dict], evidence: dict[str, list[dict]], max_edges:int=30) -> str:
    """ 
    structured facts + citations
    The model must cite using [CITE edge_key:n]
    """
    lines: list[str] = []
    for e in graph_edges[:max_edges]:
        ek = e["edge_key"]
        rel = e.get("relation")
        conf = e.get("confidence")
        kind = e.get("kind")
        state = e.get("state")
        
        lines.append(f"[EDGE {ek}] rel = {rel}, confidence = {conf}, kind = {kind}, state = {state}")
        
        cites = evidence.get(ek, [])[:2]
        for i, ev in enumerate(cites, start=1):
            quote = (ev.get("quote") or "").strip()
            chunk_id = ev.get("chunk_id")
            doc_id = ev.get("document_id")
            cs = ev.get("char_start")
            ce = ev.get("char_end")
            lines.append(f"  [CITE {ek}:{i}] doc={doc_id} chunk={chunk_id} offset={cs}-{ce} quote={quote}")
            
    return "\n".join(lines)

def call_openai_chat(model: str, system_prompt: str, user_prompt: str)-> str:
    resp = openai_client.chat.completions.create(
        model= model,
        messages=[
            {"role":"system","content":system_prompt},
            {"role":"user","content":user_prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
        top_p=1,
        presence_penalty = 0.0,
        frequency_penalty = 0.0,       
    )
    return resp.choices[0].message.content or " "

def call_groq_chat(model: str, system_prompt: str, user_prompt: str) -> str:
    resp = groq_client.chat.completions.create(
        model=model,
        messages = [
            {"role":"system","content": system_prompt},
            {"role":"user","content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    return resp.choices[0].message.content or ""

@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message is required")
        
    # Keep reasonable range
    k = max(5, min(getattr(payload, "k", 12), 30))
    
    # verify access
    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == payload.space_id,
        )
    ).scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")
    
    #  HNSW
    try:
        db.execute(sql_text("SET LOCAL hnsw.ef_search = :v"), {"v": 80})
    except Exception:
        pass
    
    # vector recall
    chunks = vector_recall_chunks(db, space_id=str(payload.space_id), question=msg, top_k=k)
    chunk_ids = [c["chunk_id"] for c in chunks]
    
    # seed from evidence 
    seed_edge_keys = edge_keys_from_chunks(db, space_id=str(payload.space_id), chunk_ids=chunk_ids, limit=80)
    seed_entities = entity_seeds_from_edges(db, space_id=str(payload.space_id),edge_keys=seed_edge_keys, limit=60)
    
    # Grapg expand
    graph_edges = graph_expand(
        db,
        space_id=str(payload.space_id),
        seed_entity_keys=seed_entities,
        max_hops=2,
        limit=60,
    )
    graph_edge_keys = [e["edge_key"] for e in graph_edges]
    
    #  Evidence pack
    evidence = evidence_pack(
        db,
        space_id = str(payload.space_id),
        edge_keys = graph_edge_keys,
        limit_per_edge=2
    )
    
    # prompts
    graph_ctx = build_graph_context(graph_edges, evidence, max_edges=30)
    vector_ctx = build_vector_context(chunks, max_chunks=6)
    
    system_prompt = (
        "You are a grounded memory assistant.\n"
        "Use provided information as primary source of truth.\n"
        "when user ask for a fact, cite the evidence using [CITE edge_key:n]\n"
        "If evidence does not support the answer, say you don't know.\n"
    )
    
    user_prompt = (
        f"Graph Facts + Evidence: \n{graph_ctx}\n\n"
        f"Vector Context: \n{vector_ctx}\n\n"
        f"User Question: {msg}\n\n"
        "Answer with citations to the evidence if asked"
    )
    
    provider = payload.provider
    if provider == "openai":
        model = payload.model or DEFAULT_OPENAI_MODEL
        if not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")
        answer = call_openai_chat(model, system_prompt, user_prompt)
        
    elif provider == "qroq":
        model = payload.model or DEFAULT_GROQ_MODEL
        if not os.getenv("GROQ_API_KEY"):
            raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set")
        answer = call_groq_chat(model, system_prompt, user_prompt)
        
    else:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")
    
    return {
        "answer": answer,
        "model": model,
        "memory_user":{
            "vector_chunks": chunks[:k],
            "seed_entities": seed_entities,
            "graph_edges": graph_edges,
        },
    }
    