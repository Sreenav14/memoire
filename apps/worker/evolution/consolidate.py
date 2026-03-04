from __future__ import annotations

import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text, select

from ..graph.age import GRAPH_NAME, _age_setup_sql


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def set_edge_state(
    db: Session,
    *,
    space_id: str,
    edge_key: str,
    state: str,
    valid_from: str | None = None,
    valid_to: str | None = None,
    supersedes_edge_key: str | None = None,
    updated_by_doc_id: str | None = None,
) -> None:
    """Update AGE edge properties by edge_key."""
    db.execute(text(_age_setup_sql()))
    cypher = """
    SELECT * FROM cypher(:g, $$
        MATCH ()-[r]->()
        WHERE r.space_id = $space_id AND r.key = $edge_key
        SET r.state = $state,
        r.valid_from = COALESCE($valid_from, r.valid_from),
        r.valid_to = COALESCE($valid_to, r.valid_to),
        r.supersedes_edge_key = COALESCE($supersedes_edge_key, r.supersedes_edge_key),
        r.updated_by_doc_id = COALESCE($updated_by_doc_id, r.updated_by_doc_id)
        RETURN 1
    $$, $params) AS (x agtype);
    """
    params = {
        "space_id": space_id,
        "edge_key": edge_key,
        "state": state,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "supersedes_edge_key": supersedes_edge_key,
        "updated_by_doc_id": updated_by_doc_id,
    }
    db.execute(text(cypher), {"g": GRAPH_NAME, "params": params})


def insert_memory_event(
    db: Session,
    *,
    space_id: str,
    event_type: str,
    target_edge_key: str | None = None,
    new_edge_key: str | None = None,
    reason: str | None = None,
    created_by_doc_id: str | None = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO memory_events(space_id, event_type, target_edge_key, new_edge_key, reason, created_by_doc_id)
            VALUES (:space_id, :event_type, :target_edge_key, :new_edge_key, :reason, :created_by_doc_id)
            """
        ),
        {
            "space_id": space_id,
            "event_type": event_type,
            "target_edge_key": target_edge_key,
            "new_edge_key": new_edge_key,
            "reason": reason,
            "created_by_doc_id": created_by_doc_id,
        },
    )


def fetch_new_edge_keys_for_docs(db: Session, *, space_id: str, document_id: str) -> list[str]:
    """Uses evidence table as the source of truth."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT edge_key
            FROM graph_evidence
            WHERE space_id = :space_id AND document_id = :document_id AND edge_key IS NOT NULL
            """
        ),
        {"space_id": space_id, "document_id": document_id},
    ).fetchall()
    return [r[0] for r in rows]


def fetch_edge_triple(db: Session, *, space_id: str, edge_key: str) -> tuple[str, str, str, float] | None:
    """Return (src_key, relation, dst_key, confidence) from AGE edge."""
    db.execute(text(_age_setup_sql()))
    cypher = """
    SELECT * FROM cypher(:g, $$
        MATCH (a)-[r]->(b)
        WHERE r.space_id = $space_id AND r.key = $edge_key
        RETURN a.key, type(r), b.key, r.confidence
    $$, $params) AS (src agtype, rel agtype, dst agtype, confidence agtype);
    """
    params = {"space_id": space_id, "edge_key": edge_key}
    row = db.execute(text(cypher), {"g": GRAPH_NAME, "params": params}).fetchone()
    if not row:
        return None
    return str(row[0]), str(row[1]), str(row[2]), float(str(row[3]))


def find_competing_edges(db: Session, *, space_id: str, src_key: str, relation: str, exclude_edge_key: str) -> list[str]:
    """Find other edges with same (src, relation) in same space."""
    db.execute(text(_age_setup_sql()))
    cypher = """
    SELECT * FROM cypher(:g, $$
        MATCH (a)-[r]->(b)
        WHERE r.space_id = $space_id AND a.key = $src_key AND type(r) = $rel AND r.key <> $exclude
        RETURN r.key
    $$, $params) AS (ekey agtype);
    """
    params = {"space_id": space_id, "src_key": src_key, "rel": relation, "exclude": exclude_edge_key}
    rows = db.execute(text(cypher), {"g": GRAPH_NAME, "params": params}).fetchall()
    return [str(r[0]) for r in rows]


ATTRIBUTE_RELATIONS = {
    "uses",
    "has_skill",
    "likes",
    "working_on",
    "located_in",
    "has",
    "owns",
}


def consolidate_document(db: Session, *, space_id: str, document_id: str) -> None:
    now = _now_iso()
    new_edge_keys = fetch_new_edge_keys_for_docs(db, space_id=space_id, document_id=document_id)

    for new_ek in new_edge_keys:
        triple = fetch_edge_triple(db, space_id=space_id, edge_key=new_ek)
        if not triple:
            continue
        src_key, relation, dst_key, new_conf = triple

        competitors = find_competing_edges(
            db,
            space_id=space_id,
            src_key=src_key,
            relation=relation,
            exclude_edge_key=new_ek,
        )

        if not competitors:
            set_edge_state(db, space_id=space_id, edge_key=new_ek, state="active", valid_from=now, updated_by_doc_id=document_id)
            continue

        if relation.lower() in ATTRIBUTE_RELATIONS:
            set_edge_state(db, space_id=space_id, edge_key=new_ek, state="active", valid_from=now, updated_by_doc_id=document_id)
            continue

        updated_any = False
        for old_ek in competitors:
            old_triple = fetch_edge_triple(db, space_id=space_id, edge_key=old_ek)
            if not old_triple:
                continue
            _, _, old_dst, old_conf = old_triple

            if old_dst == dst_key:
                set_edge_state(db, space_id=space_id, edge_key=new_ek, state="active", valid_from=now, updated_by_doc_id=document_id)
                updated_any = True
                continue

            if new_conf >= old_conf:
                set_edge_state(db, space_id=space_id, edge_key=old_ek, state="deprecated", valid_to=now, updated_by_doc_id=document_id)
                set_edge_state(db, space_id=space_id, edge_key=new_ek, state="active", valid_from=now, supersedes_edge_key=old_ek, updated_by_doc_id=document_id)
                insert_memory_event(
                    db,
                    space_id=space_id,
                    event_type="update",
                    target_edge_key=old_ek,
                    new_edge_key=new_ek,
                    reason=f"new edge with ({new_conf}) >= old_conf ({old_conf}) for same (src, rel)",
                    created_by_doc_id=document_id,
                )
                updated_any = True
            else:
                set_edge_state(db, space_id=space_id, edge_key=old_ek, state="disputed", updated_by_doc_id=document_id)
                set_edge_state(db, space_id=space_id, edge_key=new_ek, state="disputed", valid_from=now, updated_by_doc_id=document_id)
                insert_memory_event(
                    db,
                    space_id=space_id,
                    event_type="contradict",
                    target_edge_key=old_ek,
                    new_edge_key=new_ek,
                    reason=f"new edge with ({new_conf}) < old_conf ({old_conf}) for same (src, rel)",
                    created_by_doc_id=document_id,
                )
            updated_any = True

        if not updated_any:
            set_edge_state(db, space_id=space_id, edge_key=new_ek, state="active", valid_from=now, updated_by_doc_id=document_id)

    db.commit()
