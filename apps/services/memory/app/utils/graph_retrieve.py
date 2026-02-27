from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

GRAPH_NAME = "memory_graph"

def _age_setup_sql() -> str:
    return "LOAD 'age'; SET search_path = ag_catalog, \"$user\", public;"

def graph_expand(
    db:Session,
    *,
    space_id: str,
    seed_entity_keys: list[str],
    max_hops: int = 2,
    limit: int = 60,
) -> list[dict]:
    """ 
    Graph-first traversal and only active + explicit only edges 
    """
    if not seed_entity_keys:
        return []
    
    db.execute(text(_age_setup_sql()))
    
    cypher = """ 
    SELECT * FROM cypher(:g, $$
    MATCH (s:Entity)
    WHERE s.space_id = $space_id AND s.key IN $seeds
    
    MATCH p =(s) - [r*1..$max_hops]->(t)
    WHERE ALL (e IN r WHERE
        e.space_id = $space_id 
        AND COALESCE(e.state, 'active) = 'active'
        AND COALESCE(e.kind, 'explicit') = 'explicit'
    )
    
    UNWIND r AS e
    RETURN DISTINCT
        e.key,
        type(e),
        COALESCE(e.confidence, 0.7),
        COALESCE(e.state, 'active'),
    LIMIT $limit
    $$, $params) AS (
        edge_key agtype,
        rel agtype,
        confidence agtype,
        kind agtype,
        state agtype,
    );
    """
    
    params = {"space_id": space_id, "seeds": seed_entity_keys, "max_hops": max_hops, "limit": limit}
    rows = db.execute(text(cypher), {"g": GRAPH_NAME, "params": params}).fetchall()
    
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


def evidence_pack(
    db:Session,
    *,
    space_id: str,
    edge_keys: list[str],
    limit_per_edge: int = 3
    ) -> dict[str, list[dict]]:
    """ 
    pull citations for each edges
    """
    
    if not edge_keys:
        return {}
    
    rows = db.execute(
        text(
            """ 
            SELECT edge_key, document_id, chunk_id, quote, char_start, char_end, confidence
            FROM graph_evidence
            WHERE space_id = :space_id
                AND edge_key = ANY(:edge_keys)
            ORDER BY confidence DESC, created_at DESC
            """ 
        ),
        {"space_id": space_id, "edge_keys": edge_keys},
    ).fetchall()
    
    out: dict[str,list[dict]] = {}
    for edge_key, doc_id, chunk_id, quote, cs, ce, conf in rows:
        ek = str(edge_key)
        out.setdefault(ek, [])
        if len(out[ek]) < limit_per_edge:
            out[ek].append({
                "document_id": str(doc_id),
                "chunk_id": str(chunk_id),
                "quote": quote,
                "char_start": int(cs),
                "char_end": int(ce),
                "confidence": float(conf),
            })
    return out