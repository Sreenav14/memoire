from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Depends, APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, text

from ..deps import get_db
from ..models import UserSpace
from ..auth_deps import get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileAboutUpdate(BaseModel):
    space_id: UUID
    about: str = ""


def _require_space_access(db: Session, *, space_id: UUID, user_id: str) -> None:
    membership = db.execute(
        select(UserSpace).where(
            UserSpace.user_id == UUID(user_id),
            UserSpace.space_id == space_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this space")


@router.get("/about")
def get_profile_about(
    space_id: UUID,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the free-text profile for this user in this space."""
    _require_space_access(db, space_id=space_id, user_id=user_id)

    row = db.execute(
        text(
            """
            SELECT static_profile
            FROM profiles
            WHERE space_id = :space_id AND user_id = :user_id
            """
        ),
        {"space_id": str(space_id), "user_id": user_id},
    ).fetchone()

    static_profile = row[0] if row else {}
    about = ""
    if isinstance(static_profile, dict):
        about = (static_profile.get("about") or "").strip()

    return {"about": about}


@router.post("/about")
def set_profile_about(
    payload: ProfileAboutUpdate,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sets/replaces the free-text profile for this user in this space."""
    about_text = (payload.about or "").strip()

    _require_space_access(db, space_id=payload.space_id, user_id=user_id)

    db.execute(
        text(
            """
            INSERT INTO profiles (space_id, user_id, static_profile, dynamic_profile)
            VALUES(
                :space_id,
                :user_id,
                jsonb_build_object('about', :about),
                '{}'::jsonb
            )
            ON CONFLICT (space_id, user_id) DO UPDATE
                SET static_profile = COALESCE(profiles.static_profile, '{}'::jsonb)
                    || jsonb_build_object('about', :about),
                    updated_at = now()
            """
        ),
        {"space_id": str(payload.space_id), "user_id": user_id, "about": about_text},
    )
    db.commit()
    return {"ok": True}
