"""Ingest the myScheme corpus into the Tier-2 (discovery) scheme file.

WHY THIS EXISTS, AND WHAT IT REFUSES TO DO
------------------------------------------
Tier 1 (`app/data/schemes.json`) is hand-verified: each scheme carries
structured, executable eligibility rules, and the deterministic matcher is
allowed to *assert* that a citizen is eligible.

Tier 2 (this file's output) cannot make that promise, and does not try.

Every published source — myScheme included — states eligibility as PROSE, not
as rules. Turning ~2,000 prose paragraphs into executable logic would require
an LLM, and an LLM that mis-reads "SC/ST women with landholding under 2 acres,
excluding income-tax payers" writes a rule that is silently and permanently
wrong. A bad rule baked into the corpus is far worse than a bad extraction: the
extraction eval catches the latter on the next run, while the former quietly
tells the wrong citizen they qualify, forever, with an audit trail that looks
clean.

So this ingester interprets NOTHING. It extracts text deterministically, splits
on myScheme's own section headings, and stores the government's words verbatim.
Tier 2 records are surfaced for an operator to read and verify against the
official link. They are never marked eligible. Hallucination is prevented
structurally — the tier is incapable of asserting entitlement — rather than by
hoping a model behaves.

Anything that cannot be validated is REJECTED, not guessed at.

Usage:
    python -m tools.ingest_myscheme            # full run
    python -m tools.ingest_myscheme --limit 50 # smoke test
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests
from pypdf import PdfReader

_ROOT = Path(__file__).resolve().parents[1]
OUT = _ROOT / "app" / "data" / "schemes_discovery.json"

HF_REPO = "shrijayan/gov_myscheme"
HF_BASE = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/text_data/"
HF_API = f"https://huggingface.co/api/datasets/{HF_REPO}"
SCHEME_URL = "https://www.myscheme.gov.in/schemes/{slug}"

# Snapshot date of the upstream capture. Surfaced on every record: a welfare
# tool must never imply this is live data.
SNAPSHOT = "2025-02-09"

SECTIONS = [
    "Details", "Benefits", "Eligibility", "Exclusions",
    "Application Process", "Documents Required",
    "Frequently Asked Questions", "Sources And References",
]

# The PDFs are print-to-PDF captures of the live page, so browser chrome is
# baked into the text. Left in, it corrupts the section split — this is what
# made pm-kisan's "Eligibility" come out as navigation text.
CHROME = [
    r"Are\s*you\s*sure\s*you\s*want\s*to\s*sign\s*out\?", r"Sign\s*Out",
    r"Eng\s*English/हिंदी", r"Sign\s*In", r"Feedback", r"Cancel",
    r"Something\s*went\s*wrong\.\s*Please\s*try\s*again\s*later\.",
    r"You\s*need\s*to\s*sign\s*in\s*before\s*applying\s*for\s*schemes",
    r"It\s*seems\s*you\s*have\s*already\s*initiated\s*your\s*application\s*earlier\.",
    r"To\s*know\s*more\s*please\s*visit", r"Apply\s*Now", r"Check\s*Eligibility",
    r"Sign\s*in\s*to\s*apply", r"Was\s*this\s*helpful\?",
]

# an "eligibility" blob that is really nav/tag text
JUNK = re.compile(r"^(ministry|department|govt|government)\b|sign\s*in\s*to\s*apply", re.I)
CRITERIA = re.compile(
    r"\b(should|must|age|income|years|eligible|resident|applicant|belong|"
    r"holder|women|farmer|family|student|worker|citizen)\b",
    re.I,
)


def clean(t: str) -> str:
    t = t.replace("\t", " ").replace("\xa0", " ").replace("﻿", "")
    for c in CHROME:
        t = re.sub(c, " ", t, flags=re.I)
    return re.sub(r"[ ]{2,}", " ", t)


def split_sections(t: str) -> dict[str, str]:
    pat = "|".join(re.escape(s) for s in SECTIONS)
    parts = re.split(f"({pat})", t)
    out: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        k, v = parts[i], parts[i + 1].strip()
        if k not in out or len(v) > len(out[k]):
            out[k] = v
    return out


def extract_name(t: str) -> str:
    """Scheme title is the first line, ahead of the language toggle."""
    head = t.split("\n", 1)[0]
    head = re.split(r"Eng\s*English|Details\s*Benefits", head)[0]
    return re.sub(r"\s+", " ", head).strip()[:160]


def validate(name: str, elig: str) -> str | None:
    """Return a rejection reason, or None when the record is trustworthy."""
    if not name or len(name) < 4:
        return "no-name"
    if not elig:
        return "no-eligibility-section"
    if len(elig) < 60:
        return "too-short"
    if JUNK.search(elig[:80]):
        return "nav-text-not-criteria"
    if not CRITERIA.search(elig):
        return "no-criteria-language"
    return None


def list_slugs() -> list[str]:
    meta = requests.get(HF_API, timeout=60).json()
    files = [s["rfilename"] for s in meta.get("siblings", []) if s["rfilename"].endswith(".pdf")]
    # collapse the ' copy.pdf' / '(1).pdf' duplicates in the upstream dump
    return sorted({re.sub(r"( copy|\(\d+\))", "", f.split("/")[-1][:-4]).strip() for f in files})


def fetch(slug: str):
    try:
        r = requests.get(HF_BASE + slug + ".pdf", timeout=45)
        if r.status_code != 200:
            return slug, None, f"http-{r.status_code}"
        raw = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(r.content)).pages)
        t = clean(raw)
        secs = split_sections(t)
        name = extract_name(t)
        elig = secs.get("Eligibility", "")

        reason = validate(name, elig)
        if reason:
            return slug, None, reason

        return slug, {
            "id": f"ms-{slug}",
            "slug": slug,
            "name": name,
            "tier": "discovery",
            # Verbatim government text. Never parsed into rules.
            "eligibility_text": elig[:3000],
            "benefits_text": secs.get("Benefits", "")[:1200],
            "documents_text": secs.get("Documents Required", "")[:1200],
            "exclusions_text": secs.get("Exclusions", "")[:800],
            "official_link": SCHEME_URL.format(slug=slug),
            "source": f"myscheme.gov.in via HF {HF_REPO}",
            "snapshot": SNAPSHOT,
        }, None
    except Exception as e:  # noqa: BLE001 - one bad PDF must not kill the run
        return slug, None, f"error:{type(e).__name__}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    slugs = list_slugs()
    if args.limit:
        slugs = slugs[: args.limit]
    print(f"slugs to ingest: {len(slugs)}")

    ok: list[dict] = []
    rejected: dict[str, list[str]] = {}
    done = 0

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for slug, rec, reason in ex.map(fetch, slugs):
            done += 1
            if rec:
                ok.append(rec)
            else:
                rejected.setdefault(reason, []).append(slug)
            if done % 200 == 0:
                print(f"  {done}/{len(slugs)}  accepted={len(ok)}", flush=True)

    ok.sort(key=lambda r: r["slug"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(ok, f, ensure_ascii=False, indent=1)

    n = len(slugs)
    print(f"\naccepted : {len(ok)}/{n} ({len(ok)/n:.1%})")
    print(f"rejected : {n - len(ok)}")
    for r, s in sorted(rejected.items(), key=lambda x: -len(x[1])):
        print(f"   {r:<26} {len(s):>4}   e.g. {', '.join(s[:3])}")
    print(f"\nwrote {OUT.relative_to(_ROOT)}")

    if len(ok) < n * 0.80:
        print("\nyield below 80% — upstream format may have changed.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
