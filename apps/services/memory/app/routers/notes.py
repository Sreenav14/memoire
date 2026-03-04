from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from ..deps import get_db
from ..models import UserSpace, MemoryItem
from ..schema import NoteCreate
from ..auth_deps import get_current_user
from .cursor import encode_cursor, decode_cursor
from ..utils.llm.embeddings import embed_text

router = APIRouter(prefix="/notes", tags=["notes"])


@router.post("")
def create_note(
    payload: NoteCreate,
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user),
            UserSpace.space_id == payload.space_id,
        )
    ).scalar_one_or_none()

    if not allowed:
        raise HTTPException(status_code=403, detail="No access to this space")

    vector = embed_text(payload.content)
    note = MemoryItem(
        space_id=payload.space_id,
        user_id=UUID(user),
        type="note",
        content=payload.content,
        embeddings=vector,
    )

    db.add(note)
    db.commit()
    db.refresh(note)

    return {
        "id": str(note.id),
        "space_id": str(note.space_id),
        "user_id": str(note.user_id),
        "type": note.type,
        "content": note.content,
        "created_at": note.created_at,
    }


@router.get("")
def list_notes(
    space_id: str,
    limit: int = 50,
    cursor: Optional[str] = None,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 100))

    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == UUID(space_id),
        )
    ).scalar_one_or_none()

    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")

    q = (
        select(MemoryItem)
        .where(
            MemoryItem.space_id == UUID(space_id),
            MemoryItem.type == "note",
        )
        .order_by(MemoryItem.created_at.desc(), MemoryItem.id.desc())
        .limit(limit + 1)
    )

    if cursor:
        try:
            cursor_created_at, cursor_id = decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor")
        q = q.filter(
            or_(
                MemoryItem.created_at < cursor_created_at,
                and_(
                    MemoryItem.created_at == cursor_created_at,
                    MemoryItem.id < UUID(cursor_id),
                ),
            )
        )

    rows = db.execute(q).scalars().all()

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(last.created_at, str(last.id))

    return {
        "items": [
            {
                "id": str(item.id),
                "space_id": str(item.space_id),
                "user_id": str(item.user_id),
                "type": item.type,
                "content": item.content,
                "created_at": item.created_at,
            }
            for item in items
        ],
        "next_cursor": next_cursor,
    }


@router.get("/{note_id}")
def get_note(
    note_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = db.execute(
        select(MemoryItem).where(
            MemoryItem.id == UUID(note_id),
            MemoryItem.type == "note",
        )
    ).scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == note.space_id,
        )
    ).scalar_one_or_none()

    if not membership:
        raise HTTPException(status_code=403, detail="No access to this note")

    return {
        "id": str(note.id),
        "space_id": str(note.space_id),
        "user_id": str(note.user_id),
        "type": note.type,
        "content": note.content,
        "created_at": note.created_at,
    }
