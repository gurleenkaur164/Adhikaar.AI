"""Core AI pipeline endpoints: extract, match, and the one-shot process."""
from fastapi import APIRouter

from ..agents import eligibility_agent, extraction_agent, checklist_agent
from ..agents.orchestrator import run_pipeline
from ..schemas import (
    ExtractRequest, ExtractResponse,
    MatchRequest, MatchResponse,
    ProcessRequest,
)

router = APIRouter(prefix="/api", tags=["pipeline"])


@router.post("/extract", response_model=ExtractResponse)
def extract(req: ExtractRequest):
    """Conversational Data Entry: free text -> structured citizen profile."""
    profile, source, confidence = extraction_agent.extract_profile(req.text)
    return ExtractResponse(
        profile=profile,
        source=source,
        confidence=confidence,
        missing_fields=extraction_agent.missing_fields(profile),
    )


@router.post("/match", response_model=MatchResponse)
def match(req: MatchRequest):
    """Instant Scheme Matching: profile -> ranked eligible schemes + docs."""
    results = eligibility_agent.match_all(req.profile, include_ineligible=True)
    for m in results:
        m["documents"] = checklist_agent.localize_scheme_documents(m, req.language)
        m.pop("_documents_keys", None)
    summary = {
        "total": len(results),
        "eligible": len([m for m in results if m["status"] == "eligible"]),
        "likely": len([m for m in results if m["status"] in ("likely", "review")]),
    }
    return MatchResponse(matches=results, summary=summary)


@router.post("/process")
def process(req: ProcessRequest):
    """Full agentic run: text -> profile -> matches -> localized checklist.

    Returns the profile, ranked matches, master document checklist, a synthesis
    summary and the agent trace (for the operator to see how it decided)."""
    return run_pipeline(req.text, language=req.language)
