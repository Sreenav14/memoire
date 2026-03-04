from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..graph.age import GRAPH_NAME, _age_setup_sql

log = logging.getLogger("memoire.worker.rules")


def discover_relations(db: Session, space_id: str) -> list[str]:
    """Return distinct relation type names for a space from the AGE graph."""
    try:
        db.execute(text(_age_setup_sql()))

        rows = db.execute(
            text(
                """
                SELECT * FROM cypher(:g, $$
                    MATCH ()-[r]->()
                    WHERE r.space_id = $space_id
                    RETURN DISTINCT type(r)
                $$, $params) AS (rel agtype);
                """
            ),
            {"g": GRAPH_NAME, "params": {"space_id": space_id}},
        ).fetchall()

        return [str(r[0]).strip('"') for r in rows]
    except Exception as e:
        log.warning("discover_relations failed for space=%s: %s", space_id, str(e)[:200])
        return []
