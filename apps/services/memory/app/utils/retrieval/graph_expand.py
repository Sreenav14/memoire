from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..graph.age import GRAPH_NAME, age_setup_sql


def graph_expand(
    db: Session,
    *,
    space_id: str,
    seed_entity_keys: list[str],
    max_hops: int = 2,
    limit: int = 60,
    include_inferred: bool = False,
) -> list[dict]:
    """
    Multi-hop graph traversal starting from seed entities.
    Only traverses active edges.
    When include_inferred=False, only explicit edges are traversed.
    When include_inferred=True, both explicit and inferred edges are included.
    """
    if not seed_entity_keys:
        return []

    db.execute(text(age_setup_sql()))

    kind_filter = (
        ""
        if include_inferred
        else "AND COALESCE(e.kind, 'explicit') = 'explicit'"
    )

    cypher = f"""
    SELECT * FROM cypher(:g, $$
      MATCH (s:Entity)
      WHERE s.space_id = $space_id AND s.key IN $seeds

      MATCH p = (s)-[r*1..2]->(t)
      WHERE ALL(e IN r WHERE
        e.space_id = $space_id
        AND COALESCE(e.state, 'active') = 'active'
        {kind_filter}
      )

      UNWIND r AS e
      RETURN DISTINCT
        e.key,
        type(e),
        COALESCE(e.confidence, 0.7),
        COALESCE(e.kind, 'explicit'),
        COALESCE(e.state, 'active')
      ORDER BY COALESCE(e.confidence, 0.7) DESC
      LIMIT $lim
    $$, $params) AS (
      edge_key agtype,
      rel agtype,
      confidence agtype,
      kind agtype,
      state agtype
    );
    """

    params = {
        "space_id": space_id,
        "seeds": seed_entity_keys,
        "lim": limit,
    }
    rows = db.execute(
        text(cypher), {"g": GRAPH_NAME, "params": params}
    ).fetchall()

    out = []
    for r in rows:
        out.append({
            "edge_key": str(r[0]),
            "relation": str(r[1]),
            "confidence": float(str(r[2])),
            "kind": str(r[3]),
            "state": str(r[4]),
        })
    return out
