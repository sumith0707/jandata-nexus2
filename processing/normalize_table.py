"""
Turns ANY raw table + a column_mapping (from processing/schema_mapper.py)
into canonical long-format rows:

entity_name | entity_type | year | indicator | value | unit |
source_document | source_page | extraction_method | confidence | extracted_at

This file has no knowledge of any specific report's layout — the column
mapping (from Gemini) tells it what each column means.

entity_type distinguishes rows about a district ("district") from rows
about something else, like a crop category ("row_label") — both are kept,
since not every table is district-shaped (e.g. the crop-summary tables in
this same report have no district column at all).
"""

import re
import pandas as pd
from datetime import datetime, timezone

from processing.district_aliases import resolve_district


def _try_parse_number(raw):
    """Return (value_or_None, confidence). Flags common OCR digit confusions."""
    if raw is None:
        return None, 0.0
    s = str(raw).strip()
    if s.lower() in ("nan", "none", ""):
        return None, 0.0
    if re.search(r"[a-zA-Z]", s):
        return None, 0.2
    s_clean = s.replace(",", "")
    try:
        return float(s_clean), 1.0
    except ValueError:
        return None, 0.1


def normalize_table(
    raw_df: pd.DataFrame,
    column_mapping: dict,
    source_document: str,
    source_page: str,
    default_year: int,
    extraction_method: str,
    skip_rows: int = 0,
) -> pd.DataFrame:
    """
    raw_df: raw table, positional columns (0, 1, 2, ...)
    column_mapping: {"0": {"field": "district_name"}, "1": {"field": "value", "indicator": ..., "unit": ...}, ...}
                    as returned by schema_mapper.map_columns_with_gemini
    skip_rows: number of header rows at the top of raw_df to skip (native Word
               tables usually have 1 literal header row; OCR'd images usually don't)
    """
    # normalize mapping keys to int
    mapping = {int(k): v for k, v in column_mapping.items()}

    entity_col = None
    entity_type = "row_label"
    year_col = None
    value_cols = []  # list of (col_idx, indicator, unit)

    for col_idx, spec in mapping.items():
        field = spec.get("field")
        if field == "district_name":
            entity_col = col_idx
            entity_type = "district"
        elif field == "row_label" and entity_col is None:
            entity_col = col_idx
            entity_type = "row_label"
        elif field == "year":
            year_col = col_idx
        elif field == "value":
            value_cols.append((col_idx, spec.get("indicator", f"value_col_{col_idx}"), spec.get("unit", "")))

    records = []
    df_rows = raw_df.iloc[skip_rows:].reset_index(drop=True)
    last_seen_entity_raw = None

    for _, row in df_rows.iterrows():
        entity_raw = row.iloc[entity_col] if entity_col is not None and entity_col < len(row) else None

        if pd.isna(entity_raw) or str(entity_raw).strip() == "":
            entity_raw = last_seen_entity_raw
        else:
            last_seen_entity_raw = entity_raw

        if entity_raw is None:
            continue

        entity_str = str(entity_raw).strip()
        if not entity_str or entity_str.lower() in ("nan", ""):
            continue

        if entity_type == "district":
            canonical, confidence, method = resolve_district(entity_raw)
            if canonical is None:
                canonical = f"UNRESOLVED:{entity_raw}"
        else:
            canonical = entity_str
            confidence, method = 1.0, "not_applicable"

        year_value = default_year
        if year_col is not None and year_col < len(row):
            parsed_year, _ = _try_parse_number(row.iloc[year_col])
            if parsed_year:
                year_value = int(parsed_year)

        for col_idx, indicator, unit in value_cols:
            if col_idx >= len(row):
                continue
            raw_value = row.iloc[col_idx]
            value, val_confidence = _try_parse_number(raw_value)
            if value is None:
                continue

            overall_confidence = round(min(confidence, val_confidence), 2)

            records.append({
                "entity_name": canonical,
                "entity_type": entity_type,
                "entity_resolution_method": method,
                "year": year_value,
                "indicator": indicator,
                "value": value,
                "unit": unit,
                "source_document": source_document,
                "source_page": source_page,
                "extraction_method": extraction_method,
                "confidence": overall_confidence,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            })

    return pd.DataFrame(records)
