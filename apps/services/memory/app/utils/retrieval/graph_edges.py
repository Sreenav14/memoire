from __future__ import annotations

import json

from sqlalchemy.orm import Session
from sqlalchemy import text

from ..graph.age import GRAPH_NAME, age_setup_sql


def read_edges_meta(
    db: Session,
    *,
    space_id: str,
    edge_keys: list[str],
) -> dict[str, dict]:
    """
    Reads edge metadata (kind, state, confidence, props) from the AGE graph.
    Returns a dict keyed by edge_key.
    """
    if not edge_keys:
        return {}

    db.execute(text(age_setup_sql()))

    cypher = """
    SELECT * FROM cypher(:g, $$
      MATCH ()-[r]->()
      WHERE r.space_id = $space_id AND r.key = ANY($edge_keys)
      RETURN r.key, type(r), COALESCE(r.kind,'explicit'), COALESCE(r.state,'active'),
             COALESCE(r.confidence, 0.7), COALESCE(r.props, {})
    $$, $params) AS (ek agtype, rel agtype, kind agtype, state agtype, conf agtype, props agtype);
    """

    rows = db.execute(
        text(cypher),
        {"g": GRAPH_NAME, "params": {"space_id": space_id, "edge_keys": edge_keys}},
    ).fetchall()

    out: dict[str, dict] = {}
    for ek, rel, kind, state, conf, props in rows:
        ekey = str(ek)
        p = props
        try:
            if isinstance(props, str):
                p = json.loads(props)
        except Exception:
            p = {}

        out[ekey] = {
            "edge_key": ekey,
            "relation": str(rel),
            "kind": str(kind),
            "state": str(state),
            "confidence": float(str(conf)),
            "props": p if isinstance(p, dict) else {},
        }

    return out
