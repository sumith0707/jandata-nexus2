from dotenv import load_dotenv
load_dotenv()

import pandas as pd

from db.models import load_dataframe


test_df = pd.DataFrame([
    {
        "entity_name": "KIMS",
        "entity_type": "hospital",
        "entity_resolution_method": "groq_entity_type",
        "year": 2025,
        "indicator": "number_of_beds",
        "value": 500.0,
        "unit": "beds",
        "source_document": "feature1_test",
        "source_page": "test",
        "extraction_method": "test",
        "confidence": 0.99,
        "extracted_at": "2025-01-01T00:00:00+00:00",
        "validation_flag": False,
        "validation_reason": "",
    }
])

print("Inserting test row...")
load_dataframe(test_df)

print("✅ Successfully inserted into Supabase")
print("entity_type stored: hospital")