"""Tier-2 contract tests.

These are not really unit tests of a ranking function — they are guards on the
one promise the corpus makes: Tier 2 surfaces schemes, it never asserts
eligibility. If someone later "improves" discovery_agent by having an LLM infer
eligibility from the prose, these tests must fail loudly.
"""
from __future__ import annotations

import pytest

from app.agents import discovery_agent
from app.schemas import CitizenProfile


@pytest.fixture(scope="module")
def corpus():
    data = discovery_agent.load_discovery()
    if not data:
        pytest.skip("schemes_discovery.json not built — run tools.ingest_myscheme")
    return data


@pytest.fixture
def widow():
    return CitizenProfile(
        name="Sarita Devi", age=45, gender="female", state="Bihar",
        area="rural", is_bpl=True, marital_status="widow",
    )


def test_corpus_is_large(corpus):
    """The whole point of Tier 2 is breadth."""
    assert len(corpus) >= 1000, f"expected 1000+ discovery schemes, got {len(corpus)}"


def test_every_record_is_verbatim_and_sourced(corpus):
    """No record may exist without provenance the operator can check."""
    for s in corpus:
        assert s["tier"] == "discovery"
        assert s["eligibility_text"].strip(), f"{s['slug']}: empty eligibility"
        assert s["official_link"].startswith("https://www.myscheme.gov.in/schemes/")
        assert s["snapshot"], f"{s['slug']}: undated data"


def test_no_record_carries_structured_rules(corpus):
    """Tier 2 must never grow rule fields — that's Tier 1's job, and rules here
    would mean someone let a model interpret the prose."""
    banned = {"eligibility", "age_min", "age_max", "income_max", "requires_bpl"}
    for s in corpus:
        assert not (banned & set(s)), f"{s['slug']} has rule-shaped fields"


def test_search_never_asserts_eligibility(corpus, widow):
    results = discovery_agent.search(widow, limit=25)
    assert results, "expected some relevant schemes for a rural BPL widow"
    for r in results:
        assert r["status"] == discovery_agent.NEEDS_VERIFICATION
        assert r["status"] != "eligible"
        assert "verify" in r["disclaimer"].lower()


def test_results_are_ranked_and_capped(corpus, widow):
    results = discovery_agent.search(widow, limit=5)
    assert len(results) <= 5
    scores = [r["relevance"] for r in results]
    assert scores == sorted(scores, reverse=True), "results not ranked"


def test_ranking_is_deterministic(corpus, widow):
    """No LLM, no randomness — same profile must give the same order."""
    a = [r["scheme_id"] for r in discovery_agent.search(widow, limit=10)]
    b = [r["scheme_id"] for r in discovery_agent.search(widow, limit=10)]
    assert a == b


def test_empty_profile_returns_nothing(corpus):
    """No stated facts means no basis to rank. Return nothing rather than
    a list of the most generic schemes, which would imply a recommendation."""
    assert discovery_agent.search(CitizenProfile(), limit=10) == []


def test_matched_terms_are_explainable(corpus, widow):
    """An operator must be able to see WHY a scheme surfaced."""
    for r in discovery_agent.search(widow, limit=10):
        assert r["matched_terms"], f"{r['scheme_id']} ranked with no matched terms"
