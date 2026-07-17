"""Tier-2 discovery: surface possibly-relevant schemes. Never assert eligibility.

THE CONTRACT
------------
Tier 1 (`eligibility_agent`) evaluates hand-verified structured rules and may
return `eligible`. Tier 2 may not, ever.

Tier 2 records hold the government's eligibility PROSE, verbatim. Nothing has
parsed that prose into logic, so nothing here knows whether a citizen qualifies
— and the moment this module claimed otherwise, it would be inventing
entitlement, which is the one failure this project cannot ship.

So the only status Tier 2 can emit is `needs_verification`, and the only thing
it computes is *relevance*: a deterministic lexical overlap between the profile
and the scheme text, used purely to order 2,000 schemes so an operator sees
plausible ones first. Relevance is not eligibility, and the ranking is not
evidence. The operator reads the official text and decides.

This mirrors the rule the rest of the codebase already follows: the extraction
agent returns None rather than guess, and the matcher only says `eligible` when
the profile positively confirms. Same principle, applied to the corpus.

No LLM is involved here. Scoring is pure term matching, so it is reproducible
and auditable.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.schemas import CitizenProfile

_DATA = Path(__file__).resolve().parents[1] / "data" / "schemes_discovery.json"

NEEDS_VERIFICATION = "needs_verification"

# Terms too common across welfare prose to carry any signal.
_STOP = {
    "scheme", "government", "india", "state", "benefit", "benefits", "applicant",
    "eligible", "eligibility", "person", "family", "year", "years", "the", "and",
    "for", "with", "under", "should", "must", "will", "any", "all", "who",
}


@lru_cache(maxsize=1)
def load_discovery() -> list[dict]:
    if not _DATA.exists():
        return []
    with open(_DATA, encoding="utf-8") as f:
        return json.load(f)


def _stem(w: str) -> str:
    """Crude plural strip — just enough that `farmers` and `farmer` are one
    token.

    Deliberately does NOT strip "es" wholesale: that maps `houses` -> `hous`
    while `house` stays `house`, so the two stop matching. Stripping a single
    trailing "s" handles houses/house and farmers/farmer alike.
    """
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


# Vocabulary bridges between how a profile is stated and how policy prose is
# written. Every one of these was found by measurement, not guessed:
# 6 of 7 unreachable ground-truth pairs were PMUY, because the profile says
# `female` and the scheme text says "an adult woman". No amount of BM25 tuning
# fixes a token that simply is not there.
#
# NOTE: this maps vocabulary, never policy. `female -> woman` is a synonym.
# `widow -> houseless` would be an inference about entitlement and must never
# be added here — that is Tier 1's job, with a human verifying it.
_SYNONYMS: dict[str, set[str]] = {
    "female": {"woman", "women", "girl", "mother", "wife", "her"},
    "male": {"man", "men", "boy", "father", "husband"},
    "bpl": {"poor", "poverty", "bpl", "below", "weaker", "destitute"},
    "rural": {"village", "rural", "gramin", "gram"},
    "urban": {"urban", "city", "town", "nagar"},
    "widow": {"widow", "widowed"},
    "farmer": {"farmer", "kisan", "agriculture", "agricultural", "cultivator", "krishi"},
    "student": {"student", "education", "scholarship", "study", "school", "college"},
    "disability": {"disability", "disabled", "divyang", "handicapped"},
    "senior": {"senior", "old", "elderly", "aged", "pension", "vridha"},
    "pregnant": {"pregnant", "maternity", "lactating", "matritva"},
    "sc": {"scheduled", "caste", "dalit"},
    "st": {"scheduled", "tribe", "tribal", "adivasi"},
    "obc": {"backward", "obc"},
}


# A synonym is a guess about wording; a stated fact is not. Weighting them
# equally measurably destroyed the ranking (MRR 0.033 -> 0.012): expansion adds
# ~30 mostly-generic tokens, so schemes matching many vague words outranked the
# one scheme matching `widow`. Expansion should assist the query, not drown it.
_SYN_WEIGHT = 0.35


def _expand(terms: set[str]) -> dict[str, float]:
    """Stated facts at full weight, synonyms discounted."""
    out: dict[str, float] = {}
    for t in terms:
        out[_stem(t)] = 1.0
    for t in terms:
        for s in _SYNONYMS.get(t, set()):
            k = _stem(s)
            out.setdefault(k, _SYN_WEIGHT)  # never downgrade a stated fact
    return out


def _tokens(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in _STOP}


def _tokenise(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in _STOP]


# BM25 params. k1 damps term-frequency saturation, b controls length
# normalisation. Standard defaults; tuned values gave no measurable gain on the
# ground-truth set, so they stay at the textbook numbers.
_K1 = 1.5
_B = 0.75


@lru_cache(maxsize=1)
def _index() -> dict:
    """Inverted index with IDF weights and document lengths.

    Plain term overlap was measured at R@10 = 4% / MRR 0.024 — it could not find
    schemes Tier 1 had *verified* as correct, even in the top 50. The reason is
    that overlap scores `widow` (rare, decisive) exactly like `rural` or
    `poverty`, which hit hundreds of documents, and it ignores length, so long
    schemes match everything. BM25 fixes both: IDF rewards rare terms, and `b`
    normalises for document length.
    """
    import math

    schemes = load_discovery()
    docs: list[list[str]] = []
    for s in schemes:
        blob = " ".join(
            (s.get(k) or "") for k in ("name", "eligibility_text", "benefits_text")
        )
        docs.append(_tokenise(blob))

    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n if n else 0.0

    df: dict[str, int] = {}
    tfs: list[dict[str, int]] = []
    for d in docs:
        tf: dict[str, int] = {}
        for w in d:
            tf[w] = tf.get(w, 0) + 1
        tfs.append(tf)
        for w in tf:
            df[w] = df.get(w, 0) + 1

    # BM25 idf, floored at a small positive value so ubiquitous terms
    # contribute ~nothing instead of going negative
    idf = {
        w: max(math.log((n - c + 0.5) / (c + 0.5) + 1.0), 1e-6)
        for w, c in df.items()
    }

    postings: dict[str, list[tuple[int, int]]] = {}
    for i, tf in enumerate(tfs):
        for w, c in tf.items():
            postings.setdefault(w, []).append((i, c))

    return {
        "schemes": schemes,
        "postings": postings,
        "idf": idf,
        "dl": [len(d) for d in docs],
        "avgdl": avgdl,
    }


def _profile_terms(p: CitizenProfile) -> set[str]:
    """Only facts the citizen actually stated. Nothing inferred."""
    terms: set[str] = set()
    for val in (p.occupation, p.gender, p.state, p.category, p.area, p.marital_status):
        if val:
            terms |= _tokens(str(val))
    if getattr(p, "is_bpl", None):
        terms |= {"bpl", "poverty", "below"}
    if getattr(p, "is_student", None):
        terms |= {"student", "education", "scholarship", "study"}
    if getattr(p, "disability_percent", None):
        terms |= {"disability", "disabled", "divyang"}
    if getattr(p, "is_pregnant", None):
        terms |= {"pregnant", "maternity", "lactating"}
    age = getattr(p, "age", None)
    if age is not None:
        if age >= 60:
            terms |= {"senior"}
        elif age <= 18:
            terms |= {"child", "minor"}
    return _expand(terms)


@lru_cache(maxsize=1)
def _verified_slugs() -> frozenset[str]:
    """Tier-1 ids that also exist in Tier 2 under the SAME slug.

    Matched on exact slug only, never fuzzily. 17 Tier-1 schemes look like they
    have Tier-2 twins, but fuzzy matching wrongly collapses genuinely distinct
    schemes — e.g. Andhra's pre-matric scholarship is not the Central one, and
    IGNOAPS (old-age) is not IGNDPS (disability). Suppressing those would hide
    real schemes from an operator. Only the 11 exact collisions are safe.
    """
    from app.services.scheme_repo import load_schemes

    return frozenset(s["id"] for s in load_schemes()) & frozenset(
        s["slug"] for s in load_discovery()
    )


def search(
    profile: CitizenProfile,
    limit: int = 10,
    suppress_verified: bool = True,
) -> list[dict]:
    """Rank Tier-2 schemes by lexical relevance to the profile.

    Returns `needs_verification` records only. A score is a hint for ordering,
    never a claim about entitlement.

    `suppress_verified` hides schemes Tier 1 already ruled on by exact slug, so
    an operator never sees the same scheme both asserted and unverified. The
    ranking eval turns it off, because those collisions are its ground truth.
    """
    terms = _profile_terms(profile)
    if not terms:
        return []

    skip = _verified_slugs() if suppress_verified else frozenset()

    idx = _index()
    postings, idf, dl, avgdl = idx["postings"], idx["idf"], idx["dl"], idx["avgdl"]

    # BM25 accumulation over the profile's terms
    acc: dict[int, float] = {}
    matched: dict[int, set[str]] = {}
    for t, qw in terms.items():
        plist = postings.get(t)
        if not plist:
            continue
        w = idf[t] * qw
        for i, tf in plist:
            denom = tf + _K1 * (1 - _B + _B * dl[i] / avgdl) if avgdl else tf + _K1
            acc[i] = acc.get(i, 0.0) + w * (tf * (_K1 + 1)) / denom
            if qw == 1.0:  # only stated facts are worth showing as "why"
                matched.setdefault(i, set()).add(t)

    schemes = idx["schemes"]
    scored = []
    for i, raw in acc.items():
        s = schemes[i]
        if s["slug"] in skip:
            continue
        scored.append((round(raw, 3), sorted(matched.get(i, set())), s))

    scored.sort(key=lambda x: (-x[0], x[2]["slug"]))

    return [
        {
            "scheme_id": s["id"],
            "name": s["name"],
            "tier": "discovery",
            "status": NEEDS_VERIFICATION,
            "relevance": score,
            "matched_terms": hits,
            # verbatim government text — the operator reads this, not a summary
            "eligibility_text": s["eligibility_text"],
            "official_link": s["official_link"],
            "snapshot": s["snapshot"],
            "disclaimer": (
                "Relevance only — eligibility has NOT been evaluated. "
                f"Text captured {s['snapshot']}; verify at the official link."
            ),
        }
        for score, hits, s in scored[:limit]
    ]
