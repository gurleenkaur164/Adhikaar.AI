# Adhikar.AI - An Agentic Copilot for Government Scheme Extraction

> **Theme:** Build for Bharat & Agentic AI · **Target impact:** Empowering CSC operators in rural India
> By Gurleen Kaur, Thapar Institute of Engineering & Technology.

Adhikar.AI transforms India's Common Service Centres (CSCs) from time-consuming data-entry
hubs into autonomous, AI-driven civic engines. A CSC operator types or dictates a citizen's
details in plain language; the system extracts a structured profile, matches every government
welfare scheme the citizen is entitled to, and generates a **localized document checklist**
(Hindi / Punjabi / English) — in seconds, at **₹0 operational cost**.

---

## The problem

- India runs **5.5 lakh+ CSCs** - the primary digital bridge for rural citizens.
- There are **1,000+ Central & State welfare schemes**, each with strict eligibility rules.
- **Scheme complexity** - citizens miss out; allocated welfare funds go under-utilised.
- **Operator bottlenecks** - CSC Village-Level Entrepreneurs (VLEs) drown in manual paperwork.
- **Last-mile drop-off** - even when a scheme is found, citizens abandon it for want of the
  right prerequisite documents.

## The solution

| Feature | What it does |
|---|---|
| **Conversational Data Entry** | Free text (any language) - clean structured citizen profile |
| **Instant Scheme Matching** | Profile checked against a **deterministic** rule base - policy-compliant matches |
| **Smart Document Checklists** | Consolidated, de-duplicated checklist localized to Hindi / Punjabi |
| **Assisted Application Prep** | Operator-ready summary dashboard + saved application record |
| **Zero-Cost Scale** | Free-tier architecture, human-in-the-loop, runs with **no API key** |

---

## Architecture — the agentic pipeline

The pitch's CrewAI-style workflow is implemented as an explicit, **auditable** pipeline
(`app/agents/orchestrator.py`). Each stage is a pure function over the previous stage's output,
so every decision is traceable — essential for a government service.



**Why AI extraction is separated from a deterministic matcher:** the LLM handles the messy,
multilingual *understanding* of the input, but eligibility is decided by a transparent rule
engine — so the tool never "hallucinates" an entitlement. The matcher is deliberately
conservative: a scheme is only marked **Eligible** when the profile *positively confirms* at
least two of its criteria; a single thin rule (e.g. an age band) is downgraded to **Review**
for the human operator. (This is why a 22-year-old is *not* told she's "eligible" for a
pension scheme.)

### Tech stack

| Layer | Technology |
|---|---|
| Frontend | **Next.js 16** (App Router) + Tailwind CSS v4 — Government-of-India portal UI |
| Backend | **FastAPI** (Python) |
| AI / NLP | **Llama 3 via Groq** (high-speed, zero-cost) with a deterministic rule-based fallback |
| Database | **SQLite** locally · **PostgreSQL**-ready for production (via `DATABASE_URL`) |
| Deploy | Vercel (frontend) + Render (backend) |

---



## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/process` | **Full pipeline**: text → profile → matches → localized checklist + trace |
| POST | `/api/extract` | Conversational data entry: text → structured profile |
| POST | `/api/match` | Profile → ranked eligible schemes with localized documents |
| GET  | `/api/schemes` | List the scheme knowledge base (`?category=` filter) |
| GET  | `/api/schemes/{id}` | Full scheme detail incl. eligibility rules |
| POST | `/api/applications` | Save a prepared application (human-in-the-loop record) |
| GET  | `/api/applications` | List saved applications |
| GET  | `/health` | Status, extraction mode, schemes loaded |

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/process \
  -H "Content-Type: application/json" \
  -d '{"text":"Sarita Devi is a 45 year old widow from a village in Bihar. She is BPL.","language":"hi"}'
```

---

## Datasets

The matcher ships with a **curated, machine-readable** dataset of 22 real Central welfare
schemes (`backend/app/data/schemes.json`) with structured eligibility rules, benefits and
required documents — plus a Hindi/Punjabi/English document-localization table
(`backend/app/data/localization.json`).

Public datasets used as the **source & expansion path** (the public data stores eligibility as
*free text*, which is exactly why an AI extraction layer is needed to make it matchable):

- **myScheme portal** — 1,000+ Central & State schemes with eligibility, benefits, documents:
  <https://www.myscheme.gov.in> · [dashboard](https://www.myscheme.gov.in/dashboard)
- **myScheme dataset (Hugging Face)** — `shrijayan/gov_myscheme`:
  <https://huggingface.co/datasets/shrijayan/gov_myscheme>
- **Indian Government Schemes (Kaggle)**:
  <https://www.kaggle.com/datasets/jainamgada45/indian-government-schemes> ·
  <https://www.kaggle.com/datasets/ash1003/indian-government-welfare-schemes>
- **Open Government Data (OGD) Platform India** — `data.gov.in` scheme datasets:
  <https://www.data.gov.in/keywords/Scheme>

To scale to the full corpus: ingest the myScheme/Kaggle text dumps, run the extraction agent
over each scheme's free-text eligibility to produce the structured rule blocks used here, and
append them to `schemes.json`.

---



> **Note on national symbols:** this project uses the **Ashoka Chakra** as a national motif.
> The State Emblem of India (the four-lion capitol) is legally protected under the State
> Emblem of India (Prohibition of Improper Use) Act, 2005, and is deliberately **not** used.
> This is a hackathon concept and **not** an official Government of India service.
