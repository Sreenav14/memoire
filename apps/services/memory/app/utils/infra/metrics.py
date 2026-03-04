from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text


def inc(db: Session, *, name: str, space_id: str | None = None, n: int = 1) -> None:
    """Increment a named counter. Upserts into metrics_counters."""
    if space_id is not None:
        db.execute(
            text(
                """
                INSERT INTO metrics_counters(space_id, name, value)
                VALUES (:space_id, :name, :n)
                ON CONFLICT(space_id, name)
                  WHERE space_id IS NOT NULL
                DO UPDATE SET
                  value = metrics_counters.value + EXCLUDED.value,
                  updated_at = now()
                """
            ),
            {"space_id": space_id, "name": name, "n": n},
        )
    else:
        db.execute(
            text(
                """
                INSERT INTO metrics_counters(space_id, name, value)
                VALUES (NULL, :name, :n)
                ON CONFLICT(name)
                  WHERE space_id IS NULL
                DO UPDATE SET
                  value = metrics_counters.value + EXCLUDED.value,
                  updated_at = now()
                """
            ),
            {"name": name, "n": n},
        )
