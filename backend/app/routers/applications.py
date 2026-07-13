"""Save & retrieve prepared applications (the human-in-the-loop record)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Application
from ..schemas import ApplicationCreate

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.post("", status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    app = Application(
        citizen_name=payload.citizen_name or (payload.profile or {}).get("name"),
        raw_input=payload.raw_input,
        profile=payload.profile,
        matched_schemes=payload.matched_schemes,
        language=payload.language,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app.to_dict()


@router.get("")
def list_applications(db: Session = Depends(get_db)):
    apps = db.query(Application).order_by(Application.created_at.desc()).all()
    return {"count": len(apps), "applications": [a.to_dict() for a in apps]}


@router.get("/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db)):
    app = db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app.to_dict()
