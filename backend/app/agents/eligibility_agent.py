"""Eligibility Agent — deterministic rules engine.

Zero AI here by design: the pitch promises "100% accurate, guaranteed scheme
matches, eliminating human guesswork". Each scheme's structured eligibility
block is evaluated against the citizen profile. Unknown facts never hard-fail a
scheme — they downgrade it to 'likely' / 'review' so the human operator decides.
"""
from ..schemas import CitizenProfile
from ..services.scheme_repo import load_schemes

# criteria checkers return one of: "pass", "fail", "unknown"


def _check_enum(profile_val, allowed) -> str:
    if profile_val in (None, ""):
        return "unknown"
    return "pass" if str(profile_val).lower() in [str(a).lower() for a in allowed] else "fail"


def _evaluate(profile: CitizenProfile, elig: dict) -> tuple[list[str], list[str], list[str]]:
    """Returns (matched, failed, unknown) human-readable criteria labels."""
    matched, failed, unknown = [], [], []

    def record(label: str, result: str):
        {"pass": matched, "fail": failed, "unknown": unknown}[result].append(label)

    if "gender" in elig:
        record(f"Gender: {', '.join(elig['gender'])}", _check_enum(profile.gender, elig["gender"]))

    if "age_min" in elig or "age_max" in elig:
        lo, hi = elig.get("age_min", 0), elig.get("age_max", 200)
        label = f"Age {lo}-{hi if hi < 200 else '+'}"
        if profile.age is None:
            record(label, "unknown")
        else:
            record(label, "pass" if lo <= profile.age <= hi else "fail")

    if "income_max" in elig:
        label = f"Annual income ≤ ₹{elig['income_max']:,}"
        if profile.annual_income is None:
            record(label, "unknown")
        else:
            record(label, "pass" if profile.annual_income <= elig["income_max"] else "fail")

    if "occupation" in elig:
        record(f"Occupation: {', '.join(elig['occupation'])}", _check_enum(profile.occupation, elig["occupation"]))

    if "category" in elig:
        record(f"Category: {', '.join(c.upper() for c in elig['category'])}", _check_enum(profile.category, elig["category"]))

    if "area" in elig:
        record(f"Area: {', '.join(elig['area'])}", _check_enum(profile.area, elig["area"]))

    if elig.get("requires_bpl"):
        if profile.is_bpl is None:
            record("BPL household", "unknown")
        else:
            record("BPL household", "pass" if profile.is_bpl else "fail")

    if "disability_min" in elig:
        label = f"Disability ≥ {elig['disability_min']}%"
        if profile.disability_percent is None:
            record(label, "unknown")
        else:
            record(label, "pass" if profile.disability_percent >= elig["disability_min"] else "fail")

    if "marital_status" in elig:
        record(f"Marital status: {', '.join(elig['marital_status'])}", _check_enum(profile.marital_status, elig["marital_status"]))

    if elig.get("is_student"):
        if profile.is_student is None:
            record("Currently a student", "unknown")
        else:
            record("Currently a student", "pass" if profile.is_student else "fail")

    if "land_holding_min" in elig:
        label = "Owns cultivable land"
        if profile.land_holding_acres is None:
            record(label, "unknown")
        else:
            record(label, "pass" if profile.land_holding_acres >= elig["land_holding_min"] else "fail")

    for flag in elig.get("custom", []):
        pretty = flag.replace("_", " ").capitalize()
        val = getattr(profile, flag, None)
        if val is None:
            val = flag in (profile.flags or [])
            record(pretty, "pass" if val else "unknown")
        else:
            record(pretty, "pass" if val else "fail")

    return matched, failed, unknown


def evaluate_scheme(profile: CitizenProfile, scheme: dict) -> dict:
    matched, failed, unknown = _evaluate(profile, scheme.get("eligibility", {}))

    # Status is deliberately conservative — this is a government service, so we
    # never over-promise. A scheme is only "eligible" when the citizen's profile
    # positively confirms at least TWO of its criteria and nothing is unknown.
    # A single thin match (e.g. only an age band, like Atal Pension for any
    # 18-40 adult) is downgraded to "review" so the operator decides, rather
    # than the tool declaring a 22-year-old "eligible" for a pension scheme.
    if failed:
        status = "not_eligible"
    elif not matched:
        status = "review"                       # nothing positively confirmed yet
    elif unknown:
        status = "likely"                        # partial confirmation, gaps remain
    elif len(matched) >= 2:
        status = "eligible"                      # fully & substantively confirmed
    else:
        status = "review"                        # technically qualifies on one thin rule

    denom = len(matched) + len(unknown)
    score = round(len(matched) / denom, 2) if denom else 0.0

    return {
        "scheme_id": scheme["id"],
        "name": scheme["name"],
        "category": scheme["category"],
        "benefit": scheme["benefit"],
        "status": status,
        "score": score,
        "matched_criteria": matched,
        "failed_criteria": failed + [f"{u} (unconfirmed)" for u in unknown],
        "official_link": scheme["official_link"],
        "_documents_keys": scheme["documents"],  # localized later by checklist agent
    }


_STATUS_RANK = {"eligible": 0, "likely": 1, "review": 2, "not_eligible": 3}


def match_all(profile: CitizenProfile, include_ineligible: bool = False) -> list[dict]:
    results = [evaluate_scheme(profile, s) for s in load_schemes()]
    if not include_ineligible:
        results = [r for r in results if r["status"] != "not_eligible"]
    results.sort(key=lambda r: (_STATUS_RANK[r["status"]], -r["score"]))
    return results
