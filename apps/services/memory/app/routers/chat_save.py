from uuid import UUID
from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..deps import get_db
from ..models import MemoryItem, UserSpace
from ..schema import SaveConversationRequest, ChatMessage
from ..auth_deps import get_current_user
from ..utils.embeddings import embed_text

router = APIRouter(prefix="/chat_save", tags=["chat"])

def _Clean(s: str) -> str:
    return (s or "").strip()

def _pick_messages(messages: list[ChatMessage], mode: str, max_messages: int) -> list[ChatMessage]:
    msgs = [m for m in messages if _Clean(m.content)]
    if not msgs:
        return []
    
    # pick last assistant message
    if mode == "last_assistant":
        for m in reversed(msgs):
            if m.role == 'assistant':
                return [m]
        return []
    
    # for last user + assistant_message
    if mode == "last_user":
        assistant_idx = None
        for i in range(len(msgs)-1, -1, -1):
            if msgs[i].role == 'assistant':
                assistant_idx = i
                break
        if assistant_idx is not None:
            return []
    
        user_idx = None
        for j in range(assistant_idx-1, -1, -1):
            if msgs[j].role == 'user':
                user_idx = j
                break
            
        if user_idx is None:
            return [msgs[assistant_idx]]
        return msgs[msgs[user_idx],msgs[assistant_idx]]

    # for full mode
    if mode == "full":
        max_messages = max(1,min(max_messages or 20, 100))
        return msgs[-max_messages:]
    
    return []

def _format(title: str, selected: list[ChatMessage]) -> str:
    lines = []
    if title:
        lines.append(f"Title: {title}")
        lines.append("")
    for m in selected:
        role = "User" if m.role == "user" else "Assistant"
        lines.append(f"{role}: {_Clean(m.content)}")
    return "\n".join(lines).strip()
        
@router.post("")
def save_chat_to_memory(
    payload: SaveConversationRequest,
    user_id: str = Depends(get_current_user),
    db:Session = Depends(get_db),
):
    # verify access
    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == payload.space_id,
        )
    ).scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")
    
    selected = _pick_messages(payload.messages, payload.mode, payload.max_message)
    if not selected:
        raise HTTPException(status_code=400, detail="No messages to save")
    
    content = _format(payload.title, selected)
    
    try:
        vec = embed_text(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")
    
    # insert into memory
    item = MemoryItem(
        space_id = payload.space_id,
        user_id = UUID(user_id),
        type = "note",
        content = content,
        emb_text = vec,
    )
    
    db.add(item)
    db.commit()
    db.refresh(item)
    
    return {
        "id": str(item.id),
        "space_id": str(item.space_id),
        "user_id":str(item.user_id),
        "created_at": item.created_at,
        "mode": payload.mode,
    }
            