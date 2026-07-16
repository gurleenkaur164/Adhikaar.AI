"""Evaluation harness for the AI layer.

Scores the extraction agent field-by-field against a hand-labeled set, and the
eligibility agent against expected scheme statuses. Without this, "the
predictions are more accurate" is an unfalsifiable claim.

Four outcomes are tracked per field, because they are not equally bad:

  correct       expected a value, got that value
  wrong         expected a value, got a DIFFERENT value  (worst: silently misleads)
  missed        expected a value, got null               (recoverable: operator is told)
  hallucinated  expected null, got a value               (worst: invents entitlement)

Run directly for a report:
    python -m tests.eval.runner            # rule-based path only
    python -m tests.eval.runner --ai       # exercise the Groq/LLM path too
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.agents import eligibility_agent, extraction_agent  # noqa: E402
from app.schemas import CitizenProfile  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "cases.json"

CORRECT = "correct"
WRONG = "wrong"
MISSED = "missed"
HALLUCINATED = "hallucinated"


def load_cases() -> list[dict]:
    with open(CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _equal(expected, actual) -> bool:
    if expected is None or actual is None:
        return expected is actual or (expected is None and actual is None)
    if isinstance(expected, bool) or isinstance(actual, bool):
        return bool(expected) is bool(actual)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 0.01
    return str(expected).strip().lower() == str(actual).strip().lower()


@dataclass
class FieldResult:
    case_id: str
    field_name: str
    expected: object
    actual: object
    outcome: str


@dataclass
class CaseResult:
    case_id: str
    fields: list[FieldResult] = field(default_factory=list)
    status_checks: list[tuple[str, str, str]] = field(default_factory=list)  # scheme, expected, actual
    confidence: float = 0.0
    confidence_ok: bool = True
    source: str = ""

    @property
    def status_correct(self) -> int:
        return sum(1 for _, e, a in self.status_checks if e == a)


def score_profile(case: dict, profile: CitizenProfile) -> list[FieldResult]:
    results: list[FieldResult] = []

    for name, exp in (case.get("expected") or {}).items():
        actual = getattr(profile, name, None)
        if exp is None:
            outcome = CORRECT if actual in (None, "") else HALLUCINATED
        elif actual in (None, ""):
            outcome = MISSED
        else:
            outcome = CORRECT if _equal(exp, actual) else WRONG
        results.append(FieldResult(case["id"], name, exp, actual, outcome))

    for name in case.get("expect_null") or []:
        actual = getattr(profile, name, None)
        outcome = CORRECT if actual in (None, "") else HALLUCINATED
        results.append(FieldResult(case["id"], name, None, actual, outcome))

    for flag in case.get("expected_flags") or []:
        present = flag in (profile.flags or [])
        results.append(
            FieldResult(case["id"], f"flag:{flag}", flag, profile.flags, CORRECT if present else MISSED)
        )

    return results


def run_case(case: dict, use_ai: bool) -> CaseResult:
    if use_ai:
        profile, source, confidence = extraction_agent.extract_profile(case["text"])
    else:
        profile = extraction_agent._rule_based(case["text"])
        source = "rule-based"
        confidence = extraction_agent._confidence(profile) if hasattr(
            extraction_agent, "_confidence"
        ) else round(
            sum(1 for f in extraction_agent._KEY_FIELDS if getattr(profile, f) not in (None, ""))
            / len(extraction_agent._KEY_FIELDS),
            2,
        )

    result = CaseResult(case_id=case["id"], source=source, confidence=confidence)
    result.fields = score_profile(case, profile)

    expected_statuses = case.get("expected_statuses") or {}
    if expected_statuses:
        matches = {
            m["scheme_id"]: m["status"]
            for m in eligibility_agent.match_all(profile, include_ineligible=True)
        }
        for scheme_id, exp_status in expected_statuses.items():
            result.status_checks.append((scheme_id, exp_status, matches.get(scheme_id, "<absent>")))

    if "max_confidence" in case:
        result.confidence_ok = confidence <= case["max_confidence"]

    return result


def run_eval(use_ai: bool = False) -> list[CaseResult]:
    return [run_case(c, use_ai) for c in load_cases()]


def report(results: list[CaseResult]) -> dict:
    counts = {CORRECT: 0, WRONG: 0, MISSED: 0, HALLUCINATED: 0}
    for r in results:
        for f in r.fields:
            counts[f.outcome] += 1
    total = sum(counts.values())

    status_total = sum(len(r.status_checks) for r in results)
    status_ok = sum(r.status_correct for r in results)

    return {
        "field_counts": counts,
        "field_total": total,
        "field_accuracy": round(counts[CORRECT] / total, 4) if total else 0.0,
        "status_total": status_total,
        "status_correct": status_ok,
        "status_accuracy": round(status_ok / status_total, 4) if status_total else 0.0,
        "confidence_violations": [r.case_id for r in results if not r.confidence_ok],
    }


def _print_report(results: list[CaseResult]) -> None:
    rep = report(results)
    c = rep["field_counts"]

    print("=" * 78)
    print("EXTRACTION — field-level outcomes")
    print("=" * 78)
    for name, key in (
        ("correct", CORRECT),
        ("wrong (silently misleading)", WRONG),
        ("missed (null, operator warned)", MISSED),
        ("hallucinated (invented a fact)", HALLUCINATED),
    ):
        n = c[key]
        pct = (n / rep["field_total"] * 100) if rep["field_total"] else 0
        print(f"  {name:<34} {n:>4}  ({pct:5.1f}%)")
    print(f"  {'TOTAL':<34} {rep['field_total']:>4}")
    print(f"\n  field accuracy: {rep['field_accuracy']:.1%}")

    print("\n" + "=" * 78)
    print("ELIGIBILITY — expected scheme statuses")
    print("=" * 78)
    print(f"  {rep['status_correct']}/{rep['status_total']} correct  ({rep['status_accuracy']:.1%})")

    failures = [
        (r.case_id, s, e, a) for r in results for s, e, a in r.status_checks if e != a
    ]
    if failures:
        print("\n  mismatches:")
        for case_id, scheme, exp, act in failures:
            print(f"    {case_id:<32} {scheme:<26} expected {exp:<14} got {act}")

    if rep["confidence_violations"]:
        print(f"\n  confidence too high on: {', '.join(rep['confidence_violations'])}")

    print("\n" + "=" * 78)
    print("PER-FIELD DETAIL (non-correct only)")
    print("=" * 78)
    for r in results:
        bad = [f for f in r.fields if f.outcome != CORRECT]
        if not bad:
            continue
        print(f"\n  {r.case_id}  (source={r.source}, confidence={r.confidence})")
        for f in bad:
            print(f"    {f.outcome:<13} {f.field_name:<22} expected={f.expected!r:<22} got={f.actual!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ai", action="store_true", help="exercise the Groq/LLM path")
    args = ap.parse_args()

    if args.ai:
        from app.config import settings

        if not settings.ai_enabled:
            print("GROQ_API_KEY is not set — the --ai run would silently measure the "
                  "rule-based fallback instead. Refusing to report a misleading number.")
            raise SystemExit(2)

    results = run_eval(use_ai=args.ai)
    print(f"\npath: {'AI (Groq) + rule-based merge' if args.ai else 'rule-based only'}\n")
    _print_report(results)


if __name__ == "__main__":
    main()
