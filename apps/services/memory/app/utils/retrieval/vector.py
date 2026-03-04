from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from ..llm.embeddings import embed_text


def vector_recall_chunks(
    db: Session,
    *,
    space_id: str,
    question: str,
    top_k: int = 12,
) -> list[dict]:
    """Fast semantic recall using pgvector. Returns top-k chunks with similarity scores."""
    qvec = embed_text(question)

    rows = db.execute(
        sql_text(
            """
            SELECT
                c.id AS chunk_id,
                c.text,
                d.source_type,
                (c.embeddings <-> :qvec) AS distance
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.space_id = :space_id
            ORDER BY (c.embeddings <-> :qvec)
            LIMIT :limit
            """
        ),
        {"qvec": qvec, "space_id": space_id, "limit": top_k},
    ).fetchall()

    results = []
    for r in rows:
        distance = float(r.distance)
        base_score = 1.0 / (1.0 + distance)

        weight = 1.0
        if r.source_type == "chat":
            weight = 0.85
        elif r.source_type == "profile":
            weight = 0.9

        final_score = base_score * weight

        results.append({
            "chunk_id": str(r.chunk_id),
            "text": r.text,
            "score": final_score,
            "source_type": r.source_type,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
