"""Agentic Orchestrator.

Mirrors the CrewAI-style workflow from the pitch as an explicit, auditable
pipeline (no heavyweight dependency, deterministic ordering):

    Intake -> Extraction -> Eligibility -> Checklist -> Synthesis

Each stage is a pure function over the previous stage's output, which makes the
whole flow easy to log, test and reason about — important for a government
service where every decision must be traceable.
"""
from ..schemas import CitizenProfile
from . import checklist_agent, eligibility_agent, extraction_agent


def run_pipeline(text: str, language: str = "en", include_ineligible: bool = False) -> dict:
    trace: list[dict] = []

    # 1. Intake
    trace.append({"agent": "Intake", "detail": f"Received {len(text)} chars of operator input"})

    # 2. Extraction (AI or rule-based)
    profile, source, confidence = extraction_agent.extract_profile(text)
    missing = extraction_agent.missing_fields(profile)
    trace.append({
        "agent": "Extraction",
        "detail": f"Structured profile built via {source} (confidence {confidence})",
        "source": source,
        "missing_fields": missing,
    })

    # 3. Eligibility (deterministic)
    matches = eligibility_agent.match_all(profile, include_ineligible=include_ineligible)
    eligible = [m for m in matches if m["status"] == "eligible"]
    trace.append({
        "agent": "Eligibility",
        "detail": f"Matched {len(matches)} schemes ({len(eligible)} fully eligible) against the rule base",
    })

    # 4. Checklist (localized). Build the consolidated master list first (it
    # needs the raw document keys), then localize + strip keys per scheme.
    checklist = checklist_agent.build_master_checklist(matches, language)
    for m in matches:
        m["documents"] = checklist_agent.localize_scheme_documents(m, language)
        m.pop("_documents_keys", None)
    trace.append({
        "agent": "Checklist",
        "detail": f"Generated a {checklist['total_documents']}-document localized checklist ({language})",
    })

    # 5. Synthesis
    summary = {
        "citizen_name": profile.name,
        "total_matches": len(matches),
        "eligible": len([m for m in matches if m["status"] == "eligible"]),
        "likely": len([m for m in matches if m["status"] in ("likely", "review")]),
        "extraction_source": source,
        "confidence": confidence,
        "missing_fields": missing,
        "top_schemes": [m["name"] for m in matches[:3]],
    }
    trace.append({"agent": "Synthesis", "detail": "Compiled operator-ready application summary"})

    return {
        "profile": profile.model_dump(),
        "matches": matches,
        "checklist": checklist,
        "summary": summary,
        "trace": trace,
        "language": language,
    }
