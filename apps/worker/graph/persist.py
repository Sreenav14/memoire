from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import text

from .age import upsert_vertex, upsert_edge
from .key import entity_key, edge_key


def write_entity_evidence(
    db: Session,
    space_id: str,
    document_id: str,
    chunk_id: str,
    ekey: str,
    quote: str,
    qs: int,
    qe: int,
    conf: float,
):
    db.execute(
        text("""
            INSERT INTO graph_evidence(space_id, entity_key, document_id, chunk_id, quote, char_start, char_end, confidence)
            VALUES (:space_id, :entity_key, :doc, :chunk, :quote, :cs, :ce, :conf)
        """),
        {
            "space_id": space_id,
            "entity_key": ekey,
            "doc": document_id,
            "chunk": chunk_id,
            "quote": quote,
            "cs": qs,
            "ce": qe,
            "conf": conf,
        },
    )


def write_edge_evidence(
    db: Session,
    space_id: str,
    document_id: str,
    chunk_id: str,
    ekey: str,
    quote: str,
    qs: int,
    qe: int,
    conf: float,
):
    db.execute(
        text("""
            INSERT INTO graph_evidence(space_id, edge_key, document_id, chunk_id, quote, char_start, char_end, confidence)
            VALUES (:space_id, :edge_key, :doc, :chunk, :quote, :cs, :ce, :conf)
        """),
        {
            "space_id": space_id,
            "edge_key": ekey,
            "doc": document_id,
            "chunk": chunk_id,
            "quote": quote,
            "cs": qs,
            "ce": qe,
            "conf": conf,
        },
    )


def persist_chunk_graph(
    db: Session,
    space_id: str,
    document_id: str,
    chunk_id: str,
    chunk_text: str,
    extraction: dict,
):
    # 1) Build accepted entities (once)
    accepted: dict[str, dict] = {}
    for e in extraction.get("entities", []):
        if not e.get("accepted"):
            continue

        etype = (e.get("type") or "concept").lower().strip()
        cname = (e.get("canonical_name") or e.get("candidate_text") or "").strip()
        if not cname:
            continue

        k = entity_key(etype, cname)
        accepted[cname] = {
            "key": k,
            "type": etype,
            "name": cname,
            "aliases": e.get("aliases") or [],
        }

    if not accepted:
        return

    # 2) Upsert vertices (once)
    name_to_vid: dict[str, int] = {}
    for cname, meta in accepted.items():
        vid = upsert_vertex(
            db=db,
            space_id=space_id,
            key=meta["key"],
            name=meta["name"],
            etype=meta["type"],
            aliases=meta["aliases"],
            props={},
        )
        name_to_vid[cname] = vid

    # 3) Upsert edges + write evidence
    for r in extraction.get("relations", []):
        src = r.get("src")
        dst = r.get("dst")
        rel = r.get("relation")

        if not src or not dst or not rel:
            continue
        if src not in name_to_vid or dst not in name_to_vid:
            continue

        skey = accepted[src]["key"]
        dkey = accepted[dst]["key"]
        ek = edge_key(skey, rel, dkey)

        upsert_edge(
            db=db,
            space_id=space_id,
            ekey=ek,
            src_vid=name_to_vid[src],
            relation=rel,
            dst_vid=name_to_vid[dst],
            confidence=float(r.get("confidence", 0.7)),
            props={},
        )

        qs = int(r.get("quote_start", 0))
        qe = int(r.get("quote_end", 0))
        qs = max(0, min(qs, len(chunk_text)))
        qe = max(qs, min(qe, len(chunk_text)))

        quote = chunk_text[qs:qe].strip()
        if not quote:
            quote = chunk_text[max(0, qs - 40) : min(len(chunk_text), qe + 40)].strip()

        write_edge_evidence(
            db=db,
            space_id=space_id,
            document_id=document_id,
            chunk_id=chunk_id,
            ekey=ek,
            quote=quote,
            qs=qs,
            qe=qe,
            conf=float(r.get("confidence", 0.7)),
        )

    # Let the caller (worker) commit once per document
    db.flush()
