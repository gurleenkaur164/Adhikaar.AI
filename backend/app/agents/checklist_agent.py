"""Checklist Agent — turns each matched scheme's document keys into a
localized, de-duplicated checklist the citizen can understand.

Produces both a per-scheme list (localized labels) and a consolidated
"master checklist" across all recommended schemes, so the operator can tell the
citizen exactly what to bring in one trip — tackling the last-mile drop-off.
"""
from ..services.scheme_repo import localize_document, ui_string


def localize_scheme_documents(match: dict, language: str) -> list[dict[str, str]]:
    keys = match.get("_documents_keys", [])
    return [localize_document(k, language) for k in keys]


def build_master_checklist(matches: list[dict], language: str) -> dict:
    """Consolidated unique documents across the recommended (non-ineligible)
    schemes, with which schemes need each document."""
    recommended = [m for m in matches if m["status"] in ("eligible", "likely", "review")]
    doc_to_schemes: dict[str, list[str]] = {}
    order: list[str] = []

    for m in recommended:
        for key in m.get("_documents_keys", []):
            if key not in doc_to_schemes:
                doc_to_schemes[key] = []
                order.append(key)
            doc_to_schemes[key].append(m["name"])

    items = []
    for key in order:
        loc = localize_document(key, language)
        items.append({
            "key": key,
            "label": loc["label"],
            "needed_for": doc_to_schemes[key],
            "count": len(doc_to_schemes[key]),
        })
    # most-reused documents first — those are the "bring these no matter what"
    items.sort(key=lambda x: -x["count"])

    return {
        "title": ui_string("checklist_title", language),
        "language": language,
        "items": items,
        "total_documents": len(items),
    }
