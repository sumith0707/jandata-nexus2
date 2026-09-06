"""
Government report tables often have multi-row headers (a title banner,
a two-level header like "Area Sown" spanning "Irrigated/Rainfed/Total",
and sometimes a column-index reference row like "1 2 3 4..."). Blindly
assuming "row 0 is the header" or "there is no header" both fail on real
documents. This module inspects the table's actual content and figures
out where the header ends and real data begins — no per-report hardcoding.
"""

import re
import pandas as pd


def _is_numeric(value) -> bool:
    if value is None:
        return False
    s = str(value).strip().replace(",", "")
    if s == "" or s.lower() == "nan":
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def _looks_like_banner_row(row: pd.Series) -> bool:
    """A row where every non-null cell repeats the same text (title banners)."""
    non_null = [str(v).strip() for v in row.dropna()]
    if len(non_null) < 2:
        return False
    return len(set(non_null)) == 1


def _looks_like_index_row(row: pd.Series) -> bool:
    """A row like [_, _, 1, 2, 3, 4, ...] where values roughly match column position + 1."""
    matches, checked = 0, 0
    for col_idx, value in enumerate(row):
        if pd.isna(value) or str(value).strip() == "":
            continue
        checked += 1
        s = str(value).strip()
        if re.fullmatch(r"\d+", s) and int(s) == col_idx + 1:
            matches += 1
    return checked >= 2 and matches / checked >= 0.6


def detect_header_and_data_start(raw_df: pd.DataFrame):
    """
    Returns (headers: list[str], data_start_row: int)

    headers: one combined string per column, built from whichever rows
             look like header text (joined with " - " if multi-row).
    data_start_row: index of the first row that is real data.
    """
    n_cols = raw_df.shape[1]
    header_parts = [[] for _ in range(n_cols)]
    row_idx = 0

    while row_idx < len(raw_df):
        row = raw_df.iloc[row_idx]
        non_null = row.dropna()

        if len(non_null) == 0:
            row_idx += 1
            continue

        if _looks_like_banner_row(row):
            row_idx += 1
            continue

        if _looks_like_index_row(row):
            row_idx += 1
            continue

        numeric_count = sum(1 for v in non_null if _is_numeric(v))
        frac_numeric = numeric_count / len(non_null)

        if frac_numeric < 0.5:
            # treat as header content — but only pull in cells that are
            # themselves text; skip numeric fragments that leaked into an
            # otherwise-text row (this is what caused "...- 129|" pollution)
            for col_idx, value in enumerate(row):
                if pd.notna(value) and str(value).strip():
                    text = str(value).strip().replace("\n", " ")
                    if _is_numeric(text) or re.fullmatch(r"[\|\]\}\)]*\d+(\.\d+)?[\|\]\}\)]*", text):
                        continue
                    if text not in header_parts[col_idx]:  # avoid repeating identical sub-header
                        header_parts[col_idx].append(text)
            row_idx += 1
            continue

        # majority numeric -> this is the first real data row
        break

    headers = [" - ".join(parts) if parts else None for parts in header_parts]
    return headers, row_idx