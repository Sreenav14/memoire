from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text

from ..graph.age import GRAPH_NAME, _age_setup_sql, upsert_vertex, upsert_edge
from ..graph.key import edge_key as make_edge_key
from .consolidate import insert_memory_event


def run_inference_rules(
    db: Session,
    *,
    space_id: str,
    per_rule_limit: int = 1500,
) -> dict:
    """
    Generic inference runner:
    - Loads enabled rules from inference_rules
    - Executes each rule as a bounded Cypher query
    - Writes inferred edges with provenance (support_edges)
    - Uses only explicit + active edges as supports
    - Avoids infinite duplicates by relying on graph_edge_map uniqueness
    """
    db.execute(text(_age_setup_sql()))

    rules = db.execute(
        text(
            """
            SELECT name, rule_json
            FROM inference_rules
            WHERE space_id = :space_id
              AND is_enabled = true
            ORDER BY name ASC
            """
        ),
        {"space_id": space_id},
    ).fetchall()

    inferred_created = 0
    rules_used = 0

    for name, rule_json in rules:
        rule = rule_json if isinstance(rule_json, dict) else {}
        pattern = rule.get("pattern") or []
        infer = rule.get("infer") or {}

        rel_out = infer.get("rel")
        if not pattern or not infer or not rel_out:
            continue

        confidence = float(rule.get("confidence") or 0.55)

        match_parts: list[str] = []
        where_parts: list[str] = []
        return_parts: list[str] = []

        for i, p in enumerate(pattern):
            frm = p["from"]
            to = p["to"]
            rel = p["rel"]
            rvar = f"r{i}"

            match_parts.append(f"(n{frm})-[{rvar}:{rel}]->(n{to})")

            where_parts.append(f"{rvar}.space_id = $space_id")
            where_parts.append(f"COALESCE({rvar}.state,'active') = 'active'")
            where_parts.append(f"COALESCE({rvar}.kind,'explicit') = 'explicit'")

            return_parts.append(f"{rvar}.key")

        src_var = infer["from"]
        dst_var = infer["to"]

        cypher = f"""
        SELECT * FROM cypher(:g, $$
          MATCH {", ".join(match_parts)}
          WHERE {" AND ".join(where_parts)}
          RETURN n{src_var}.key, n{dst_var}.key, {", ".join(return_parts)}
          LIMIT $lim
        $$, $params) AS (
          src agtype,
          dst agtype,
          {", ".join([f"s{i} agtype" for i in range(len(pattern))])}
        );
        """

        rows = db.execute(
            text(cypher),
            {"g": GRAPH_NAME, "params": {"space_id": space_id, "lim": per_rule_limit}},
        ).fetchall()

        if not rows:
            continue

        rules_used += 1

        for r in rows:
            src = str(r[0])
            dst = str(r[1])
            support_edges = [str(r[2 + i]) for i in range(len(pattern))]

            ekey = make_edge_key(src, rel_out, dst)

            src_vid = upsert_vertex(db, space_id, src, src, "Entity")
            dst_vid = upsert_vertex(db, space_id, dst, dst, "Entity")

            existed = db.execute(
                text(
                    """
                    SELECT 1
                    FROM graph_edge_map
                    WHERE space_id = :space_id AND edge_key = :ekey
                    LIMIT 1
                    """
                ),
                {"space_id": space_id, "ekey": ekey},
            ).fetchone()

            upsert_edge(
                db,
                space_id=space_id,
                ekey=ekey,
                src_vid=src_vid,
                relation=rel_out,
                dst_vid=dst_vid,
                confidence=confidence,
                props={
                    "rule": name,
                    "support_edges": support_edges,
                },
                kind="inferred",
                state="active",
            )

            if not existed:
                insert_memory_event(
                    db,
                    space_id=space_id,
                    event_type="merge",
                    target_edge_key=support_edges[0] if support_edges else None,
                    new_edge_key=ekey,
                    reason=f"inferred via rule {name} supports={support_edges}",
                    created_by_doc_id=None,
                )
                inferred_created += 1

    db.commit()
    return {"rules_used": rules_used, "inferred_edges_created": inferred_created}
