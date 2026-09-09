"""
Uses Groq to map an unknown government-data table onto our canonical schema.

Groq is responsible for determining:
- which column contains the entity
- what type of entity it represents
- how each remaining column should be interpreted

Entity types are domain-agnostic. Examples:
district, region, state, city, school, hospital, highway,
government_scheme, university, etc.
"""
import json
import os
import re
import time
from groq import Groq, RateLimitError
ENTITY_TYPE_GUIDE = """
entity_type must describe WHAT the entity actually is based on the
table content and surrounding context.
Examples:
- district
- region
- state
- city
- village
- school
- university
- hospital
- highway
- government_scheme
- department
- municipality
- crop
- commodity
- indicator
- other
IMPORTANT:
- Do NOT infer entity_type solely from a column header.
- Use the entity names, sample values, table context, and other columns.
- "District" in a header is evidence, not absolute proof.
- Keep "district" and "region" separate.
- Do NOT create parent/child mappings such as region -> district.
- entity_type is NOT restricted to geographic entities.
"""
CANONICAL_FIELD_GUIDE = """
Canonical fields you can map a column to:
- "entity_name": the primary entity represented by each row
- "year": a calendar or fiscal year (plain integer, e.g. 2025)
- "date": a specific calendar date (e.g. "25.07.2025", "2025-07-25")
- "period": a named period that is not a plain year or date
  (e.g. "Kharif 2025-26", "Q2 FY24", "Rabi season")
- "row_label": a secondary category/item label that is NOT the primary entity
- "value": any numeric measurement column
- "ignore": serial numbers, decorative columns, or anything not useful as data
Only ONE column should normally be selected as entity_name.
Use "date" or "period" instead of "year" when the source's actual time
reference is more specific or doesn't reduce cleanly to a single year —
don't force a date/period into "year" if it would lose information.
"""
PROMPT_TEMPLATE = """
You are a precise government-data schema interpretation engine.
Your job is to understand the meaning and thematic domain of a table using ALL available contextual evidence.

Source document / Dataset title:
{source_document}

Surrounding section text / Context:
{doc_context}

Table headers:
{headers}

Sample rows:
{sample_rows}

{field_guide}
{entity_type_guide}

DOMAIN DETERMINATION INSTRUCTIONS:
Determine the primary thematic domain (e.g., "health", "agriculture", "education", "water_resources", "finance", "infrastructure", "demographics", "welfare", "environment", "employment", "transport", etc.) using all available contextual evidence in the following priority order:
1. Dataset/document title ({source_document})
2. Section headings and surrounding text context ({doc_context})
3. Dataset description/context
4. Indicator names
5. Column names
6. Other indicators/rows in the same dataset
7. The actual values and units where useful

CRITICAL CONSISTENCY RULE:
Indicators that represent the same concept must receive the same domain across different years, districts, rows, or records within the same dataset/source, unless the source explicitly demonstrates that the meaning of the indicator has changed.
The year, district, or numerical values of a row must NOT by themselves cause the domain to become null when the indicator's meaning is already clear from the surrounding dataset context.

NULL HANDLING RULES:
- Do NOT return null merely because an individual row or table slice lacks enough information.
- Use the broader document/table/dataset context to infer the domain.
- Return null (or JSON null) ONLY when there is genuinely insufficient contextual evidence in the entire dataset/source to determine the domain.
- Do not guess an unrelated domain simply to avoid null.

Return:
1. entity_column: the zero-based column index containing the primary entity
2. entity_type: the semantic type of that entity
3. entity_type_confidence: confidence from 0.0 to 1.0
4. entity_type_reason: a short explanation of why the entity type was selected
5. domain: the high-level subject area/domain (string or null if genuinely insufficient evidence)
6. a field mapping for EVERY column
For EACH column index:
- "field": one of entity_name, year, date, period, row_label, value, ignore
- if "field" is "value", also include:
  - "indicator": short snake_case name
  - "unit": appropriate unit if identifiable

CRITICAL RULES:
1. Determine entity_type and domain from CONTENT AND CONTEXT, not merely headers.
2. Do NOT assume that every table with a "District" header is necessarily a district dataset. Inspect the actual entity values.
3. "district" and "region" are different entity types.
4. Never create a region -> district relationship.
5. entity_type can be non-geographic: school, hospital, university, highway, government_scheme, etc.
6. Do not invent entities, years, measurements, or values.
7. Preserve the exact column indexes.
8. Return an entry for EVERY column.
9. Every value column must have a DIFFERENT indicator.
10. If OCR makes the entity ambiguous, lower entity_type_confidence rather than inventing an entity type.

Respond with ONLY valid JSON.
Format:
{{
  "_entity_column": 1,
  "_entity_type": "district",
  "_entity_type_confidence": 0.98,
  "_entity_type_reason": "The entity values are Karnataka district names.",
  "_domain": "agriculture",
  "0": {{"field": "ignore"}},
  "1": {{"field": "entity_name"}},
  "2": {{
      "field": "value",
      "indicator": "targeted_area",
      "unit": "hectares"
  }}
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
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start:end + 1])
def _compact_repeated_header_text(headers: list) -> list:
    """
    Merged-cell government tables often repeat a long descriptive prefix
    or suffix across every column header, e.g.:

        '2010- 11 - Enrolments classes I to V'
        '2011- 12 - Enrolments classes I to V'
        ...

    Sending that repeated text to Groq once per column burns tokens for
    zero extra information — Groq only needs the varying part (the year)
    plus the shared text ONCE for context. This strips the repeated
    prefix/suffix from each header, keeping only what actually
    distinguishes the columns.

    Headers that don't participate in the pattern (e.g. an unrelated
    entity-name column) are left untouched.
    """
    if not headers or len(headers) < 3:
        return headers

    str_headers = [str(h) if h is not None else "" for h in headers]
    split_headers = [h.split(" - ") for h in str_headers]

    # ---- Try a shared trailing (suffix) chunk first ----
    last_parts = [p[-1].strip() for p in split_headers if len(p) > 1]
    if last_parts:
        most_common = max(set(last_parts), key=last_parts.count)
        if last_parts.count(most_common) >= max(2, len(headers) // 2):
            compacted = []
            affected = 0
            for parts, original in zip(split_headers, str_headers):
                if len(parts) > 1 and parts[-1].strip() == most_common:
                    compacted.append(" - ".join(parts[:-1]).strip())
                    affected += 1
                else:
                    compacted.append(original)
            print(
                f" Compacted repeated header suffix "
                f"({affected} columns affected): \"{most_common}\""
            )
            return compacted

    # ---- Otherwise try a shared leading (prefix) chunk ----
    first_parts = [p[0].strip() for p in split_headers if len(p) > 1]
    if first_parts:
        most_common = max(set(first_parts), key=first_parts.count)
        if first_parts.count(most_common) >= max(2, len(headers) // 2):
            compacted = []
            for parts, original in zip(split_headers, str_headers):
                if len(parts) > 1 and parts[0].strip() == most_common:
                    compacted.append(" - ".join(parts[1:]).strip())
                else:
                    compacted.append(original)
            print(f" Compacted repeated header prefix: \"{most_common}\"")
            return compacted

    return str_headers
def _dedupe_indicator_names(mapping: dict) -> dict:
    """
    Safety net: if Groq reuses an indicator name across columns,
    suffix duplicates with _2, _3, etc.
    """
    seen = {}
    for col_idx in sorted(
        [k for k in mapping.keys() if str(k).isdigit()],
        key=int,
    ):
        spec = mapping[col_idx]
        if spec.get("field") == "value":
            indicator = spec.get(
                "indicator",
                f"value_col_{col_idx}",
            )
            if indicator in seen:
                seen[indicator] += 1
                spec["indicator"] = (
                    f"{indicator}_{seen[indicator]}"
                )
            else:
                seen[indicator] = 1
    return mapping
def _validate_entity_metadata(mapping: dict) -> dict:
    """
    Validate Groq's entity metadata without replacing it with
    header-based assumptions.
    """
    valid_entity_types = {
        "district",
        "region",
        "state",
        "city",
        "village",
        "school",
        "university",
        "hospital",
        "highway",
        "government_scheme",
        "department",
        "municipality",
        "crop",
        "commodity",
        "indicator",
        "other",
    }
    entity_type = str(
        mapping.get("_entity_type", "other")
    ).strip().lower()
    if entity_type not in valid_entity_types:
        entity_type = "other"
    mapping["_entity_type"] = entity_type
    try:
        confidence = float(
            mapping.get("_entity_type_confidence", 0.0)
        )
    except (TypeError, ValueError):
        confidence = 0.0
    mapping["_entity_type_confidence"] = round(
        max(0.0, min(1.0, confidence)),
        2,
    )
    if not mapping.get("_entity_type_reason"):
        mapping["_entity_type_reason"] = (
            "Entity type resolved from table content and context."
        )
    try:
        entity_column = int(mapping["_entity_column"])
    except (TypeError, ValueError):
        entity_column = None
    mapping["_entity_column"] = entity_column

    raw_domain = mapping.get("_domain", mapping.get("domain"))
    if raw_domain is None or str(raw_domain).strip().lower() in ("none", "null", ""):
        domain = None
    else:
        domain = str(raw_domain).strip().lower()
    mapping["_domain"] = domain

    return mapping

DOCUMENT_DOMAIN_PROMPT = """
You are determining the primary thematic domain of a government document,
based on its title and opening text.

Source document / filename: {source_document}

Opening text (first few paragraphs):
{sample_text}

Determine the primary domain (e.g. "agriculture", "health", "education",
"water_resources", "finance", "infrastructure", "demographics", "welfare",
"environment", "employment", "transport", etc.).

Return ONLY valid JSON: {{"domain": "agriculture"}}
If genuinely insufficient evidence, return {{"domain": null}}.
"""


def determine_document_domain(paragraphs: list, source_document: str = "") -> str | None:
    """
    One lightweight Groq call per document (not per table) to tag the
    overall domain for document_chunks, and to give table-level schema
    mapping a consistent doc_context so the same document doesn't get
    conflicting domains across its tables and its text.
    """
    if not paragraphs:
        return None

    client = _get_client()
    sample_text = " ".join(paragraphs[:5])[:1500]  # keep the call cheap

    prompt = DOCUMENT_DOMAIN_PROMPT.format(
        source_document=source_document or "Not specified",
        sample_text=sample_text,
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Return only the requested JSON object."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        result = _extract_json(response.choices[0].message.content)
        domain = result.get("domain")
        if domain is None or str(domain).strip().lower() in ("none", "null", ""):
            return None
        return str(domain).strip().lower()
    except Exception as e:
        print(f"      Document domain detection failed (non-fatal): {e}")
        return None


def map_columns_with_gemini(
    headers: list,
    sample_rows: list,
    source_document: str = "",
    doc_context: str = "",
) -> dict:
    """
    Kept with the original function name so downstream imports
    do not break.

    Returns column mappings plus entity metadata:
    {
        "_entity_column": 1,
        "_entity_type": "district",
        "_entity_type_confidence": 0.98,
        "_entity_type_reason": "...",
        "_domain": "health",
        "0": {"field": "ignore"},
        "1": {"field": "entity_name"},
        ...
    }
    """
    client = _get_client()

    headers = _compact_repeated_header_text(headers)

    prompt = PROMPT_TEMPLATE.format(
        source_document=source_document or "Not specified",
        doc_context=doc_context or "Not specified",
        headers=headers,
        sample_rows=sample_rows[:5],
        field_guide=CANONICAL_FIELD_GUIDE,
        entity_type_guide=ENTITY_TYPE_GUIDE,
    )
    max_retries = 6
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise domain-agnostic "
                            "data-schema interpretation engine. "
                            "Determine entity type from content and context. "
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
            break
        except RateLimitError as e:
            if attempt < max_retries - 1:
                wait_secs = 5 * (attempt + 1)
                print(f" Groq rate limit encountered. Retrying in {wait_secs} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_secs)
            else:
                raise e

    text = response.choices[0].message.content
    mapping = _extract_json(text)
    mapping = _validate_entity_metadata(mapping)
    mapping = _dedupe_indicator_names(mapping)
    return mapping