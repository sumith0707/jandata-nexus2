"""OCR-aware validation layer; preserves the existing DB schema."""

import math
import pandas as pd


KNOWN_RANGES = {
    "pct_coverage": (0, 300),
    "pct_of_normal_coverage": (0, 300),
    "coverage_percent": (0, 300),
    "coverage_last_year_percent": (0, 300),
    "percent_of_normal_coverage": (0, 300),
}

GENERIC_RANGE = (0, 1_000_000)


def _is_finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _range_for_row(row):
    indicator = str(row.get("indicator", "")).strip().lower()

    if indicator in KNOWN_RANGES:
        return KNOWN_RANGES[indicator]

    unit = str(row.get("unit", "")).strip().lower()

    if (
        "%" in unit
        or "percent" in unit
        or "percentage" in unit
    ):
        return (0, 300)

    return GENERIC_RANGE


def validate(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["validation_flag"] = False
    df["validation_reason"] = ""

    if df.empty:
        return df

    for idx, row in df.iterrows():
        reasons = []

        entity = str(
            row.get("entity_name", "")
        )

        entity_type = str(
            row.get("entity_type", "")
        ).strip().lower()

        method = str(
            row.get("entity_resolution_method", "")
        ).lower()

        # Entity type must be present.
        if not entity_type:
            reasons.append("missing_entity_type")

        # Only an unresolved district is a hard entity error.
        #
        # Non-district entities such as hospitals, schools,
        # regions, universities, etc. should NOT be treated
        # as district-resolution failures.
        if (
            entity_type == "district"
            and entity.startswith("UNRESOLVED:")
        ):
            reasons.append("unresolved_entity")

        try:
            confidence = float(
                row.get("confidence", 1.0)
            )
        except (TypeError, ValueError):
            confidence = 0.0

        # Fuzzy matches are accepted; only genuinely weak/unresolved
        # rows are hard-flagged.
        if confidence < 0.35 and method in {
            "unresolved",
            "empty_input",
            "unresolved_short_input",
        }:
            reasons.append("very_low_confidence")

        value = row.get("value")

        if not _is_finite(value):
            reasons.append("invalid_numeric_value")
        else:
            numeric = float(value)

            lo, hi = _range_for_row(row)

            if not (lo <= numeric <= hi):
                reasons.append(
                    f"out_of_range({numeric:g})"
                )

        if reasons:
            df.at[idx, "validation_flag"] = True

            df.at[idx, "validation_reason"] = ";".join(
                reasons
            )

    # Duplicates are useful information, but they are NOT
    # automatically invalid.
    if {
        "entity_name",
        "year",
        "indicator",
    }.issubset(df.columns):

        dup_mask = df.duplicated(
            subset=[
                "entity_name",
                "year",
                "indicator",
            ],
            keep=False,
        )

        for idx in df.index[dup_mask]:
            existing = str(
                df.at[idx, "validation_reason"] or ""
            )

            if "duplicate_entry" not in existing:
                df.at[idx, "validation_reason"] = (
                    f"{existing};duplicate_entry"
                    if existing
                    else "duplicate_entry"
                )

    return df