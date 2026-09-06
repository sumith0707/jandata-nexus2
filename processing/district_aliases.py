"""OCR-aware Karnataka district name resolver."""

import re
import unicodedata
from rapidfuzz import process, fuzz

DISTRICT_ALIASES = {
    "Bagalkote": ["Bagalkot"],
    "Ballari": ["Bellary"],
    "Belagavi": ["Belgaum"],
    "Bengaluru Rural": ["Bangalore Rural", "Bengaluru Rural District", "Bangalore Rural District"],
    "Bengaluru Urban": ["Bangalore Urban", "BBMP", "Bengaluru Urban District", "Bengaluru (Urban)", "Bangalore (Urban)"],
    "Bengaluru South": ["Bangalore South", "Bengaluru South District"],
    "Bidar": [],
    "Chamarajanagara": ["Chamarajanagar", "Chamrajnagar"],
    "Chikkaballapur": ["Chikballapur", "Chikballapura", "Chikkaballapura"],
    "Chikkamangaluru": ["Chikmagalur", "Chikkamagaluru", "Chikmangaluru"],
    "Chitradurga": [],
    "Dakshina Kannada": ["Dakshin Kannada", "Dakshina Kannda", "Dakshina Kanmda", "Dakshina Kannnada", "D.K.", "DK", "South Kanara", "South Canara"],
    "Davanagere": ["Davangere"],
    "Dharwad": ["Dharwar"],
    "Gadag": [],
    "Hassan": [],
    "Haveri": [],
    "Kalaburagi": ["Kalburgi", "Gulbarga"],
    "Kodagu": ["Coorg"],
    "Kolar": [],
    "Koppal": [],
    "Mandya": [],
    "Mysuru": ["Mysore"],
    "Raichur": ["Raichuru"],
    "Ramanagara": ["Ramnagar"],
    "Shivamogga": ["Shimoga"],
    "Tumakuru": ["Tumkur"],
    "Udupi": [],
    "Uttara Kannada": ["Uttarkannada", "Uttar Kannada", "Uttara Kannda", "Uttara Kannnada", "North Kanara", "North Canara"],
    "Vijayanagara": ["Vijayanagar"],
    "Vijayapura": ["Bijapur"],
    "Yadgiri": ["Yadgir", "Yadagiri"],
}

DISTRICT_CODES = {"Dakshina Kannada": "575"}

_OCR_WORD_FIXES = {
    "kanmda": "kannada", "kannda": "kannada", "kannnada": "kannada",
    "uttarkannada": "uttara kannada", "dakshin kannada": "dakshina kannada",
    "dakshina kannda": "dakshina kannada", "dakshina kanmda": "dakshina kannada",
    "dakshina kannnada": "dakshina kannada", "chikkamagaluru": "chikkamangaluru",
    "chikmagalur": "chikkamangaluru", "chikballapur": "chikkaballapur",
    "chikballapura": "chikkaballapur", "kalburgi": "kalaburagi",
    "gulbarga": "kalaburagi", "bellary": "ballari", "belgaum": "belagavi",
    "davangere": "davanagere", "dharwar": "dharwad", "mysore": "mysuru",
    "shimoga": "shivamogga", "tumkur": "tumakuru", "ramnagar": "ramanagara",
    "yadgir": "yadgiri", "yadagiri": "yadgiri", "coorg": "kodagu",
    "bijapur": "vijayapura", "vijayanagar": "vijayanagara",
}

def _normalise(value):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    value = value.lower().strip()
    value = re.sub(r"^\s*\d+\s*[\|.\-:\]]\s*", "", value)
    value = re.sub(r"[^\w\s().&-]", " ", value)
    value = value.replace("(", " ").replace(")", " ")
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s+(district|dist\.?)$", "", value)
    tokens = [_OCR_WORD_FIXES.get(x, x) for x in value.split()]
    return " ".join(tokens)

_ALIAS_TO_CANONICAL = {}
for canonical, aliases in DISTRICT_ALIASES.items():
    _ALIAS_TO_CANONICAL[_normalise(canonical)] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[_normalise(alias)] = canonical

CANONICAL_NAMES = list(DISTRICT_ALIASES.keys())
_ALIAS_KEYS = list(_ALIAS_TO_CANONICAL.keys())

def clean_district_string(raw):
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return ""
    return re.sub(r"^\s*\d+\s*[\|.\-:\]]\s*", "", s).strip(" .,:;|[]")

def resolve_district(raw_name, min_score=80):
    cleaned = clean_district_string(raw_name)
    if not cleaned:
        return None, 0.0, "empty_input"

    key = _normalise(cleaned)
    if key in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[key], 1.0, "exact_alias"

    compact = re.sub(r"[^a-z]", "", key)
    if len(compact) < 5:
        return None, 0.0, "unresolved_short_input"

    rough = process.extract(key, _ALIAS_KEYS, scorer=fuzz.WRatio, limit=5)
    best_key, best_score = None, 0
    for candidate, _, _ in rough:
        score = max(fuzz.ratio(key, candidate), fuzz.WRatio(key, candidate), fuzz.token_set_ratio(key, candidate))
        if score > best_score:
            best_key, best_score = candidate, score

    threshold = 90 if len(compact) <= 6 else min_score
    if best_key is not None and best_score >= threshold:
        return _ALIAS_TO_CANONICAL[best_key], round(best_score / 100, 2), "fuzzy_match"

    return None, 0.0, "unresolved"
