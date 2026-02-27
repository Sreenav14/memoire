from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

GRAPH_NAME = "memory_graph"

def _age_setup_sql() -> str:
    return "LOAD 'age'; SET search_path = ag_catalog, \"$user\", public;"

def edge_keys_from_chunks(db: Session, *, space_id: str, chunk_ids: list[str], limit: int = 50) -> list[str]:
    """ 
    From top chunks, collect edge keys supported by evidence
    """
    
    if not chunk_ids:
        return []
    
    rows = db.execute(
        text(
            """ 
            SELECT DISTINCT edge_key
            WHERE space_id = :space_id 
                AND chunk_id = ANY(:chunk_ids)
                AND edge_key IS NOT NULL
            LIMIT :limit
            """
        ),
        {"space_id": space_id, "chunk_ids": chunk_ids, "limit": limit},
    ).fetchall()
    
    return [str(r[0]) for r in rows]

def entity_seeds_from_edges(
    db:Session,
    *,
    space_id: str,
    edge_keys: list[str],
    limit: int = 30
    ) -> list[str]:
    
    """ 
    for those edges, fetch src and dst entity keys from AGE to create seed nodes.
    """
    
    if not edge_keys:
        return []
    db.execute(text(_age_setup_sql()))
    cypher = """
    SELECT * FROM cypher(:g, $$
        MATCH (a:Entity)-[r]-> (b:Entity)
        WHERE r,space_id = $space_id AND r.key IN $edge_keys
        RETURN DISTINCT a.key, b.key
        LIMIT $limit 
    $$, $params) AS (src agtype, dst agtype);
    """
    params = {"space_id": space_id, "edge_keys": edge_keys, "limit": limit }
    rows = db.execute(text(cypher), {"g": GRAPH_NAME, "params": params}).fetchall()
    
    seeds: list[str] = []
    seen = set()
    for src, dst in rows:
        for k in (str(src), str(dst)):
            if k and k not in seen:
                seen.add(k)
                seeds.append(k)
    return seeds