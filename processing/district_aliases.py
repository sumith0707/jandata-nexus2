"""
Canonical Karnataka district list + alias resolution.

Core entity-resolution piece: different source documents spell district
names differently. We map every variant to one canonical name.
"""

from rapidfuzz import process, fuzz

DISTRICT_ALIASES = {
    "Bagalkote": ["Bagalkot"],
    "Ballari": ["Bellary"],
    "Belagavi": ["Belgaum"],
    "Bengaluru Rural": ["Bangalore Rural", "Rural"],
    "Bengaluru Urban": ["Bangalore Urban", "BBMP", "Bengaluru (Urban)"],
    "Bengaluru South": ["Bangalore South"],
    "Bidar": [],
    "Chamarajanagara": ["Chamarajanagar", "Chamrajnagar"],
    "Chikkaballapur": ["Chikballapur", "Chikballapura"],
    "Chikkamangaluru": ["Chikmagalur", "Chikkamagaluru"],
    "Chitradurga": [],
    "Dakshina Kannada": ["Dakshin Kannada", "D.K.", "DK", "South Kanara"],
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
    "Uttara Kannada": ["Uttarkannada", "Uttar Kannada", "North Kanara"],
    "Vijayanagara": ["Vijayanagar"],
    "Vijayapura": ["Bijapur"],
    "Yadgiri": ["Yadgir"],
}

DISTRICT_CODES = {
    "Dakshina Kannada": "575",
    # add more as you encounter them in real sources
}

_ALIAS_TO_CANONICAL = {}
for canonical, aliases in DISTRICT_ALIASES.items():
    _ALIAS_TO_CANONICAL[canonical.lower().strip()] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower().strip()] = canonical

CANONICAL_NAMES = list(DISTRICT_ALIASES.keys())


def clean_district_string(raw: str) -> str:
    """Strip OCR/table junk like leading row numbers: '17|Kalburgi' -> 'Kalburgi'."""
    if raw is None:
        return ""
    s = str(raw).strip()
    for sep in ["|", "]", ")"]:
        if sep in s:
            parts = s.split(sep)
            s = parts[-1].strip()
    s = s.strip(" .")
    return s


def resolve_district(raw_name: str, min_score: int = 80):
    """
    Resolve a raw district string to a canonical name.
    Returns: (canonical_name_or_None, confidence_0_to_1, method)
    """
    cleaned = clean_district_string(raw_name)
    if not cleaned:
        return None, 0.0, "empty_input"

    key = cleaned.lower().strip()

    if key in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[key], 1.0, "exact_alias"

    choices = list(_ALIAS_TO_CANONICAL.keys())
    match = process.extractOne(key, choices, scorer=fuzz.WRatio)
    if match:
        matched_key, score, _ = match
        if score >= min_score:
            return _ALIAS_TO_CANONICAL[matched_key], round(score / 100, 2), "fuzzy_match"

    return None, 0.0, "unresolved"
