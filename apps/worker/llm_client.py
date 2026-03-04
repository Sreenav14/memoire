from __future__ import annotations

import json
import os
from typing import Any

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "stub").lower()


def call_llm_json(system_prompt: str, user_payload: dict, schema: dict | None = None, **kwargs) -> dict:
    """
    Provider-agnostic JSON LLM call.
    - stub: returns static empty response (for dev/testing)
    - bedrock: planned for production
    """
    if LLM_PROVIDER == "stub":
        return {"entities": [], "relations": []}

    if LLM_PROVIDER == "bedrock":
        raise NotImplementedError("Bedrock support not implemented yet")

    raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")


def call_openai_chat(model: str, system_prompt: str, user_prompt: str) -> str:
    """Direct OpenAI chat call for rule generation and other non-extraction tasks."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    return resp.choices[0].message.content or ""
