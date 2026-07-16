"""Regression tests for the extraction agent.

Each test pins one defect that was found by the eval harness. They exercise the
RULE-BASED path only, so they need no API key and no network — the same
guarantee the app itself makes.
"""
import pytest

from app.agents.extraction_agent import (
    _canonical_occupation,
    _confidence,
    _from_ai,
    _merge,
    _name,
    _rule_based,
)
from app.schemas import CitizenProfile


# --- Indic word boundaries ------------------------------------------------
# `\b` needs a \w -> non-\w transition, but Devanagari/Gurmukhi combining vowel
# signs are not \w, so `\bविधवा\b` never matched anything.

@pytest.mark.parametrize(
    "text, field, expected",
    [
        ("सुनीता देवी 50 साल की विधवा है।", "marital_status", "widow"),
        ("सुनीता देवी 50 साल की विधवा है।", "gender", "female"),
        ("वह एक महिला है, उम्र 30 साल।", "gender", "female"),
        ("वह गर्भवती है, उम्र 26 साल।", "is_pregnant", True),
        ("ਉਹ ਇੱਕ ਵਿਦਿਆਰਥੀ ਹੈ।", "is_student", True),
    ],
)
def test_indic_words_ending_in_a_combining_vowel_are_matched(text, field, expected):
    assert getattr(_rule_based(text), field) == expected


def test_consonant_final_indic_words_still_work():
    p = _rule_based("ਜਸਵੀਰ ਸਿੰਘ 45 ਸਾਲ ਦਾ ਕਿਸਾਨ ਹੈ, ਪਿੰਡ ਵਿੱਚ ਰਹਿੰਦਾ ਹੈ।")
    assert p.age == 45
    assert p.occupation == "farmer"
    assert p.area == "rural"


# --- income period --------------------------------------------------------
# The period used to be read from the whole description, so an age mention
# ("45 years old") suppressed the monthly conversion.

def test_monthly_income_is_annualised_even_when_age_mentions_years():
    p = _rule_based("Sunita is 45 years old and earns 6000 a month.")
    assert p.annual_income == 72000


def test_explicit_annual_income_is_not_multiplied():
    p = _rule_based("Ramu is a 30 year old labourer. His annual income is Rs 40,000.")
    assert p.annual_income == 40000


def test_small_annual_income_survives_to_reach_income_capped_schemes():
    """A wrong x12 turns ₹40k into ₹4.8L and silently fails Ayushman Bharat's
    ₹2.5L cap — the citizens most in need are the ones it would exclude."""
    p = _rule_based("Ramu earns 40000 per year.")
    assert p.annual_income is not None
    assert p.annual_income <= 250000


def test_unstated_income_period_is_flagged_not_guessed():
    p = _rule_based("Ramu is a labourer with an income of 20000.")
    assert p.annual_income == 20000
    assert "income_period_unstated" in p.flags


@pytest.mark.parametrize(
    "text, expected",
    [
        ("income 9000 per month", 108000),
        ("earns around 12000 monthly", 144000),
        ("annual income is about 1.5 lakh", 150000),
        ("family income is 1 lakh per year", 100000),
        ("उसकी आय 80000 प्रति वर्ष है।", 80000),
    ],
)
def test_income_period_variants(text, expected):
    assert _rule_based(text).annual_income == expected


# --- disability -----------------------------------------------------------

def test_unquantified_disability_is_not_assumed():
    """IGNDPS requires 80%. Assuming 40% made the rule FAIL, marking the scheme
    not_eligible and dropping it off the operator's screen entirely."""
    p = _rule_based("Mohan Lal is a 42 year old disabled man. He has a BPL card.")
    assert p.disability_percent is None
    assert "disability_percent_unstated" in p.flags


def test_stated_disability_percent_is_kept():
    assert _rule_based("Prakash, 45, has 60% disability.").disability_percent == 60


# --- occupation -----------------------------------------------------------

def test_domestic_worker_is_not_misread_as_labourer():
    """"domestic worker" contains "worker", a labourer keyword; first-match
    dict ordering classified every domestic worker as a labourer."""
    assert _rule_based("She works as a domestic worker in Delhi.").occupation == "domestic_worker"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("he is a daily wage labourer", "labourer"),
        ("an OBC e-rickshaw driver", "rickshaw_puller"),
        ("runs a kirana shop", "shopkeeper"),
        ("is a fisherman in a coastal village", "fisherman"),
        ("earns by stitching clothes", "tailor"),
        ("is a carpenter", "artisan"),
        ("is a street vendor", "street_vendor"),
    ],
)
def test_occupation_longest_keyword_wins(text, expected):
    assert _rule_based(text).occupation == expected


# --- gender ---------------------------------------------------------------

def test_relation_words_do_not_decide_the_subjects_gender():
    """"Kamla Devi ... her husband was the earning member" is a woman."""
    p = _rule_based(
        "Kamla Devi, 35, from a BPL family. Her husband was the earning member "
        "and he died last year."
    )
    assert p.gender == "female"
    assert "breadwinner_deceased" in p.flags


def test_subject_is_the_daughter_not_the_possessive_pronoun():
    assert _rule_based("Rajesh opened an account for his daughter Meena, 7.").gender == "female"


# --- name -----------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("Sarita Devi is a 45 year old widow from Bihar.", "Sarita Devi"),
        ("Gurmeet Singh, 52, is a farmer in Punjab.", "Gurmeet Singh"),
        ("Bhagwan Das, aged 68, lives in a village.", "Bhagwan Das"),
        ("Her name is Anita and she is 26.", "Anita"),
        ("A person came to the centre today asking about schemes.", None),
        ("She is a 45 year old widow.", None),
        ("The woman is 45 years old.", None),
    ],
)
def test_name_extraction(text, expected):
    assert _name(text) == expected


# --- normalising the LLM's answer -----------------------------------------

def test_llm_synonyms_are_canonicalised_to_the_rule_bases_vocabulary():
    """An LLM answering "Female"/"Scheduled Caste"/"agriculture" used to pass
    straight through and then silently fail the matcher's enum check."""
    p = _from_ai(
        {
            "gender": "Female",
            "category": "Scheduled Caste",
            "area": "Village",
            "occupation": "agriculture",
            "marital_status": "Widowed",
        }
    )
    assert p.gender == "female"
    assert p.category == "sc"
    assert p.area == "rural"
    assert p.occupation == "farmer"
    assert p.marital_status == "widow"


def test_llm_string_numbers_and_booleans_are_coerced():
    p = _from_ai({"age": "45", "annual_income": "1,20,000", "is_bpl": "yes"})
    assert p.age == 45
    assert p.annual_income == 120000
    assert p.is_bpl is True


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"age": 250}, "age"),
        ({"age": -3}, "age"),
        ({"disability_percent": 900}, "disability_percent"),
        ({"annual_income": -5000}, "annual_income"),
    ],
)
def test_out_of_range_llm_values_are_discarded(payload, field):
    assert getattr(_from_ai(payload), field) is None


def test_unrecognised_occupation_becomes_null_not_garbage():
    assert _canonical_occupation("astronaut") is None


def test_from_ai_survives_junk():
    assert _from_ai({"nonsense": 1, "flags": "not-a-list"}).flags == []
    assert _from_ai([]) == CitizenProfile()


# --- merge + confidence ---------------------------------------------------

def test_merge_fills_llm_gaps_from_rules():
    ai = CitizenProfile(name="Sarita", age=45)
    rule = CitizenProfile(age=45, gender="female", is_bpl=True)
    merged, agreement, conflicts = _merge(ai, rule)
    assert merged.name == "Sarita"
    assert merged.gender == "female"
    assert merged.is_bpl is True
    assert conflicts == []
    assert agreement == 1.0


def test_merge_records_disagreement_instead_of_hiding_it():
    ai = CitizenProfile(age=45, gender="male")
    rule = CitizenProfile(age=45, gender="female")
    merged, agreement, conflicts = _merge(ai, rule)
    assert merged.gender == "male"          # the LLM still wins
    assert "conflict:gender" in merged.flags  # but it is no longer silent
    assert agreement == 0.5
    assert conflicts == ["conflict:gender"]


def test_confidence_is_low_when_nothing_was_extracted():
    assert _confidence(CitizenProfile()) == 0.0


def test_confidence_rewards_independent_agreement():
    full = CitizenProfile(
        age=45, gender="female", annual_income=72000, occupation="tailor",
        category="sc", area="rural", is_bpl=True,
    )
    assert _confidence(full, agreement=1.0) > _confidence(full, agreement=0.0)


def test_confidence_is_penalised_by_guesses_and_conflicts():
    base = CitizenProfile(age=45, gender="female", is_bpl=True)
    guessed = base.model_copy(update={"flags": ["income_period_unstated"]})
    conflicted = base.model_copy(update={"flags": ["conflict:gender"]})
    assert _confidence(guessed) < _confidence(base)
    assert _confidence(conflicted) < _confidence(base)
