from __future__ import annotations

import os
import random
import time
from typing import Optional

from openai import OpenAI
from groq import Groq

# Keep clients here (single init)
_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
DEFAULT_GROQ_MODEL = os.getenv("GROQ_CHAT_MODEL", "llama-3.1-8b-instant")

# Simple timeouts (seconds)
OPENAI_TIMEOUT_S = float(os.getenv("OPENAI_TIMEOUT_S", "30"))
GROQ_TIMEOUT_S = float(os.getenv("GROQ_TIMEOUT_S", "30"))

# Retry config
MAX_ATTEMPTS = int(os.getenv("LLM_MAX_ATTEMPTS", "5"))


def _sleep_backoff(attempt: int) -> None:
    # exponential backoff with jitter
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
    """
    Single gateway for all providers.
    - Central place for retries/backoff/timeouts.
    - Later: add provider == "bedrock" here without changing routers.
    """
    provider = (provider or "").lower().strip()

    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set")

        use_model = model or DEFAULT_OPENAI_MODEL

        last_err: Optional[Exception] = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = _openai.chat.completions.create(
                    model=use_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens,
                    timeout=OPENAI_TIMEOUT_S,  # important
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                last_err = e
                # In v1 we retry with backoff for transient failures.
                # If you want stricter behavior later, we can narrow to known retryable codes.
                if attempt < MAX_ATTEMPTS - 1:
                    _sleep_backoff(attempt)
                    continue
                raise RuntimeError(f"OpenAI chat failed after {MAX_ATTEMPTS} attempts: {e}") from e

        raise RuntimeError(f"OpenAI chat failed: {last_err}")

    if provider == "groq":
        if not os.getenv("GROQ_API_KEY"):
            raise RuntimeError("GROQ_API_KEY is not set")

        use_model = model or DEFAULT_GROQ_MODEL

        last_err: Optional[Exception] = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = _groq.chat.completions.create(
                    model=use_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens,
                    timeout=GROQ_TIMEOUT_S,  # important
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                last_err = e
                if attempt < MAX_ATTEMPTS - 1:
                    _sleep_backoff(attempt)
                    continue
                raise RuntimeError(f"Groq chat failed after {MAX_ATTEMPTS} attempts: {e}") from e

        raise RuntimeError(f"Groq chat failed: {last_err}")

    # Future:
    # if provider == "bedrock":
    #     return bedrock_chat_completion(...)

    raise RuntimeError(f"Invalid provider: {provider}")