"""Evaluation harness for the Tier-2 ranker.

WHY THIS EXISTS
---------------
Tier 2 cannot assert eligibility, so it can't be scored for correctness. But it
can still fail: if the ranker buries the right scheme at position 400, an
operator never scrolls to it and the corpus is decorative. "We have 1,966
schemes" is a storage fact, not a capability. This measures the capability.

GROUND TRUTH — and its limits
-----------------------------
Tier 1 is hand-verified and scores 16/16 on expected statuses, so when it says a
profile is eligible for `pm-kisan`, that is trustworthy. 11 Tier-1 schemes also
exist in the Tier-2 corpus under the same slug. So for each eval case:

    Tier-1 says eligible for X, and X is in Tier 2
      => a competent ranker should surface X near the top

This is a real but NARROW test. It only covers schemes that appear in both
corpora, which skews Central and skews toward the scheme types Tier 1 curated.
It says nothing about the ~1,955 Tier-2 schemes with no verified counterpart.
Treat the numbers as a floor, not a grade.

Run:
    python -m tests.eval.ranking
"""
from __future__ import annotations

import json
from pathlib import Path

from app.agents import discovery_agent, eligibility_agent, extraction_agent
from app.services.scheme_repo import load_schemes

CASES = Path(__file__).resolve().parent / "cases.json"
KS = (1, 3, 5, 10, 20, 50)


def build_ground_truth() -> list[tuple[str, object, str]]:
    """(case_id, profile, scheme_slug) for every verified-eligible scheme that
    also exists in Tier 2."""
    t2_slugs = {s["slug"] for s in discovery_agent.load_discovery()}
    shared = {s["id"] for s in load_schemes()} & t2_slugs

    pairs = []
    for case in json.load(open(CASES, encoding="utf-8")):
        profile = extraction_agent._rule_based(case["text"])
        for m in eligibility_agent.match_all(profile, include_ineligible=False):
            if m["status"] == "eligible" and m["scheme_id"] in shared:
                pairs.append((case["id"], profile, m["scheme_id"]))
    return pairs


def evaluate(search_fn, pairs) -> dict:
    """recall@k plus MRR over the ground-truth pairs."""
    maxk = max(KS)
    hits = {k: 0 for k in KS}
    rr_total = 0.0
    ranks: list[tuple[str, str, object]] = []

    for case_id, profile, want in pairs:
        results = search_fn(profile, limit=maxk)
        order = [r["scheme_id"].removeprefix("ms-") for r in results]
        rank = order.index(want) + 1 if want in order else None
        ranks.append((case_id, want, rank))
        if rank:
            rr_total += 1 / rank
            for k in KS:
                if rank <= k:
                    hits[k] += 1

    n = len(pairs)
    return {
        "n": n,
        "recall": {k: hits[k] / n for k in KS},
        "mrr": rr_total / n if n else 0.0,
        "ranks": ranks,
    }


def _print(label: str, rep: dict) -> None:
    print(f"\n{label}  (n={rep['n']} ground-truth pairs)")
    print("  " + "  ".join(f"R@{k}={rep['recall'][k]:.0%}" for k in KS))
    print(f"  MRR = {rep['mrr']:.3f}")
    missed = [(c, s) for c, s, r in rep["ranks"] if r is None]
    if missed:
        print(f"  not found in top {max(KS)}: " + ", ".join(f"{c}->{s}" for c, s in missed[:6]))


if __name__ == "__main__":
    pairs = build_ground_truth()
    if not pairs:
        raise SystemExit("no ground truth — is schemes_discovery.json built?")

    # dedupe must be OFF here: the ground-truth schemes ARE the Tier-1
    # collisions, so suppressing them would make this measure nothing.
    rep = evaluate(
        lambda p, limit: discovery_agent.search(p, limit=limit, suppress_verified=False),
        pairs,
    )
    _print("lexical overlap (current)", rep)
