from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text

from .graph_edges import read_edges_meta


def build_grounded_evidence(
    db: Session,
    *,
    space_id: str,
    graph_edge_keys: list[str],
    limit_total: int = 12,
) -> list[dict]:
    """
    For each edge returned by graph expansion, fetch grounded citations.
    - Explicit edges: cite their own evidence rows directly.
    - Inferred edges: cite evidence from their support_edges (so quotes
      are still real text from real documents, not fabricated).
    """
    if not graph_edge_keys:
        return []

    meta = read_edges_meta(db, space_id=space_id, edge_keys=graph_edge_keys)

    explicit_keys: list[str] = []
    inferred_map: dict[str, list[str]] = {}

    for ek in graph_edge_keys:
        info = meta.get(ek)
        if not info:
            explicit_keys.append(ek)
            continue

        kind = (info.get("kind") or "explicit").lower()
        if kind == "inferred":
            supports = info.get("props", {}).get("support_edges") or []
            if supports:
                inferred_map[ek] = supports
            else:
                explicit_keys.append(ek)
        else:
            explicit_keys.append(ek)

    all_evidence_keys = list(explicit_keys)
    for supports in inferred_map.values():
        all_evidence_keys.extend(supports)
    all_evidence_keys = list(dict.fromkeys(all_evidence_keys))

    if not all_evidence_keys:
        return []

    rows = db.execute(
        text(
            """
            SELECT edge_key, quote, confidence, created_at
            FROM graph_evidence
            WHERE space_id = :space_id
              AND edge_key = ANY(:keys)
            ORDER BY confidence DESC, created_at DESC
            LIMIT :lim
            """
        ),
        {"space_id": space_id, "keys": all_evidence_keys, "lim": limit_total * 3},
    ).fetchall()

    support_to_inferred: dict[str, str] = {}
    for inferred_ek, supports in inferred_map.items():
        for sek in supports:
            support_to_inferred.setdefault(sek, inferred_ek)

    out: list[dict] = []
    for edge_key, quote, conf, created_at in rows:
        ek = str(edge_key)
        cite_for = support_to_inferred.get(ek, ek)
        out.append({
            "edge_key": ek,
            "cite_for": cite_for,
            "quote": (quote or "").strip(),
            "confidence": float(conf),
            "created_at": created_at,
        })

    out.sort(key=lambda x: (-x["confidence"],))
    return out[:limit_total]


def build_graph_context(evidence_rows: list[dict]) -> str:
    lines = []
    counts: dict[str, int] = {}
    for ev in evidence_rows:
        k = ev.get("cite_for") or ev.get("edge_key", "unknown")
        counts[k] = counts.get(k, 0) + 1
        cite_id = f"{k}:{counts[k]}"
        lines.append(f"[{cite_id}] {ev['quote']}")
    return "\n".join(lines)
