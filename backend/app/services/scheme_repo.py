"""Loads the curated scheme dataset and localization tables once at import.

This is the deterministic "knowledge base" from the pitch — kept separate from
the AI layer so policy-compliant matching never depends on an LLM guess.
"""
import json
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache
def load_schemes() -> list[dict]:
    with open(_DATA_DIR / "schemes.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def load_localization() -> dict:
    with open(_DATA_DIR / "localization.json", encoding="utf-8") as f:
        return json.load(f)


def get_scheme(scheme_id: str) -> dict | None:
    return next((s for s in load_schemes() if s["id"] == scheme_id), None)


def localize_document(key: str, language: str) -> dict[str, str]:
    docs = load_localization()["documents"]
    entry = docs.get(key, {})
    label = entry.get(language) or entry.get("en") or key.replace("_", " ").title()
    return {"key": key, "label": label}


def ui_string(name: str, language: str) -> str:
    ui = load_localization()["ui"]
    lang = ui.get(language, ui["en"])
    return lang.get(name, ui["en"].get(name, name))
