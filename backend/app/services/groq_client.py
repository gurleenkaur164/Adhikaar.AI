"""Thin wrapper around the Groq chat-completions API (Llama 3).

Isolated here so the rest of the app is agnostic to the provider. Returns None
on any failure (no key, network error, bad JSON) so callers can fall back to the
deterministic parser and the platform keeps working at Rs. 0.
"""
import json
import logging
import random
import re
import time

from ..config import settings

log = logging.getLogger(__name__)

try:  # optional dependency — app runs fine without it
    from groq import Groq
except Exception:  # pragma: no cover
    Groq = None

_MAX_ATTEMPTS = 3
_BACKOFF_BASE = 0.4  # seconds


def _extract_json(text: str) -> dict | None:
    """Llama sometimes wraps JSON in prose/markdown fences — pull it out."""
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    # Fall back to the outermost {...} span. Non-greedy would stop at the first
    # nested closing brace, so this stays greedy on purpose.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _client() -> "Groq | None":
    if not settings.ai_enabled or Groq is None:
        return None
    try:
        return Groq(api_key=settings.GROQ_API_KEY)
    except Exception:  # pragma: no cover — bad key format etc.
        log.warning("Groq client could not be constructed", exc_info=True)
        return None


def chat_json(system_prompt: str, user_prompt: str) -> dict | None:
    """Ask the model for a JSON object. Returns None if it cannot be obtained.

    Retries transient failures with jittered backoff. A single dropped packet
    used to silently demote the whole request to the weaker rule-based parser
    with nothing logged — the operator saw a thinner profile and no explanation.
    Failures are now logged so a degraded AI path is visible rather than
    invisible; callers still get None and still fall back, so the Rs. 0
    guarantee is unchanged.
    """
    client = _client()
    if client is None:
        return None

    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            completion = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            data = _extract_json(completion.choices[0].message.content)
            if data is not None:
                return data
            last_error = ValueError("model returned no parseable JSON object")
        except Exception as exc:  # network, rate limit, 5xx, malformed response
            last_error = exc

        if attempt < _MAX_ATTEMPTS:
            time.sleep(_BACKOFF_BASE * (2 ** (attempt - 1)) + random.uniform(0, 0.2))

    log.warning(
        "Groq extraction failed after %d attempts (%s); falling back to the "
        "rule-based parser.", _MAX_ATTEMPTS, last_error,
    )
    return None
