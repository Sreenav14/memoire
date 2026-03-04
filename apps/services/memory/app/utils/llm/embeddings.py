from __future__ import annotations

import os
from typing import List

EMBEDDING_DIM = 1536
MODEL = "text-embedding-3-small"

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=key)
    return _client


def embed_text(text: str) -> List[float]:
    """Convert text to embeddings using OpenAI API."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Text is required")

    response = _get_client().embeddings.create(
        model=MODEL,
        input=text[:8000],
    )
    vector = response.data[0].embedding

    if len(vector) != EMBEDDING_DIM:
        raise ValueError(f"Expected {EMBEDDING_DIM} dimensions, got {len(vector)}")

    return vector
