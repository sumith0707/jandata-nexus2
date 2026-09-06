"""
Uses Gemini Flash (free tier) to map an unknown table's columns onto our
canonical schema. This replaces hardcoding column positions per report —
the whole point of this file existing is that it works on tables it has
never seen before.

Requires: GEMINI_API_KEY environment variable.
Get a free key at https://aistudio.google.com/apikey (no credit card needed).
"""

import os
import json
import re
from google import genai

CANONICAL_FIELD_GUIDE = """
Canonical fields you can map a column to:
- "district_name": names of Karnataka districts or administrative regions
- "year": a calendar or fiscal year
- "row_label": a category/crop/item label that is NOT a district (e.g. crop name, indicator name)
- "value": any numeric measurement column
- "ignore": serial numbers, decorative columns, or anything not useful as data
"""

PROMPT_TEMPLATE = """
You are helping map a messy government data table to a standard schema.

Table headers (may be noisy/OCR'd, could be missing): {headers}

Sample rows: {sample_rows}

{field_guide}

For EACH column index (starting at 0), return:
- "field": one of district_name, year, row_label, value, ignore
- if "field" is "value": also include "indicator" (a short snake_case name for what this
  measures, e.g. "area_sown_total_lakh_ha") and "unit" (e.g. "lakh hectares", "percent", "mm")

CRITICAL: every "value" column MUST get a DIFFERENT "indicator" name, even if the
header text repeats (e.g. multiple "Area Sown" sub-columns for irrigated/rainfed/total).
Look at surrounding column headers to disambiguate — e.g. use
"area_sown_irrigated_lakh_ha", "area_sown_rainfed_lakh_ha", "area_sown_total_lakh_ha"
instead of reusing "area_sown" three times. Two columns must never share an indicator name.

Respond with ONLY valid JSON, no markdown fences, no explanation. Format:
{{"0": {{"field": "row_label"}}, "1": {{"field": "value", "indicator": "...", "unit": "..."}}, ...}}
"""


MODEL_NAME = "gemini-3.6-flash"  # update here if Google renames/deprecates this model again


def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Get a free key at https://aistudio.google.com/apikey "
            "and set it as an environment variable before running this."
        )
    return genai.Client(api_key=api_key)


def _extract_json(text: str) -> dict:
    """Gemini sometimes wraps JSON in markdown fences despite instructions — strip them."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _dedupe_indicator_names(mapping: dict) -> dict:
    """
    Safety net: if Gemini still reuses an indicator name across columns
    despite the prompt instruction, suffix duplicates with _2, _3, etc.
    so no two columns collide in the database.
    """
    seen = {}
    for col_idx in sorted(mapping.keys(), key=int):
        spec = mapping[col_idx]
        if spec.get("field") == "value":
            indicator = spec.get("indicator", f"value_col_{col_idx}")
            if indicator in seen:
                seen[indicator] += 1
                spec["indicator"] = f"{indicator}_{seen[indicator]}"
            else:
                seen[indicator] = 1
    return mapping


def map_columns_with_gemini(headers: list, sample_rows: list) -> dict:
    """
    headers: list of column header strings (can include None/empty for unknown headers)
    sample_rows: list of lists — a few representative data rows

    Returns: {column_index_str: {"field": ..., "indicator": ..., "unit": ...}}
    """
    client = _get_client()
    prompt = PROMPT_TEMPLATE.format(
        headers=headers,
        sample_rows=sample_rows[:5],
        field_guide=CANONICAL_FIELD_GUIDE,
    )
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    mapping = _extract_json(response.text)
    return _dedupe_indicator_names(mapping)


if __name__ == "__main__":
    # Quick manual test — requires GEMINI_API_KEY to be set.
    test_headers = ["Sl. No.", "District", "Targeted Area", "Irrigated", "Rainfed", "Total", "% Coverage"]
    test_rows = [
        ["1", "Bagalkote", "3.11", "2.222", "0.977", "3.199", "103"],
        ["2", "Ballari", "1.64", "0.796", "0.372", "1.167", "71"],
    ]
    mapping = map_columns_with_gemini(test_headers, test_rows)
    print(json.dumps(mapping, indent=2))
