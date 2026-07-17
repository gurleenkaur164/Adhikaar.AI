"""Agentic Orchestrator.

Mirrors the CrewAI-style workflow from the pitch as an explicit, auditable
pipeline (no heavyweight dependency, deterministic ordering):

    Intake -> Extraction -> Eligibility -> Discovery -> Checklist -> Synthesis

Each stage is a pure function over the previous stage's output, which makes the
whole flow easy to log, test and reason about — important for a government
service where every decision must be traceable.

Eligibility and Discovery are deliberately separate stages over separate
corpora, and the distinction is the core safety property of this service:

  Eligibility  Tier 1 — hand-verified structured rules. MAY assert `eligible`.
  Discovery    Tier 2 — ~2k schemes of verbatim government prose. May only
               ever return `needs_verification`.

Tier 2 exists because no published source states eligibility as rules; it is
all prose. Converting 2,000 prose paragraphs into logic would take an LLM, and
a misread rule would be silently and permanently wrong. Keeping the corpora
apart means breadth never buys itself a false assertion of entitlement.
"""
from ..schemas import CitizenProfile
from . import checklist_agent, discovery_agent, eligibility_agent, extraction_agent


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
        "tier": "verified",
    })

    # 4. Discovery (Tier 2). Ranked by lexical relevance only. These are NOT
    # eligibility decisions and must never be merged into `matches` — an
    # operator (and the UI) has to be able to tell an assertion from a lead.
    discovery = discovery_agent.search(profile, limit=10)
    trace.append({
        "agent": "Discovery",
        "detail": (
            f"Surfaced {len(discovery)} possibly-relevant schemes from the "
            f"{len(discovery_agent.load_discovery())}-scheme corpus "
            f"(relevance only — eligibility not evaluated)"
        ),
        "tier": "discovery",
    })

    # 5. Checklist (localized). Build the consolidated master list first (it
    # needs the raw document keys), then localize + strip keys per scheme.
    checklist = checklist_agent.build_master_checklist(matches, language)
    for m in matches:
        m["documents"] = checklist_agent.localize_scheme_documents(m, language)
        m.pop("_documents_keys", None)
    trace.append({
        "agent": "Checklist",
        "detail": f"Generated a {checklist['total_documents']}-document localized checklist ({language})",
    })

    # 6. Synthesis
    summary = {
        "citizen_name": profile.name,
        "total_matches": len(matches),
        "eligible": len([m for m in matches if m["status"] == "eligible"]),
        "likely": len([m for m in matches if m["status"] in ("likely", "review")]),
        "needs_verification": len(discovery),
        "extraction_source": source,
        "confidence": confidence,
        "missing_fields": missing,
        "top_schemes": [m["name"] for m in matches[:3]],
    }
    trace.append({"agent": "Synthesis", "detail": "Compiled operator-ready application summary"})

    return {
        "profile": profile.model_dump(),
        "matches": matches,          # Tier 1 — verified, may say `eligible`
        "discovery": discovery,      # Tier 2 — leads, always `needs_verification`
        "checklist": checklist,
        "summary": summary,
        "trace": trace,
        "language": language,
    }
