"""Read-only access to the scheme knowledge base."""
from fastapi import APIRouter, HTTPException

from ..services.scheme_repo import load_schemes, get_scheme

router = APIRouter(prefix="/api/schemes", tags=["schemes"])


@router.get("")
def list_schemes(category: str | None = None):
    schemes = load_schemes()
    if category:
        schemes = [s for s in schemes if s["category"].lower() == category.lower()]
    # strip the raw rules from the list view; keep it light
    return {
        "count": len(schemes),
        "schemes": [
            {k: s[k] for k in ("id", "name", "ministry", "category", "description", "benefit", "level", "official_link")}
            for s in schemes
        ],
    }


@router.get("/categories")
def list_categories():
    cats = sorted({s["category"] for s in load_schemes()})
    return {"categories": cats}


@router.get("/{scheme_id}")
def scheme_detail(scheme_id: str):
    scheme = get_scheme(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return scheme
