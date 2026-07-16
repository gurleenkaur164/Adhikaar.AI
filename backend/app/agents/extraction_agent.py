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
Extract ONE citizen's details from the operator's description into JSON. The input may be in English, Hindi, Punjabi or a mix.

Return ONLY a JSON object with these keys (use null when the description does not state the fact):
{
  "name": string,
  "age": integer,
  "gender": "male" | "female" | "other",
  "annual_income": integer (rupees per YEAR),
  "occupation": one keyword from the OCCUPATIONS list below,
  "category": "general" | "obc" | "sc" | "st",
  "state": string,
  "area": "rural" | "urban",
  "is_bpl": boolean,
  "disability_percent": integer 1-100,
  "marital_status": "single" | "married" | "widow",
  "is_student": boolean,
  "land_holding_acres": number,
  "is_pregnant": boolean,
  "num_children": integer,
  "flags": array of strings for other notable facts (e.g. "breadwinner_deceased")
}

OCCUPATIONS — use EXACTLY one of these strings, never a synonym:
farmer, labourer, artisan, street_vendor, student, shopkeeper, teacher,
domestic_worker, fisherman, tailor, rickshaw_puller
(a carpenter/potter/weaver/blacksmith/mason is "artisan"; a maid or house help is
"domestic_worker"; an auto or e-rickshaw driver is "rickshaw_puller")

RULES — these decide whether a citizen keeps or loses a real entitlement:

1. NEVER invent a fact. If the description does not state it, the value is null.
   An unknown field is safe: the operator is shown it and asked. A guessed field
   is not: it silently changes which schemes the citizen is offered.

2. disability_percent: only fill this when a NUMBER is stated. "he is disabled"
   with no percentage means disability_percent is null, NOT 40 and NOT 80.

3. annual_income: report rupees PER YEAR.
   - "6000 a month"        -> 72000   (multiply monthly figures by 12)
   - "40,000 per year"     -> 40000   (already annual, do NOT multiply)
   - "3 lakh"              -> 300000
   If the period is genuinely not stated, report the number as given and add
   "income_period_unstated" to flags. Do not guess the period from the size of
   the number.

4. Describe the SUBJECT of the application, not their relatives.
   - "Kamla's husband died last year"  -> the subject is Kamla: gender "female".
   - "Rajesh wants an account for his daughter Meena, 7" -> the subject is
     Meena: name "Meena", age 7, gender "female".

5. Do not infer is_bpl from an occupation or a low income. It requires the
   description to say so (BPL, below poverty line, garib, Antyodaya, ration card).

EXAMPLES

Input: Sarita Devi is a 45 year old widow from a village in Bihar. She is BPL.
Output: {"name":"Sarita Devi","age":45,"gender":"female","annual_income":null,"occupation":null,"category":null,"state":"Bihar","area":"rural","is_bpl":true,"disability_percent":null,"marital_status":"widow","is_student":null,"land_holding_acres":null,"is_pregnant":null,"num_children":null,"flags":[]}

Input: Sunita is 45 years old, works as a domestic worker in Delhi, and earns 6000 a month.
Output: {"name":"Sunita","age":45,"gender":"female","annual_income":72000,"occupation":"domestic_worker","category":null,"state":"Delhi","area":null,"is_bpl":null,"disability_percent":null,"marital_status":null,"is_student":null,"land_holding_acres":null,"is_pregnant":null,"num_children":null,"flags":[]}

Input: Mohan Lal is a 42 year old disabled man from a village in Rajasthan. He has a BPL ration card.
Output: {"name":"Mohan Lal","age":42,"gender":"male","annual_income":null,"occupation":null,"category":null,"state":"Rajasthan","area":"rural","is_bpl":true,"disability_percent":null,"marital_status":null,"is_student":null,"land_holding_acres":null,"is_pregnant":null,"num_children":null,"flags":["disability_percent_unstated"]}

Input: ਜਸਵੀਰ ਸਿੰਘ 45 ਸਾਲ ਦਾ ਕਿਸਾਨ ਹੈ, ਪਿੰਡ ਵਿੱਚ ਰਹਿੰਦਾ ਹੈ।
Output: {"name":"Jasveer Singh","age":45,"gender":"male","annual_income":null,"occupation":"farmer","category":null,"state":null,"area":"rural","is_bpl":null,"disability_percent":null,"marital_status":null,"is_student":null,"land_holding_acres":null,"is_pregnant":null,"num_children":null,"flags":[]}"""

# ---- fields the matcher cares most about; used to report "missing" -------
_KEY_FIELDS = ["age", "gender", "annual_income", "occupation", "category", "area", "is_bpl"]


def _w(*alternatives: str) -> str:
    """Build a whole-word alternation that also works for Indic scripts.

    `\\b` is a transition between a \\w and a non-\\w character, but Python's `re`
    does not treat Devanagari/Gurmukhi combining vowel signs (Unicode categories
    Mn/Mc) as word characters. So for any word ending in one — विधवा, महिला,
    गर्भवती, बच्चे, ਵਿਦਿਆਰਥੀ, ਆਦਮੀ, ਰੇਹੜੀ — there is no \\w→non-\\w transition at
    the end and `\\bविधवा\\b` can never match. Words ending in a consonant
    (किसान, गांव, साल) match fine, which is why this looked like it worked.

    Lookarounds express the intent directly — "not preceded/followed by another
    word character" — and behave identically to `\\b` for ASCII.
    """
    return r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)"


_OCCUPATION_MAP = {
    "farmer": ["farmer", "kisan", "farming", "agricultur", "cultivat", "dairy farm",
               "किसान", "ਕਿਸਾਨ"],
    "labourer": ["labour", "labor", "mazdoor", "daily wage", "worker", "construction worker",
                 "construction labour", "unorganised worker", "unorganized worker",
                 "मजदूर", "ਮਜ਼ਦੂਰ"],
    "artisan": ["artisan", "craft", "craftsman", "carpenter", "blacksmith", "potter",
                "weaver", "cobbler", "mason", "kumhar", "goldsmith", "sunar", "lohar",
                "badhai", "mochi", "ਕਾਰੀਗਰ"],
    "street_vendor": ["street vendor", "vendor", "hawker", "thela", "rehri", "ਰੇਹੜੀ"],
    "student": ["student", "study", "studying", "college", "school", "छात्र", "ਵਿਦਿਆਰਥੀ"],
    "shopkeeper": ["shop", "shopkeeper", "dukaan", "kirana", "trader", "business"],
    "teacher": ["teacher", "adhyapak"],
    "domestic_worker": ["domestic worker", "maid", "house help", "househelp"],
    "fisherman": ["fisher", "fisherman", "machhuara"],
    "tailor": ["tailor", "darzi", "stitch", "sewing", "silai"],
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


_MONTHLY_RE = re.compile(
    r"(per\s*month|a\s*month|/\s*month|monthly|mahina|mahine|maheena|prati\s*maah|"
    r"महीना|महीने|प्रति\s*माह|ਮਹੀਨਾ|ਮਹੀਨੇ)"
)
# NB: bare "saal"/"साल" is deliberately NOT an annual marker — in practice it
# almost always denotes AGE ("umar 35 saal"), and treating it as a period marker
# reintroduces exactly the cross-contamination this function exists to prevent.
_ANNUAL_RE = re.compile(
    r"(per\s*year|a\s*year|/\s*year|yearly|annual|annually|per\s*annum|salana|"
    r"prati\s*varsh|प्रति\s*वर्ष|प्रति\s*साल|वर्ष|सालाना|ਸਾਲਾਨਾ|ਪ੍ਰਤੀ\s*ਸਾਲ)"
)


def _income_period(text: str, span: tuple[int, int]) -> str | None:
    """Decide whether an income figure is monthly or annual.

    Only the text immediately around the figure is considered. The previous
    implementation searched the WHOLE description for the token "year", so an
    unrelated age mention ("Sunita is 45 years old ... earns 6000 a month")
    suppressed the monthly conversion and recorded ₹6,000 as an ANNUAL income.
    """
    start, end = span
    window = text[max(0, start - 40): min(len(text), end + 40)]
    if _MONTHLY_RE.search(window):
        return "month"
    if _ANNUAL_RE.search(window):
        return "year"
    return None


_NAME_STOPWORDS = {
    "a", "an", "the", "she", "he", "his", "her", "they", "this", "that", "one",
    "person", "citizen", "applicant", "operator", "mr", "mrs", "ms", "shri", "smt",
    "there", "we", "i", "it", "today",
}


def _name(text: str) -> str | None:
    """Best-effort name extraction.

    An operator almost never writes "her name is Sarita" — they open with the
    name ("Sarita Devi is a 45 year old widow", "Gurmeet Singh, 52, ..."). The
    old pattern only handled the explicit "name is X" form, so the README's own
    flagship example extracted no name at all.
    """
    m = re.search(
        r"(?:name is|named|naam|called)\s+([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,2})", text
    )
    if m:
        return m.group(1).strip()

    # Leading proper noun, confirmed by what follows it ("X is ...", "X, 52, ...").
    m = re.match(
        r"\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})(?=\s*,|\s+(?:is|was|ji|bhai|hai|aged|umar)\b)",
        text,
    )
    if m:
        candidate = m.group(1).strip()
        if candidate.split()[0].lower() not in _NAME_STOPWORDS:
            return candidate
    return None


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

    # gender — strongest evidence first.
    #
    # "husband"/"wife"/"brother" are deliberately absent: they describe a
    # RELATION, not the subject. "Kamla Devi ... her husband died" is a woman,
    # and reading "husband" as male evidence gets her exactly backwards. The
    # pronoun is the more reliable signal there, so relations are left out
    # entirely and pronouns act as the fallback tier.
    if re.search(_w("woman", "female", "lady", "girl", "daughter", "beti", "mahila",
                    "widow", "widowed", "vidhwa", "mother", "pregnant",
                    "महिला", "विधवा", "बेटी", "ਔਰਤ", "ਧੀ"), t):
        p.gender = "female"
    elif re.search(_w("man", "male", "boy", "son", "beta", "father",
                      "पुरुष", "बेटा", "ਆਦਮੀ", "ਮੁੰਡਾ"), t):
        p.gender = "male"
    elif re.search(_w("she", "her", "hers"), t):
        p.gender = "female"
    elif re.search(_w("he", "his", "him"), t):
        p.gender = "male"

    # income — the period is read from the text AROUND the figure, never from
    # the whole description (see _income_period).
    inc = re.search(
        r"(?:income|earns?|earning|salary|wage|kamata|kamai|आय|ਆਮਦਨ)[^\d]{0,20}"
        r"([\d,\.]+\s*(?:lakh|lac|crore|thousand|k|hazaar)?)",
        t,
    )
    if inc:
        val = _num(inc.group(1))
        if val is not None:
            period = _income_period(t, inc.span(1))
            if period == "month":
                val *= 12
            elif period is None:
                # Unstated period. Do NOT guess by magnitude: multiplying by 12
                # on a hunch can turn a genuine ₹40,000/year into ₹4.8 lakh and
                # silently disqualify the poorest citizens from income-capped
                # schemes like Ayushman Bharat. Recording the figure as-is keeps
                # the scheme visible; the flag tells the operator to confirm.
                p.flags.append("income_period_unstated")
            p.annual_income = val

    # occupation — pick the LONGEST matching keyword, not the first one in dict
    # order. "domestic worker" contains "worker", which is a labourer keyword,
    # so first-match ordering silently classified domestic workers as labourers.
    best: tuple[int, str, str] | None = None
    for norm, kws in _OCCUPATION_MAP.items():
        for kw in kws:
            if kw in t and (best is None or len(kw) > best[0]):
                best = (len(kw), norm, kw)
    if best:
        p.occupation = best[1]
        if best[1] == "student":
            p.is_student = True

    # category
    if re.search(_w("scheduled tribe", "st", "adivasi", "tribal", "अनुसूचित जनजाति"), t):
        p.category = "st"
    elif re.search(_w("scheduled caste", "sc", "dalit", "अनुसूचित जाति"), t):
        p.category = "sc"
    elif re.search(_w("obc", "other backward", "backward class", "पिछड़ा"), t):
        p.category = "obc"
    elif re.search(_w("general", "upper caste", "सामान्य"), t):
        p.category = "general"

    # area
    if re.search(_w("rural", "village", "villages", "gaon", "pind", "गांव", "गाँव", "ਪਿੰਡ"), t):
        p.area = "rural"
    elif re.search(_w("urban", "city", "town", "shehar", "sheher", "shahar", "nagar",
                      "शहर", "ਸ਼ਹਿਰ"), t):
        p.area = "urban"

    # bpl — "below poverty line" is usually written with an article ("below THE
    # poverty line"), which the old adjacent-word pattern could not match.
    if re.search(r"below\s+(?:the\s+)?poverty", t) or re.search(
        _w("bpl", "poor", "garib", "gareeb", "antyodaya", "गरीब", "ਗਰੀਬ"), t
    ):
        p.is_bpl = True

    # disability
    dis = re.search(r"(\d{1,3})\s*%?\s*(?:disab|divyang|handicap)", t)
    if not dis:
        dis = re.search(r"(?:disab|divyang|handicap)[^\d]{0,15}(\d{1,3})\s*%", t)
    if dis:
        pct = int(dis.group(1))
        if 0 < pct <= 100:
            p.disability_percent = pct
    elif re.search(_w("disabled", "disability", "divyang", "handicapped", "handicap",
                      "blind", "deaf", "दिव्यांग", "ਦਿਵਿਆਂਗ"), t):
        # Disability is mentioned but NOT quantified. Do not invent a number:
        # IGNDPS requires 80%, so assuming the old default of 40% made the rule
        # FAIL, marked the scheme not_eligible, and dropped the disability
        # pension off the operator's screen entirely. Left unknown, the matcher
        # reports "likely" and the operator is asked to confirm the percentage.
        p.flags.append("disability_percent_unstated")

    # marital status
    if re.search(_w("widow", "widowed", "vidhwa", "विधवा", "ਵਿਧਵਾ"), t):
        p.marital_status = "widow"
        if p.gender is None:
            p.gender = "female"
    elif re.search(_w("married", "shaadi", "husband", "wife", "विवाहित", "ਵਿਆਹਿਆ"), t):
        p.marital_status = "married"
    elif re.search(_w("unmarried", "single", "अविवाहित"), t):
        p.marital_status = "single"

    # student
    if re.search(_w("student", "studying", "college", "school", "छात्र", "ਵਿਦਿਆਰਥੀ"), t) or re.search(
        r"class\s*\d+", t
    ):
        p.is_student = True

    # land holding
    land = re.search(r"([\d\.]+)\s*(?:acre|acres|bigha|hectare|killa|ekad)", t)
    if land:
        p.land_holding_acres = float(land.group(1))
    elif p.occupation == "farmer" and re.search(_w("land", "zameen", "khet", "jameen", "ਜ਼ਮੀਨ"), t):
        p.land_holding_acres = 1.0
        p.flags.append("land_holding_assumed")

    # pregnancy
    if re.search(_w("pregnant", "expecting", "garbhvati", "गर्भवती", "ਗਰਭਵਤੀ"), t):
        p.is_pregnant = True
        if p.gender is None:
            p.gender = "female"

    # children
    ch = re.search(r"(\d+)\s*(?:child|children|kids|bachche|बच्चे|ਬੱਚੇ)", t)
    if ch:
        p.num_children = int(ch.group(1))

    # extra flags
    if re.search(r"(?:breadwinner|earning member).{0,30}(?:died|death|expired|passed away)", t):
        p.flags.append("breadwinner_deceased")

    p.name = _name(text)

    # state
    for s in _STATES:
        if re.search(r"\b" + re.escape(s) + r"\b", t):
            p.state = s.title()
            break

    return p


# --- normalising the LLM's answer ----------------------------------------
# The prompt ASKS for normalised keywords, but nothing enforced it. An LLM that
# answers "Female", "Scheduled Caste" or "agriculture" instead of "female",
# "sc", "farmer" used to sail through _from_ai untouched and then silently fail
# the matcher's enum check — PM-KISAN would just vanish from a farmer's results
# with no error anywhere. Normalising here is what makes the rule base reachable.

_GENDER_SYNONYMS = {
    "female": ["female", "f", "woman", "women", "lady", "girl", "mahila", "महिला"],
    "male": ["male", "m", "man", "men", "boy", "पुरुष"],
    "other": ["other", "transgender", "trans", "third gender"],
}
_CATEGORY_SYNONYMS = {
    "sc": ["sc", "scheduled caste", "scheduled-caste", "dalit"],
    "st": ["st", "scheduled tribe", "scheduled-tribe", "adivasi", "tribal"],
    "obc": ["obc", "other backward class", "other backward classes", "backward class"],
    "general": ["general", "gen", "unreserved", "ur", "upper caste"],
}
_AREA_SYNONYMS = {
    "rural": ["rural", "village", "gaon", "pind", "countryside"],
    "urban": ["urban", "city", "town", "shehar", "shahar", "nagar", "metro"],
}
_MARITAL_SYNONYMS = {
    "widow": ["widow", "widowed", "widower", "vidhwa"],
    "married": ["married", "shaadi shuda", "vivahit"],
    "single": ["single", "unmarried", "never married", "divorced", "separated"],
}


def _canonical(value, synonyms: dict[str, list[str]]) -> str | None:
    if value in (None, ""):
        return None
    v = str(value).strip().lower()
    for canon, words in synonyms.items():
        if v in words:
            return canon
    for canon, words in synonyms.items():
        if any(w in v for w in words):
            return canon
    return None


def _canonical_occupation(value) -> str | None:
    if value in (None, ""):
        return None
    v = str(value).strip().lower().replace(" ", "_")
    if v in _OCCUPATION_MAP:
        return v
    v = v.replace("_", " ")
    best: tuple[int, str] | None = None
    for norm, kws in _OCCUPATION_MAP.items():
        for kw in kws:
            if kw in v and (best is None or len(kw) > best[0]):
                best = (len(kw), norm)
    return best[1] if best else None


def _coerce_int(value) -> int | None:
    if value in (None, "", True, False):
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _coerce_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    v = str(value).strip().lower()
    if v in ("true", "yes", "y", "1", "haan"):
        return True
    if v in ("false", "no", "n", "0", "nahi"):
        return False
    return None


def _from_ai(data: dict) -> CitizenProfile:
    """Coerce the LLM's JSON into a validated, NORMALISED profile."""
    if not isinstance(data, dict):
        return CitizenProfile()

    allowed = CitizenProfile.model_fields.keys()
    clean = {k: v for k, v in data.items() if k in allowed and v is not None}

    clean["gender"] = _canonical(clean.get("gender"), _GENDER_SYNONYMS)
    clean["category"] = _canonical(clean.get("category"), _CATEGORY_SYNONYMS)
    clean["area"] = _canonical(clean.get("area"), _AREA_SYNONYMS)
    clean["marital_status"] = _canonical(clean.get("marital_status"), _MARITAL_SYNONYMS)
    clean["occupation"] = _canonical_occupation(clean.get("occupation"))

    for f in ("age", "annual_income", "disability_percent", "num_children"):
        clean[f] = _coerce_int(clean.get(f))
    for f in ("is_bpl", "is_student", "is_pregnant"):
        clean[f] = _coerce_bool(clean.get(f))

    if clean.get("land_holding_acres") is not None:
        try:
            clean["land_holding_acres"] = float(str(clean["land_holding_acres"]).strip())
        except (TypeError, ValueError):
            clean["land_holding_acres"] = None

    # Sanity bounds — an out-of-range number is a hallucination, not a fact.
    if clean.get("age") is not None and not 0 < clean["age"] < 120:
        clean["age"] = None
    if clean.get("disability_percent") is not None and not 0 < clean["disability_percent"] <= 100:
        clean["disability_percent"] = None
    if clean.get("annual_income") is not None and clean["annual_income"] < 0:
        clean["annual_income"] = None

    if not isinstance(clean.get("flags"), list):
        clean["flags"] = []
    clean["flags"] = [str(f) for f in clean["flags"]]

    clean = {k: v for k, v in clean.items() if v is not None}
    try:
        return CitizenProfile(**clean)
    except Exception:
        return CitizenProfile()


def _merge(ai: CitizenProfile, rule: CitizenProfile) -> tuple[CitizenProfile, float, list[str]]:
    """Combine the two extractors.

    The LLM still wins an outright disagreement — it reads context the regexes
    cannot. But a disagreement is no longer silent: it is recorded as a
    `conflict:<field>` flag so the operator can see which facts the two
    extractors read differently, and it lowers the reported confidence.

    Returns (profile, agreement, conflicts).
    """
    merged = ai.model_dump()
    conflicts: list[str] = []
    agreed = comparable = 0

    for k, rule_val in rule.model_dump().items():
        if k == "flags":
            continue
        ai_val = merged.get(k)
        if ai_val in (None, "") and rule_val not in (None, ""):
            merged[k] = rule_val
        elif ai_val not in (None, "") and rule_val not in (None, ""):
            if k in _KEY_FIELDS:
                comparable += 1
                if str(ai_val).strip().lower() == str(rule_val).strip().lower():
                    agreed += 1
                else:
                    conflicts.append(f"conflict:{k}")

    merged["flags"] = sorted({*(ai.flags or []), *(rule.flags or []), *conflicts})
    agreement = (agreed / comparable) if comparable else 1.0
    return CitizenProfile(**merged), agreement, conflicts


# Flags meaning "we guessed, or we could not read this" — each one is a reason
# to trust the profile a little less.
_SOFT_FLAGS = {"income_period_unstated", "land_holding_assumed", "disability_percent_unstated"}


def _confidence(profile: CitizenProfile, agreement: float | None = None) -> float:
    """How much the operator should trust this profile, in [0, 1].

    This is NOT a probability of correctness — nothing here can measure that at
    runtime. It combines the two things we can actually observe:

      completeness  how many of the matcher's key fields we managed to fill.
      agreement     for fields BOTH extractors filled, how often they agreed.
                    Two independent extractors reaching the same answer is real
                    evidence; it is the only correctness signal available.

    Unresolved guesses and conflicts subtract. The previous version counted
    non-null fields only, so a fully-populated hallucination scored 1.0.
    """
    filled = sum(1 for f in _KEY_FIELDS if getattr(profile, f) not in (None, ""))
    completeness = filled / len(_KEY_FIELDS)

    score = completeness if agreement is None else 0.6 * completeness + 0.4 * agreement

    flags = profile.flags or []
    score -= 0.05 * sum(1 for f in flags if f in _SOFT_FLAGS)
    score -= 0.10 * sum(1 for f in flags if f.startswith("conflict:"))

    return round(min(1.0, max(0.0, score)), 2)


def extract_profile(text: str) -> tuple[CitizenProfile, str, float]:
    """Returns (profile, source, confidence)."""
    rule = _rule_based(text)
    ai_json = chat_json(_SYSTEM_PROMPT, f"Operator description:\n{text}")

    if ai_json:
        profile, agreement, _ = _merge(_from_ai(ai_json), rule)
        source = "groq"
        confidence = _confidence(profile, agreement)
    else:
        profile = rule
        source = "rule-based"
        confidence = _confidence(profile)

    return profile, source, confidence


def missing_fields(profile: CitizenProfile) -> list[str]:
    return [f for f in _KEY_FIELDS if getattr(profile, f) in (None, "")]
