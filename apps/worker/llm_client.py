from __future__ import annotations
import json
import os
from typing import Any, Dict

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "stub").lower()


def call_llm_json(system_prompt: str, user_payload: dict, schema:dict | None = None, **kwargs) -> dict:
    """
    
    Provider-agnostic JSON LLM call
    -stub: returns static JSON response
    -bedrock: later
    """ 
    
    if LLM_PROVIDER == "stub":
        return {"entities": [], "relations": []}

    if LLM_PROVIDER == "bedrock":
        raise NotImplementedError("Bedrock support not implemented yet")
    
    raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")