"""
Validation layer — runs AFTER normalization, BEFORE the database.

Does not fix errors, only flags them for review. Since indicators are now
dynamic (Gemini names them per-table), we can't hardcode a range per
indicator ahead of time — instead we use generic sanity rules plus an
optional per-indicator override list you can grow over time.
"""

import pandas as pd

# Optional: tighten ranges for specific indicators you've seen before.
# Falls back to the generic rule below for any indicator not listed here.
KNOWN_RANGES = {
    "pct_coverage": (0, 300),
    "pct_of_normal_coverage": (0, 300),
}

GENERIC_RANGE = (0, 1_000_000)  # catches negative values and OCR garbage like misplaced decimals


def validate(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["validation_flag"] = False
    df["validation_reason"] = ""

    for idx, row in df.iterrows():
        reasons = []

        if str(row["entity_name"]).startswith("UNRESOLVED"):
            reasons.append("unresolved_entity")

        if row["confidence"] < 0.7:
            reasons.append("low_confidence")

        lo, hi = KNOWN_RANGES.get(row["indicator"], GENERIC_RANGE)
        if not (lo <= row["value"] <= hi):
            reasons.append(f"out_of_range({row['value']})")

        if reasons:
            df.at[idx, "validation_flag"] = True
            df.at[idx, "validation_reason"] = ";".join(reasons)

    dup_mask = df.duplicated(subset=["entity_name", "year", "indicator"], keep=False)
    df.loc[dup_mask, "validation_flag"] = True
    df.loc[dup_mask, "validation_reason"] = df.loc[dup_mask, "validation_reason"] + ";duplicate_entry"

    return df
