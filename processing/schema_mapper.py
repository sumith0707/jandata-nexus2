"""
Uses Groq to map an unknown government-data table's columns onto our
canonical schema.

Requires: GROQ_API_KEY environment variable.
"""

import json
import os
import re

from groq import Groq


CANONICAL_FIELD_GUIDE = """
Canonical fields you can map a column to:

- "district_name": names of Karnataka districts or administrative regions
- "year": a calendar or fiscal year
- "row_label": a category/crop/item label that is NOT a district
  (e.g. crop name, indicator name)
- "value": any numeric measurement column
- "ignore": serial numbers, decorative columns, or anything not useful as data
"""


PROMPT_TEMPLATE = """
You are helping map a messy government data table to a standard schema.

Table headers (may be noisy/OCR'd, could be missing):
{headers}

Sample rows:
{sample_rows}

{field_guide}

For EACH column index (starting at 0), return:

- "field": one of district_name, year, row_label, value, ignore
- if "field" is "value": also include "indicator" (a short snake_case name
  for what this measures) and "unit" (e.g. "lakh hectares", "percent", "mm")

CRITICAL:
1. Every "value" column MUST get a DIFFERENT "indicator" name.
2. If headers repeat, use surrounding headers/sample values to disambiguate.
3. Never invent a district/year/value that is not represented by a column.
4. Preserve the column index exactly.
5. Return an entry for EVERY column.

Respond with ONLY valid JSON. No markdown fences. No explanation.

Format:
{{
  "0": {{"field": "row_label"}},
  "1": {{"field": "value", "indicator": "...", "unit": "..."}}
}}
"""


MODEL_NAME = os.environ.get("GROQ_MODEL", "groq/compound")


def _get_client():
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not set. Create a Groq API key and set it "
            "as an environment variable before running this."
        )

    return Groq(api_key=api_key)


def _extract_json(text: str) -> dict:
    """Handle occasional markdown fences or surrounding text."""
    text = (text or "").strip()

    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last-resort extraction of the outermost JSON object.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start:end + 1])


def _dedupe_indicator_names(mapping: dict) -> dict:
    """
    Safety net: if the model reuses an indicator name across columns,
    suffix duplicates with _2, _3, etc.
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
    Kept with the original function name so the rest of the pipeline
    does not need to change.

    headers: list of column header strings
    sample_rows: list of representative data rows

    Returns:
        {
            "column_index": {
                "field": "...",
                "indicator": "...",
                "unit": "..."
            }
        }
    """
    client = _get_client()

    prompt = PROMPT_TEMPLATE.format(
        headers=headers,
        sample_rows=sample_rows[:5],
        field_guide=CANONICAL_FIELD_GUIDE,
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise data-schema mapping engine. "
                    "Return only the requested JSON object."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content
    mapping = _extract_json(text)

    return _dedupe_indicator_names(mapping)


if __name__ == "__main__":
    test_headers = [
        "Sl. No.",
        "District",
        "Targeted Area",
        "Irrigated",
        "Rainfed",
        "Total",
        "% Coverage",
    ]

    test_rows = [
        ["1", "Bagalkote", "3.11", "2.222", "0.977", "3.199", "103"],
        ["2", "Ballari", "1.64", "0.796", "0.372", "1.167", "71"],
    ]

    mapping = map_columns_with_gemini(test_headers, test_rows)
    print(json.dumps(mapping, indent=2))
