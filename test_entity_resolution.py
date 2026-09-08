from dotenv import load_dotenv
load_dotenv()

from processing.schema_mapper import map_columns_with_gemini


test_cases = [
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
            ["District Hospital", "250"],
        ],
    },
    {
        "name": "School",
        "headers": ["School", "Students"],
        "rows": [
            ["Government High School", "450"],
            ["Karnataka Public School", "600"],
            ["Model School", "350"],
        ],
    },
    {
        "name": "Government Scheme",
        "headers": ["Scheme", "Beneficiaries"],
        "rows": [
            ["PM Kisan", "12000"],
            ["Ujjwala Yojana", "8500"],
            ["Ayushman Bharat", "6200"],
        ],
    },
]


for test in test_cases:

    print("\n" + "=" * 60)
    print(test["name"])
    print("=" * 60)

    mapping = map_columns_with_gemini(
        test["headers"],
        test["rows"],
    )

    print("Entity column:")
    print(mapping.get("_entity_column"))

    print("Entity type:")
    print(mapping.get("_entity_type"))

    print("Domain:")
    print(mapping.get("_domain"))

    print("Confidence:")
    print(mapping.get("_entity_type_confidence"))

    print("Reason:")
    print(mapping.get("_entity_type_reason"))

    print("Full mapping:")
    print(mapping)