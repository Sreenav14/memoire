from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, text

from ..deps import get_db
from ..auth_deps import get_current_user
from ..models import UserSpace

router = APIRouter(prefix="/inference-rules", tags=["inference-rules"])


class RuleUpsert(BaseModel):
    space_id: UUID
    name: str
    rule_json: dict
    is_enabled: bool = False


class RuleToggle(BaseModel):
    space_id: UUID
    name: str
    is_enabled: bool


def _access_check(db: Session, *, user_id: str, space_id: UUID) -> None:
    m = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == space_id,
        )
    ).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=403, detail="No access to this space")


@router.get("")
def list_rules(
    space_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _access_check(db, user_id=user_id, space_id=space_id)

    rows = db.execute(
        text(
            """
            SELECT name, rule_json, is_enabled, created_at, updated_at
            FROM inference_rules
            WHERE space_id = :space_id
            ORDER BY name ASC
            """
        ),
        {"space_id": str(space_id)},
    ).fetchall()

    return [
        {
            "name": r[0],
            "rule_json": r[1],
            "is_enabled": bool(r[2]),
            "created_at": r[3],
            "updated_at": r[4],
        }
        for r in rows
    ]


@router.post("")
def upsert_rule(
    payload: RuleUpsert,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _access_check(db, user_id=user_id, space_id=payload.space_id)

    db.execute(
        text(
            """
            INSERT INTO inference_rules(space_id, name, rule_json, is_enabled)
            VALUES (:space_id, :name, :rule_json::jsonb, :is_enabled)
            ON CONFLICT(space_id, name)
            DO UPDATE SET
              rule_json = EXCLUDED.rule_json,
              is_enabled = EXCLUDED.is_enabled,
              updated_at = now()
            """
        ),
        {
            "space_id": str(payload.space_id),
            "name": payload.name,
            "rule_json": json.dumps(payload.rule_json),
            "is_enabled": payload.is_enabled,
        },
    )
    db.commit()
    return {"ok": True}


@router.post("/toggle")
def toggle_rule(
    payload: RuleToggle,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _access_check(db, user_id=user_id, space_id=payload.space_id)

    db.execute(
        text(
            """
            UPDATE inference_rules
            SET is_enabled = :is_enabled,
                updated_at = now()
            WHERE space_id = :space_id AND name = :name
            """
        ),
        {
            "space_id": str(payload.space_id),
            "name": payload.name,
            "is_enabled": payload.is_enabled,
        },
    )
    db.commit()
    return {"ok": True}
