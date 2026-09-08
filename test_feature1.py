from dotenv import load_dotenv
load_dotenv()

import pandas as pd

from processing.schema_mapper import map_columns_with_gemini
from processing.normalize_table import normalize_table
from processing.validate import validate


tests = [
    {
        "name": "District",
        "headers": ["District", "Rainfall"],
        "rows": [
            ["Shimoga", "1200"],
            ["Mysore", "950"],
            ["Bellary", "700"],
        ],
    },
    {
        "name": "Region",
        "headers": ["Region", "Rainfall"],
        "rows": [
            ["Malnad", "1200"],
            ["Coastal Karnataka", "1800"],
            ["North Karnataka", "700"],
        ],
    },
    {
        "name": "Hospital",
        "headers": ["Hospital", "Beds"],
        "rows": [
            ["KIMS", "500"],
            ["SDM Hospital", "300"],
        ],
    },
]


for test in tests:

    print("\n" + "=" * 60)
    print(test["name"])
    print("=" * 60)

    raw_df = pd.DataFrame(
        test["rows"],
        columns=test["headers"],
    )

    # 1. Groq
    mapping = map_columns_with_gemini(
        test["headers"],
        test["rows"],
    )

    print("Groq entity_type:")
    print(mapping.get("_entity_type"))
    print("Groq domain:")
    print(mapping.get("_domain"))

    # 2. Normalize
    normalized = normalize_table(
        raw_df=raw_df,
        column_mapping=mapping,
        source_document="feature1_test",
        source_page="test",
        default_year=2025,
        extraction_method="test",
        skip_rows=0,
    )

    print("\nNormalized:")
    print(
        normalized[
            [
                "entity_name",
                "entity_type",
                "domain",
                "entity_resolution_method",
                "confidence",
            ]
        ].to_string(index=False)
    )

    # 3. Validate
    validated = validate(normalized)

    print("\nAfter validation:")
    print(
        validated[
            [
                "entity_name",
                "entity_type",
                "domain",
                "confidence",
                "validation_flag",
                "validation_reason",
            ]
        ].to_string(index=False)
    )

    # 4. Verify entity type and domain did not change
    expected_type = mapping.get("_entity_type")
    expected_domain = mapping.get("_domain")

    actual_types = set(
        validated["entity_type"].dropna()
    )
    actual_domains = set(
        validated["domain"].dropna()
    )

    if actual_types == {expected_type} and actual_domains == {expected_domain}:
        print(
            f"\n[PASS]: type '{expected_type}' and domain '{expected_domain}' survived "
            "Groq -> normalize -> validate"
        )
    else:
        print(
            f"\n[FAIL]: expected type '{expected_type}', domain '{expected_domain}', "
            f"got types {actual_types}, domains {actual_domains}"
        )