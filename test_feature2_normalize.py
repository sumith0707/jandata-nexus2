import pandas as pd

from processing.normalize_table import normalize_table


raw_df = pd.DataFrame(
    [
        ["Bagalkot", 12, 450, 75, 120],
        ["Mysuru", 18, 800, 140, 250],
    ],
    columns=[
        "District",
        "Government Hospitals",
        "Beds",
        "Doctors",
        "Nurses",
    ],
)


column_mapping = {
    "_entity_column": 0,
    "_entity_type": "district",
    "_entity_type_confidence": 0.98,
    "_entity_type_reason": "The entity values are Karnataka district names.",
    "_domain": "health",
    "_domain_confidence": 0.98,

    "0": {
        "field": "entity_name"
    },
    "1": {
        "field": "value",
        "indicator": "government_hospitals",
        "unit": "count",
    },
    "2": {
        "field": "value",
        "indicator": "beds",
        "unit": "count",
    },
    "3": {
        "field": "value",
        "indicator": "doctors",
        "unit": "count",
    },
    "4": {
        "field": "value",
        "indicator": "nurses",
        "unit": "count",
    },
}


result = normalize_table(
    raw_df=raw_df,
    column_mapping=column_mapping,
    source_document="med_Data.docx",
    source_page="1",
    default_year=2025,
    extraction_method="native_table",
)


print("\n========== FEATURE 2 NORMALIZATION TEST ==========")
print(result.to_string(index=False))
print("\nColumns:")
print(list(result.columns))
print("===================================================")