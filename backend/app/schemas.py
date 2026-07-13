"""Pydantic request/response models."""
from typing import Any, Optional

from pydantic import BaseModel, Field


class CitizenProfile(BaseModel):
    """Structured citizen profile — the output of the extraction agent and the
    input to the eligibility agent. Every field is optional because rural
    intake is incremental and messy."""
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None                 # male | female | other
    annual_income: Optional[int] = None          # in rupees
    occupation: Optional[str] = None             # normalised keyword
    category: Optional[str] = None               # general | obc | sc | st
    state: Optional[str] = None
    area: Optional[str] = None                    # rural | urban
    is_bpl: Optional[bool] = None
    disability_percent: Optional[int] = None
    marital_status: Optional[str] = None          # single | married | widow
    is_student: Optional[bool] = None
    land_holding_acres: Optional[float] = None
    is_pregnant: Optional[bool] = None
    num_children: Optional[int] = None
    flags: list[str] = Field(default_factory=list)  # extra custom flags


class ExtractRequest(BaseModel):
    text: str = Field(..., description="Operator's free-text description of the citizen")
    language: str = "en"


class ExtractResponse(BaseModel):
    profile: CitizenProfile
    source: str                 # "groq" | "rule-based"
    confidence: float
    missing_fields: list[str]


class MatchRequest(BaseModel):
    profile: CitizenProfile
    language: str = "en"


class SchemeMatch(BaseModel):
    scheme_id: str
    name: str
    category: str
    benefit: str
    status: str                 # eligible | likely | not_eligible
    score: float
    matched_criteria: list[str]
    failed_criteria: list[str]
    documents: list[dict[str, str]]     # localized {key, label}
    official_link: str


class MatchResponse(BaseModel):
    matches: list[SchemeMatch]
    summary: dict[str, Any]


class ProcessRequest(BaseModel):
    """One-shot: raw text -> profile -> matches -> checklist."""
    text: str
    language: str = "en"


class ApplicationCreate(BaseModel):
    citizen_name: Optional[str] = None
    raw_input: str
    profile: dict
    matched_schemes: list[dict]
    language: str = "en"
