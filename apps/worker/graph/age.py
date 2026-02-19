from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.orm import Session

GRAPH_NAME = "memory_graph"

def _age_setup_sql() -> str:
    return "LOAD 'age; SET search_path = ag_catalog, \"user\", public;"

def upsert_vertex(db:Session, space_id: str, key: str, name:str, etype: str, aliases: list[str] | None = None, props: dict | None = None) -> int:
    aliases = aliases or []
    props = props or {}
    
    db.execute(text(_age_setup_sql()))
    
    #  if we have mapped this key,  return its age id
    row = db.execute(
        text(""" SELECT ag_id FROM graph_vertex_map WHERE space_id = :space_id AND entity_key = :k"""),
        {"space_id": space_id, "k": key},
    ).fetchone()
    if row:
        return int(row[0])
    
    # 2. Create vertex in AGE and capture id
    cypher = f""" 
    SELECT * FROM cypher(
        CREATE (e.Entity{
            space_id: $space_id,
            key: $key,
            name: $name,
            type: $type,
            aliases: $aliases,
            props: $props
        })
        RETURN id(e)
    $$, $params) AS (vid agtype);
    """
    params = {
        "space_id": space_id,
        "key": key,
        "name": name,
        "type": etype,
        "aliases": aliases,
        "props": props,
    }
    
    vid_row = db.execute(text(cypher), {"g": GRAPH_NAME, "params":params}).fetchone()
    vid = int(str(vid_row[0])) # agtype -> string -> int
    
    # 3. store mapping
    db.execute(
        text("""INSERT INTO graph_vertex_map(space_id, entity_key, ag_id) VALUES (:space_id, :k, :ag_id)"""),
        {"space_id": space_id, "k": key, "ag_id": vid},
    )
    db.flush()
    return vid


def upsert_edge(db:Session, space_id: str, ekey:str, src_vid:int, relation: str, dst_vid:int, confidence: float = 0.7, props: dict | None = None) -> int:
    props = props or {} 
    
    db.execute(text(_age_setup_sql()))
    
    row = db.execute(
        text(""" SELECT ag_id FROM graph_edge_map WHERE space_id = :space_id AND edge_key = :k """),
        {"space_id": space_id, "k": ekey},
    ).fetchone()
    if row:
        return int(row[0])
    
    # create edge lable as relation (cleaner for traversal)
    rel_label = relation.strip().replace(" ", "_")
    
    cypher = f""" 
    SELECT * FROM cypher(:g, $$
        MATCH (a), (b)
        WHERE id(a) = $src AND id(b) = $dst
        CREATE (a)-[r:{rel_label} {{space_id: $space_id, key: $ekey, confidence: $conf, props: $props}}]->(b)
        RETURN id(r)
    $$, $params) AS (eid agtype);
    """
    params = {"src": src_vid, "dst":dst_vid, "space_id":space_id,"ekey": ekey,"conf": confidence, "props": props}
    eid_row = db.execute(text(cypher), {"g": GRAPH_NAME, "params":params}).fetchone()
    eid = int(str(eid_row[0]))
    
    db.execute(
        text(""" INSERT INTO graph_edge_map(space_id, edge_key, ag_id) VALUES (:space_id, :k, :ag_id)"""),
        {"space_id": space_id, "k": ekey, "ag_id": eid},
    )
    db.flush()
    return eid