"""ORM models. A saved 'Application' is the human-in-the-loop record an
operator prepares for a citizen — the extracted profile plus the matched
schemes and generated checklist."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, JSON

from .database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    citizen_name = Column(String, index=True)
    operator_id = Column(String, index=True, default="csc-operator")
    raw_input = Column(String)                 # original operator text
    profile = Column(JSON)                     # structured citizen profile
    matched_schemes = Column(JSON)             # list of match result dicts
    language = Column(String, default="en")
    status = Column(String, default="draft")   # draft | submitted
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "citizen_name": self.citizen_name,
            "operator_id": self.operator_id,
            "raw_input": self.raw_input,
            "profile": self.profile,
            "matched_schemes": self.matched_schemes,
            "language": self.language,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
