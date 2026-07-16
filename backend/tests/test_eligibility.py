"""Tests for the deterministic matcher, and for the extraction/matching seam.

The seam is where extraction defects turn into denied entitlements, so the
interesting cases here are about what an UNKNOWN fact is allowed to do.
"""
import pytest

from app.agents import eligibility_agent
from app.agents.extraction_agent import _rule_based
from app.schemas import CitizenProfile
from app.services.scheme_repo import get_scheme, load_schemes


def _status(profile: CitizenProfile, scheme_id: str) -> str:
    return eligibility_agent.evaluate_scheme(profile, get_scheme(scheme_id))["status"]


# --- unknowns must never silently deny -----------------------------------

def test_unknown_disability_keeps_the_pension_visible_for_review():
    """The whole point of the 40% default being wrong: IGNDPS needs 80%, so a
    guessed 40% FAILS the rule, marks the scheme not_eligible, and match_all
    then filters it off the operator's screen. Unknown must stay unknown."""
    profile = _rule_based("Mohan Lal is a 42 year old disabled man. He has a BPL card.")
    assert profile.disability_percent is None
    assert _status(profile, "igndps") == "likely"

    visible = {m["scheme_id"] for m in eligibility_agent.match_all(profile)}
    assert "igndps" in visible


def test_a_guessed_disability_percent_would_hide_the_scheme():
    """Pins the failure mode itself, so nobody reintroduces the default."""
    guessed = CitizenProfile(age=42, is_bpl=True, disability_percent=40)
    assert _status(guessed, "igndps") == "not_eligible"
    assert "igndps" not in {m["scheme_id"] for m in eligibility_agent.match_all(guessed)}


def test_stated_shortfall_is_honoured():
    below = CitizenProfile(age=45, is_bpl=True, disability_percent=60)
    above = CitizenProfile(age=45, is_bpl=True, disability_percent=85)
    assert _status(below, "igndps") == "not_eligible"
    assert _status(above, "igndps") == "eligible"


def test_low_income_reaches_income_capped_schemes():
    """A wrong monthly/annual call is the difference between qualifying for
    Ayushman Bharat's ₹2.5L cap and being silently excluded."""
    profile = _rule_based(
        "Ramu Yadav is a 30 year old labourer. His annual income is Rs 40,000 "
        "and he holds a BPL card."
    )
    assert profile.annual_income == 40000
    assert _status(profile, "ayushman-bharat") == "eligible"


# --- the conservative promises the README makes ---------------------------

def test_a_22_year_old_is_not_told_she_is_eligible_for_a_pension():
    """The README promises this explicitly."""
    profile = _rule_based("Priya is a 22 year old woman working as a teacher in a town in Kerala.")
    assert _status(profile, "apy") == "review"


def test_a_positively_failed_criterion_is_not_eligible():
    assert _status(CitizenProfile(gender="male", age=30, is_bpl=True), "pmuy") == "not_eligible"


def test_not_eligible_is_hidden_unless_explicitly_requested():
    profile = CitizenProfile(gender="male", age=30, is_bpl=True)
    assert "pmuy" not in {m["scheme_id"] for m in eligibility_agent.match_all(profile)}
    assert "pmuy" in {
        m["scheme_id"] for m in eligibility_agent.match_all(profile, include_ineligible=True)
    }


def test_empty_profile_never_claims_eligibility():
    for m in eligibility_agent.match_all(CitizenProfile(), include_ineligible=True):
        assert m["status"] != "eligible", m["scheme_id"]


# --- ordering + dataset integrity ----------------------------------------

def test_results_are_ranked_eligible_first():
    profile = _rule_based("Sarita Devi is a 45 year old widow from a village in Bihar. She is BPL.")
    ranks = [
        eligibility_agent._STATUS_RANK[m["status"]] for m in eligibility_agent.match_all(profile)
    ]
    assert ranks == sorted(ranks)


@pytest.mark.parametrize("scheme", load_schemes(), ids=lambda s: s["id"])
def test_every_scheme_has_the_fields_the_matcher_and_ui_need(scheme):
    for key in ("id", "name", "category", "benefit", "documents", "official_link", "eligibility"):
        assert key in scheme, f"{scheme.get('id')} is missing {key}"
    assert isinstance(scheme["documents"], list) and scheme["documents"]


@pytest.mark.parametrize("scheme", load_schemes(), ids=lambda s: s["id"])
def test_scheme_eligibility_uses_only_keys_the_matcher_understands(scheme):
    """A typo'd rule key is invisible: the matcher just skips it and the scheme
    silently becomes easier to qualify for than the policy allows."""
    known = {
        "gender", "age_min", "age_max", "income_max", "occupation", "category",
        "area", "requires_bpl", "disability_min", "marital_status", "is_student",
        "land_holding_min", "custom", "notes",
    }
    unknown = set(scheme["eligibility"]) - known
    assert not unknown, f"{scheme['id']} has unrecognised eligibility keys: {unknown}"


@pytest.mark.parametrize("scheme", load_schemes(), ids=lambda s: s["id"])
def test_scheme_enum_rules_are_reachable(scheme):
    """The rule base and the extractor must share a vocabulary. A rule listing
    only values the extractor can never emit (occupation "agriculture" against a
    profile that says "farmer") evaluates as "unknown" forever and quietly stops
    counting. Extra synonyms alongside a reachable value are harmless."""
    elig = scheme["eligibility"]
    vocab = {
        "gender": {"male", "female", "other"},
        "category": {"general", "obc", "sc", "st"},
        "area": {"rural", "urban"},
        "marital_status": {"single", "married", "widow"},
    }
    for key, allowed in vocab.items():
        required = set(elig.get(key, []))
        if required:
            assert required & allowed, (
                f"{scheme['id']}.{key} requires one of {sorted(required)}, none of "
                f"which the extractor can produce (it emits {sorted(allowed)})"
            )


@pytest.mark.parametrize("scheme", load_schemes(), ids=lambda s: s["id"])
def test_every_occupation_rule_is_reachable(scheme):
    """A scheme may list synonyms the extractor never emits ("vendor" alongside
    "street_vendor") — harmless, since one reachable value is enough to fire the
    rule. What must never happen is a rule where NO value is reachable: it would
    evaluate as "unknown" forever, and the criterion would quietly stop counting.
    """
    from app.agents.extraction_agent import _OCCUPATION_MAP

    required = set(scheme["eligibility"].get("occupation", []))
    if not required:
        pytest.skip("no occupation rule")
    assert required & set(_OCCUPATION_MAP), (
        f"{scheme['id']} requires one of {sorted(required)}, none of which the "
        f"extractor can ever produce — the rule can never match"
    )
