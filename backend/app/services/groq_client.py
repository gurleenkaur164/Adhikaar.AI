"""Thin wrapper around the Groq chat-completions API (Llama 3).

Isolated here so the rest of the app is agnostic to the provider. Returns None
on any failure (no key, network error, bad JSON) so callers can fall back to the
deterministic parser and the platform keeps working at Rs. 0.
"""
import json
import re

from ..config import settings

try:  # optional dependency — app runs fine without it
    from groq import Groq
except Exception:  # pragma: no cover
    Groq = None


def _extract_json(text: str) -> dict | None:
    """Llama sometimes wraps JSON in prose/markdown fences — pull it out."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def chat_json(system_prompt: str, user_prompt: str) -> dict | None:
    if not settings.ai_enabled or Groq is None:
        return None
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        return _extract_json(content)
    except Exception:
        return None
