from __future__ import annotations

import json
import re
import logging

from ..llm_client import call_openai_chat

log = logging.getLogger("memoire.worker.rules")

PROMPT = """
You are designing reasoning rules for a knowledge graph.

Relations available:
{relations}

Suggest 5 useful 2-hop inference rules.

Return JSON:

{{
 "rules":[
  {{
   "name":"rule_name",
   "pattern":[
     {{"from":"A","rel":"REL1","to":"B"}},
     {{"from":"B","rel":"REL2","to":"C"}}
   ],
   "infer":{{"from":"A","rel":"NEW_REL","to":"C"}},
   "confidence":0.55
  }}
 ]
}}
"""


def _extract_json(text: str) -> dict:
    """Try to parse JSON from LLM output, handling markdown code fences."""
    text = text.strip()

    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    return json.loads(text)


def generate_rules(relations: list[str]) -> dict:
    prompt = PROMPT.format(relations=", ".join(relations))

    response = call_openai_chat(
        "gpt-4o-mini",
        "You are an expert in knowledge graph reasoning. Return only valid JSON.",
        prompt,
    )

    try:
        return _extract_json(response)
    except (json.JSONDecodeError, ValueError) as e:
        log.warning("Failed to parse rule generation response: %s", str(e)[:200])
        return {"rules": []}
