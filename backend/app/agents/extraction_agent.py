"""Extraction Agent — turns an operator's free-text description of a citizen
into a structured profile.

Primary path: Groq/Llama 3 (fast, handles Hindi/Punjabi/mixed input).
Fallback path: a deterministic rule-based parser so the agent always returns
something usable even with no API key or no internet — the "Rs. 0" guarantee.
"""
import re

from ..schemas import CitizenProfile
from ..services.groq_client import chat_json

_SYSTEM_PROMPT = """You are a data-extraction assistant for an Indian Common Service Centre (CSC) operator.
Extract a citizen's details from the operator's description into JSON. The input may be in English, Hindi, Punjabi or a mix.
Return ONLY a JSON object with these keys (use null when unknown):
{
  "name": string,
  "age": integer,
  "gender": "male" | "female" | "other",
  "annual_income": integer (rupees per YEAR; convert monthly figures by x12),
  "occupation": one normalised keyword like "farmer","labourer","artisan","street_vendor","student","shopkeeper","teacher","domestic_worker",
  "category": "general" | "obc" | "sc" | "st",
  "state": string,
  "area": "rural" | "urban",
  "is_bpl": boolean,
  "disability_percent": integer,
  "marital_status": "single" | "married" | "widow",
  "is_student": boolean,
  "land_holding_acres": number,
  "is_pregnant": boolean,
  "num_children": integer,
  "flags": array of strings for other notable facts (e.g. "breadwinner_deceased")
}
Do not invent facts that are not stated."""

# ---- fields the matcher cares most about; used to report "missing" -------
_KEY_FIELDS = ["age", "gender", "annual_income", "occupation", "category", "area", "is_bpl"]

_OCCUPATION_MAP = {
    "farmer": ["farmer", "kisan", "farming", "agricultur", "cultivat", "किसान", "ਕਿਸਾਨ"],
    "labourer": ["labour", "labor", "mazdoor", "daily wage", "worker", "मजदूर", "ਮਜ਼ਦੂਰ"],
    "artisan": ["artisan", "craft", "carpenter", "blacksmith", "potter", "weaver", "cobbler", "mason", "kumhar"],
    "street_vendor": ["street vendor", "vendor", "hawker", "thela", "rehri", "ਰੇਹੜੀ"],
    "student": ["student", "study", "studying", "college", "school", "छात्र", "ਵਿਦਿਆਰਥੀ"],
    "shopkeeper": ["shop", "shopkeeper", "dukaan", "kirana", "trader", "business"],
    "teacher": ["teacher", "adhyapak"],
    "domestic_worker": ["domestic worker", "maid", "house help", "househelp"],
    "fisherman": ["fisher", "fisherman", "machhuara"],
    "tailor": ["tailor", "darzi"],
    "rickshaw_puller": ["rickshaw", "auto driver", "e-rickshaw"],
}

_STATES = [
    "punjab", "haryana", "rajasthan", "gujarat", "maharashtra", "bihar", "uttar pradesh",
    "up", "madhya pradesh", "mp", "karnataka", "kerala", "tamil nadu", "telangana",
    "andhra pradesh", "west bengal", "odisha", "assam", "jharkhand", "chhattisgarh",
    "uttarakhand", "himachal pradesh", "delhi", "jammu", "kashmir",
]


def _num(text: str) -> int | None:
    text = text.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lac|crore|thousand|k|hazaar)?", text)
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit in ("lakh", "lac"):
        val *= 100000
    elif unit == "crore":
        val *= 10000000
    elif unit in ("thousand", "k", "hazaar"):
        val *= 1000
    return int(val)


def _rule_based(text: str) -> CitizenProfile:
    t = text.lower()
    p = CitizenProfile()

    # age — try explicit "45 years / year old / saal", then "age 45 / aged 45",
    # then the common shorthand "Ramesh Kumar, 32, farmer" (comma-bracketed).
    m = re.search(r"(\d{1,3})\s*(?:years?|yrs?|saal|year old|-year|साल|ਸਾਲ)", t)
    if not m:
        m = re.search(r"\bage[d]?\s*(?:is|:)?\s*(\d{1,3})", t)
    if not m:
        m = re.search(r",\s*(\d{1,2})\s*(?:,|\.|\band\b|$)", t)  # "name, 32, ..."
    if m:
        age = int(m.group(1))
        if 0 < age < 120:
            p.age = age

    # gender
    if re.search(r"\b(woman|female|lady|girl|mahila|widow|mother|pregnant|she|her|महिला|ਔਰਤ)\b", t):
        p.gender = "female"
    elif re.search(r"\b(man|male|boy|father|husband|he|his|him|पुरुष|ਆਦਮੀ)\b", t):
        p.gender = "male"

    # income
    inc = re.search(r"(?:income|earns?|salary|kamata|kamai|आय)[^\d]{0,15}([\d,\.]+\s*(?:lakh|lac|crore|thousand|k|hazaar)?)", t)
    if inc:
        val = _num(inc.group(1))
        if val is not None:
            # heuristic: figures under ~50k are likely monthly -> annualise
            if "month" in t or "mahina" in t or "per month" in t:
                val *= 12
            elif val < 50000 and "year" not in t and "annual" not in t and "saal" not in t:
                val *= 12
            p.annual_income = val

    # occupation
    for norm, kws in _OCCUPATION_MAP.items():
        if any(kw in t for kw in kws):
            p.occupation = norm
            if norm == "student":
                p.is_student = True
            break

    # category
    if re.search(r"\b(scheduled tribe|\bst\b|adivasi|tribal)\b", t):
        p.category = "st"
    elif re.search(r"\b(scheduled caste|\bsc\b|dalit)\b", t):
        p.category = "sc"
    elif re.search(r"\b(obc|other backward|backward class)\b", t):
        p.category = "obc"
    elif re.search(r"\b(general|upper caste)\b", t):
        p.category = "general"

    # area
    if re.search(r"\b(rural|village|gaon|pind|गांव|ਪਿੰਡ)\b", t):
        p.area = "rural"
    elif re.search(r"\b(urban|city|town|shehar|nagar)\b", t):
        p.area = "urban"

    # bpl
    if re.search(r"\b(bpl|below poverty|poor|garib|antyodaya|गरीब)\b", t):
        p.is_bpl = True

    # disability
    dis = re.search(r"(\d{1,3})\s*%?\s*(?:disab|divyang|handicap)", t)
    if not dis:
        dis = re.search(r"(?:disab|divyang|handicap)[^\d]{0,15}(\d{1,3})\s*%", t)
    if dis:
        p.disability_percent = int(dis.group(1))
    elif re.search(r"\b(disabled|disability|divyang|handicap|blind|deaf)\b", t):
        p.disability_percent = 40  # unspecified -> assume the common threshold, flag for review
        p.flags.append("disability_percent_assumed")

    # marital status
    if re.search(r"\b(widow|widowed|vidhwa|विधवा)\b", t):
        p.marital_status = "widow"
        if p.gender is None:
            p.gender = "female"
    elif re.search(r"\b(married|shaadi|husband|wife)\b", t):
        p.marital_status = "married"
    elif re.search(r"\b(unmarried|single)\b", t):
        p.marital_status = "single"

    # student
    if re.search(r"\b(student|studying|class\s*\d+|college|school)\b", t):
        p.is_student = True

    # land holding
    land = re.search(r"([\d\.]+)\s*(?:acre|acres|bigha|hectare|killa|ekad)", t)
    if land:
        p.land_holding_acres = float(land.group(1))
    elif p.occupation == "farmer" and re.search(r"\b(land|zameen|khet|jameen)\b", t):
        p.land_holding_acres = 1.0
        p.flags.append("land_holding_assumed")

    # pregnancy
    if re.search(r"\b(pregnant|expecting|garbhvati|गर्भवती)\b", t):
        p.is_pregnant = True
        if p.gender is None:
            p.gender = "female"

    # children
    ch = re.search(r"(\d+)\s*(?:child|children|kids|bachche|बच्चे)", t)
    if ch:
        p.num_children = int(ch.group(1))

    # extra flags
    if re.search(r"\b(breadwinner|earning member).{0,20}(died|death|expired|passed away)\b", t):
        p.flags.append("breadwinner_deceased")

    # name (best-effort: "name is X" / "named X")
    nm = re.search(r"(?:name is|named|naam|called)\s+([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)", text)
    if nm:
        p.name = nm.group(1).strip()

    # state
    for s in _STATES:
        if re.search(r"\b" + re.escape(s) + r"\b", t):
            p.state = s.title()
            break

    return p


def _from_ai(data: dict) -> CitizenProfile:
    """Coerce the LLM's JSON into a validated profile, ignoring junk."""
    allowed = CitizenProfile.model_fields.keys()
    clean = {k: v for k, v in data.items() if k in allowed and v is not None}
    if "flags" in clean and not isinstance(clean["flags"], list):
        clean["flags"] = []
    try:
        return CitizenProfile(**clean)
    except Exception:
        return CitizenProfile()


def _merge(ai: CitizenProfile, rule: CitizenProfile) -> CitizenProfile:
    """Fill any gaps the LLM left using the rule-based parser."""
    merged = ai.model_dump()
    for k, v in rule.model_dump().items():
        if k == "flags":
            merged["flags"] = list({*(merged.get("flags") or []), *(v or [])})
        elif merged.get(k) in (None, "") and v not in (None, ""):
            merged[k] = v
    return CitizenProfile(**merged)


def extract_profile(text: str) -> tuple[CitizenProfile, str, float]:
    """Returns (profile, source, confidence)."""
    rule = _rule_based(text)
    ai_json = chat_json(_SYSTEM_PROMPT, f"Operator description:\n{text}")

    if ai_json:
        profile = _merge(_from_ai(ai_json), rule)
        source = "groq"
    else:
        profile = rule
        source = "rule-based"

    filled = sum(1 for f in _KEY_FIELDS if getattr(profile, f) not in (None, ""))
    confidence = round(filled / len(_KEY_FIELDS), 2)
    return profile, source, confidence


def missing_fields(profile: CitizenProfile) -> list[str]:
    return [f for f in _KEY_FIELDS if getattr(profile, f) in (None, "")]
