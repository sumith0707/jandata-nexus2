"""
Turns any raw table + Groq column mapping into canonical long-format rows.

Canonical output:

entity_name
entity_type
year
indicator
value
unit
source_document
source_page
extraction_method
confidence
extracted_at
"""

import re
from datetime import datetime, timezone

import pandas as pd

from processing.district_aliases import resolve_district


def _try_parse_number(raw):
    """Return (value_or_None, confidence)."""

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

    mapping = {
        int(k): v
        for k, v in column_mapping.items()
        if str(k).isdigit()
    }

    # ---------------------------------------------------------
    # Entity metadata comes directly from Groq.
    # ---------------------------------------------------------

    entity_col = column_mapping.get("_entity_column")
    entity_type = column_mapping.get(
        "_entity_type",
        "other",
    )

    entity_type_confidence = float(
        column_mapping.get(
            "_entity_type_confidence",
            0.0,
        )
    )
    domain = column_mapping.get(
        "_domain",
        "other",
    )

    domain_confidence = float(
        column_mapping.get(
            "_domain_confidence",
            0.0,
        )
    )

    

    if entity_col is not None:
        try:
            entity_col = int(entity_col)
        except (TypeError, ValueError):
            entity_col = None

    year_col = None

    value_cols = []

    for col_idx, spec in mapping.items():

        field = spec.get("field")

        if field == "year":
            year_col = col_idx

        elif field == "value":
            value_cols.append(
                (
                    col_idx,
                    spec.get(
                        "indicator",
                        f"value_col_{col_idx}",
                    ),
                    spec.get("unit", ""),
                )
            )

    # ---------------------------------------------------------
    # Fallback for malformed Groq responses.
    # This does NOT infer entity type from a header.
    # ---------------------------------------------------------

    if entity_col is None:

        for col_idx, spec in mapping.items():
            if spec.get("field") == "entity_name":
                entity_col = col_idx
                break

    # If Groq failed to identify an entity column, do not
    # silently manufacture one.
    if entity_col is None:
        return pd.DataFrame()

    records = []

    df_rows = (
        raw_df
        .iloc[skip_rows:]
        .reset_index(drop=True)
    )

    last_seen_entity_raw = None

    for _, row in df_rows.iterrows():

        entity_raw = (
            row.iloc[entity_col]
            if entity_col < len(row)
            else None
        )

        # Support merged cells / blank continuation rows.
        if (
            pd.isna(entity_raw)
            or str(entity_raw).strip() == ""
        ):
            entity_raw = last_seen_entity_raw
        else:
            last_seen_entity_raw = entity_raw

        if entity_raw is None:
            continue

        entity_str = str(entity_raw).strip()

        if not entity_str:
            continue

        if entity_str.lower() == "nan":
            continue

        # -----------------------------------------------------
        # District canonicalization is ONLY applied when
        # Groq explicitly resolved the entity as a district.
        # -----------------------------------------------------

        if entity_type == "district":

            canonical, resolution_confidence, resolution_method = (
                resolve_district(entity_raw)
            )

            if canonical is None:
                canonical = f"UNRESOLVED:{entity_raw}"

            entity_confidence = min(
                entity_type_confidence,
                resolution_confidence,
            )

        else:

            # Do NOT run district aliases on regions, states,
            # schools, hospitals, universities, etc.
            canonical = entity_str

            resolution_confidence = entity_type_confidence
            resolution_method = "groq_entity_type"
            entity_confidence = entity_type_confidence

        # -----------------------------------------------------
        # Year
        # -----------------------------------------------------

        year_value = default_year

        if (
            year_col is not None
            and year_col < len(row)
        ):

            parsed_year, _ = _try_parse_number(
                row.iloc[year_col]
            )

            if parsed_year:
                year_value = int(parsed_year)

        # -----------------------------------------------------
        # Values
        # -----------------------------------------------------

        for col_idx, indicator, unit in value_cols:

            if col_idx >= len(row):
                continue

            raw_value = row.iloc[col_idx]

            value, value_confidence = (
                _try_parse_number(raw_value)
            )

            if value is None:
                continue

            overall_confidence = round(
                min(
                    entity_confidence,
                    value_confidence,
                ),
                2,
            )

            records.append(
                {
                    "entity_name": canonical,

                    # IMPORTANT:
                    # entity_type is passed through unchanged.
                    "entity_type": entity_type,
                    "domain": domain,

                    "entity_resolution_method": (
                        resolution_method
                    ),

                   
                    "year": year_value,

                    "indicator": indicator,

                    "value": value,

                    "unit": unit,

                    "source_document": source_document,

                    "source_page": source_page,

                    "extraction_method": extraction_method,

                    "confidence": overall_confidence,

                    "extracted_at": (
                        datetime.now(timezone.utc)
                        .isoformat()
                    ),
                }
            )

    return pd.DataFrame(records)