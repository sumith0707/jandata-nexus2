"""Normalize extracted tables into the existing JanData long-format schema."""

import re
from datetime import datetime, timezone
import pandas as pd
from processing.district_aliases import resolve_district

_MISSING = {"", "nan", "none", "null", "n/a", "na", "-", "—"}
_OCR_DIGIT_TRANSLATIONS = str.maketrans({"O":"0","o":"0","I":"1","l":"1","S":"5","s":"5","B":"8"})

def _try_parse_number(raw):
    """Parse normal numbers plus conservative OCR digit substitutions."""
    if raw is None:
        return None, 0.0
    s = str(raw).strip()
    if not s or s.lower() in _MISSING:
        return None, 0.0

    s = s.replace(",", "").replace("₹", "").replace("%", "").replace("−", "-").strip()

    try:
        return float(s), 1.0
    except ValueError:
        pass

    if re.fullmatch(r"[-+0-9OoIlSsBb.\s]+", s) and re.search(r"\d", s):
        repaired = re.sub(r"\s+", "", s.translate(_OCR_DIGIT_TRANSLATIONS))
        try:
            return float(repaired), 0.88
        except ValueError:
            pass

    repaired = re.sub(r"(?<=\d)\s+(?=\d)", "", s)
    try:
        return float(repaired), 0.82
    except ValueError:
        return None, 0.0

def normalize_table(raw_df, column_mapping, source_document, source_page,
                    default_year, extraction_method, skip_rows=0):
    if raw_df is None or raw_df.empty:
        return pd.DataFrame()

    mapping = {int(k): v for k, v in column_mapping.items()}
    entity_col, entity_type, year_col = None, "row_label", None
    value_cols = []

    for col_idx, spec in mapping.items():
        field = spec.get("field")
        if field == "district_name":
            entity_col, entity_type = col_idx, "district"
        elif field == "row_label" and entity_col is None:
            entity_col, entity_type = col_idx, "row_label"
        elif field == "year":
            year_col = col_idx
        elif field == "value":
            value_cols.append((col_idx, spec.get("indicator", f"value_col_{col_idx}"), spec.get("unit", "")))

    if not value_cols:
        return pd.DataFrame()

    records = []
    df_rows = raw_df.iloc[skip_rows:].reset_index(drop=True)
    last_seen_entity_raw = None

    for _, row in df_rows.iterrows():
        entity_raw = row.iloc[entity_col] if entity_col is not None and entity_col < len(row) else None

        if pd.isna(entity_raw) or str(entity_raw).strip().lower() in _MISSING:
            entity_raw = last_seen_entity_raw
        else:
            last_seen_entity_raw = entity_raw

        if entity_raw is None:
            continue

        entity_str = str(entity_raw).strip()
        if not entity_str or entity_str.lower() in _MISSING:
            continue

        if entity_type == "district":
            canonical, entity_confidence, method = resolve_district(entity_raw)
            if canonical is None:
                canonical = f"UNRESOLVED:{entity_str}"
                entity_confidence, method = 0.0, "unresolved"
        else:
            canonical, entity_confidence, method = entity_str, 1.0, "not_applicable"

        year_value = default_year
        if year_col is not None and year_col < len(row):
            parsed_year, _ = _try_parse_number(row.iloc[year_col])
            if parsed_year is not None and 1900 <= parsed_year <= 2100:
                year_value = int(parsed_year)

        for col_idx, indicator, unit in value_cols:
            if col_idx >= len(row):
                continue
            value, value_confidence = _try_parse_number(row.iloc[col_idx])
            if value is None:
                continue

            records.append({
                "entity_name": canonical,
                "entity_type": entity_type,
                "entity_resolution_method": method,
                "year": year_value,
                "indicator": str(indicator).strip(),
                "value": value,
                "unit": str(unit).strip(),
                "source_document": source_document,
                "source_page": source_page,
                "extraction_method": extraction_method,
                "confidence": round(min(entity_confidence, value_confidence), 2),
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            })

    return pd.DataFrame(records)
