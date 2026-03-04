from __future__ import annotations

import logging
import os
import random
import time
from typing import Optional

log = logging.getLogger("memoire.llm.gateway")

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
DEFAULT_GROQ_MODEL = os.getenv("GROQ_CHAT_MODEL", "llama-3.1-8b-instant")

OPENAI_TIMEOUT_S = float(os.getenv("OPENAI_TIMEOUT_S", "30"))
GROQ_TIMEOUT_S = float(os.getenv("GROQ_TIMEOUT_S", "30"))

MAX_ATTEMPTS = int(os.getenv("LLM_MAX_ATTEMPTS", "5"))

_openai_client = None
_groq_client = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _openai_client = OpenAI(api_key=key)
    return _openai_client


def _get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _groq_client = Groq(api_key=key)
    return _groq_client


def _sleep_backoff(attempt: int) -> None:
    base = min(8.0, 0.5 * (2 ** attempt))
    time.sleep(base + random.random() * 0.25)


def chat_completion(
    *,
    provider: str,
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    max_tokens: int = 800,
) -> str:
    """Single gateway for all LLM providers with retries, backoff, and timeouts."""
    provider = (provider or "").lower().strip()

    if provider == "openai":
        client = _get_openai()
        use_model = model or DEFAULT_OPENAI_MODEL

        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = client.chat.completions.create(
                    model=use_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens,
                    timeout=OPENAI_TIMEOUT_S,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                log.warning("OpenAI attempt %d/%d failed: %s", attempt + 1, MAX_ATTEMPTS, str(e)[:200])
                if attempt < MAX_ATTEMPTS - 1:
                    _sleep_backoff(attempt)
                    continue
                raise RuntimeError(f"OpenAI chat failed after {MAX_ATTEMPTS} attempts: {e}") from e

    elif provider == "groq":
        client = _get_groq()
        use_model = model or DEFAULT_GROQ_MODEL

        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = client.chat.completions.create(
                    model=use_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens,
                    timeout=GROQ_TIMEOUT_S,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                log.warning("Groq attempt %d/%d failed: %s", attempt + 1, MAX_ATTEMPTS, str(e)[:200])
                if attempt < MAX_ATTEMPTS - 1:
                    _sleep_backoff(attempt)
                    continue
                raise RuntimeError(f"Groq chat failed after {MAX_ATTEMPTS} attempts: {e}") from e

    else:
        raise RuntimeError(f"Invalid LLM provider: '{provider}'. Use 'openai' or 'groq'.")

    raise RuntimeError("Unreachable")
