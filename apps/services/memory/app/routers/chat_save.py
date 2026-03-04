from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..deps import get_db
from ..models import UserSpace, Document, IngestionJob
from ..schema import SaveConversationRequest, ChatMessage
from ..auth_deps import get_current_user

router = APIRouter(prefix="/chat_save", tags=["chats"])


def _clean(s: str) -> str:
    return (s or "").strip()


def _pick_messages(messages: list[ChatMessage], mode: str, max_messages: int) -> list[ChatMessage]:
    msgs = [m for m in messages if _clean(m.content)]
    if not msgs:
        return []

    if mode == "last_assistant":
        for m in reversed(msgs):
            if m.role == "assistant":
                return [m]
        return []

    if mode == "last_user":
        assistant_idx = None
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].role == "assistant":
                assistant_idx = i
                break

        if assistant_idx is None:
            for m in reversed(msgs):
                if m.role == "user":
                    return [m]
            return []

        user_idx = None
        for j in range(assistant_idx - 1, -1, -1):
            if msgs[j].role == "user":
                user_idx = j
                break

        if user_idx is not None:
            return [msgs[user_idx], msgs[assistant_idx]]
        return [msgs[assistant_idx]]

    if mode == "full":
        max_messages = max(1, min(max_messages or 20, 100))
        return msgs[-max_messages:]

    return []


def _format(title: str | None, selected: list[ChatMessage]) -> str:
    lines: list[str] = []
    if title:
        lines.append(f"Title: {_clean(title)}")
        lines.append("")
    for m in selected:
        role = "User" if m.role == "user" else "Assistant"
        lines.append(f"{role}: {_clean(m.content)}")
        lines.append("")
    return "\n".join(lines).strip()


@router.post("")
def save_chat_to_memory(
    payload: SaveConversationRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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

    doc = Document(
        space_id=payload.space_id,
        user_id=UUID(user_id),
        source_type="chat",
        title=payload.title or "Saved Chat",
        source_url=None,
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    job = IngestionJob(
        job_type="document_ingest",
        space_id=payload.space_id,
        document_id=doc.id,
        payload={
            "kind": "text",
            "text": content,
        },
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {
        "document_id": str(doc.id),
        "job_id": str(job.id),
        "mode": payload.mode,
    }
