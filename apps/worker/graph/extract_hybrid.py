from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any

try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
except Exception:
    _NLP = None
    
from ..llm_client import call_llm_json

@dataclass
class Candidate:
    text: str
    start: int
    end: int
    label: str
    

def ner_candidate(text: str) -> list[Candidate]:
    if not text:
        return []
    
    if _NLP is None:
        out = []
        import re
        for m in re.finditer(fr"\b([A-Z][a-zA-Z0-9&\-/]+(?:\s+[A-Z][a-zA-Z0-9&\-/]+){0,4})\b", text):
            out.append(Candidate(m.group(1), m.start(1), m.end(1), "MISC"))
        return out[:80]
    
    doc = _NLP(text)
    out = []
    for ent in doc.ents:
        out.append(Candidate(ent.text, ent.start_char, ent.end_char, ent.label_))
    return out[:120]

LLM_SCHEMA = {
  "type": "object",
  "properties": {
    "entities": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "candidate_text": {"type": "string"},
          "accepted": {"type": "boolean"},
          "type": {"type": "string"},
          "canonical_name": {"type": "string"},
          "aliases": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["candidate_text", "accepted"]
      }
    },
    "relations": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "src": {"type": "string"},
          "relation": {"type": "string"},
          "dst": {"type": "string"},
          "confidence": {"type": "number"},
          "quote_start": {"type": "integer"},
          "quote_end": {"type": "integer"}
        },
        "required": ["src","relation","dst","confidence","quote_start","quote_end"]
      }
    }
  },
  "required": ["entities","relations"]
}

def extract_hybrid(chunk_text: str) -> dict[str, Any]:
    cands = ner_candidate(chunk_text)
    cand_list = [{"text": c.text, "start": c.start, "end": c.end, "label": c.label} for c in cands]

    system = (
      "You are a strict information extraction verifier.\n"
      "Only use the candidate entities provided.\n"
      "Return STRICT JSON matching the schema.\n"
      "Relations must be supported by a direct quote span in the chunk text.\n"
      "Do not invent entities."
    )

    user = {
      "chunk_text": chunk_text,
      "candidates": cand_list,
      "instructions": [
        "Accept or reject each candidate.",
        "For accepted ones, provide canonical_name, type, aliases.",
        "Extract relations ONLY between accepted entities.",
        "For each relation, give quote_start/quote_end (character offsets) covering the evidence in chunk_text."
      ],
      "schema": LLM_SCHEMA
    }

    return call_llm_json(system_prompt=system, user_payload=user, schema=LLM_SCHEMA)