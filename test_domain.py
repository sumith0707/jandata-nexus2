from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from processing.normalize_table import normalize_table
from processing.validate import validate

def test_domain_flow():
    print("Testing domain field flow through normalization and validation...")
    
    mock_mapping = {
        "_entity_column": 0,
        "_entity_type": "district",
        "_entity_type_confidence": 0.95,
        "_entity_type_reason": "District names",
        "_domain": "agriculture",
        "0": {"field": "entity_name"},
        "1": {"field": "value", "indicator": "sown_area", "unit": "ha"}
    }

    raw_df = pd.DataFrame([
        ["Shimoga", "1000"],
        ["Mysore", "800"]
    ], columns=["District", "Sown Area"])

    normalized = normalize_table(
        raw_df=raw_df,
        column_mapping=mock_mapping,
        source_document="test_doc.docx",
        source_page="page_1",
        default_year=2025,
        extraction_method="test_method"
    )

    assert "domain" in normalized.columns, "Domain column missing from normalized DataFrame"
    assert (normalized["domain"] == "agriculture").all(), f"Expected domain 'agriculture', got {normalized['domain'].unique()}"
    print(" -> Normalization test passed: domain correctly populated as 'agriculture'")

    validated = validate(normalized)
    assert "domain" in validated.columns, "Domain column missing from validated DataFrame"
    assert (validated["domain"] == "agriculture").all()
    assert (validated["validation_flag"] == False).all()
    print(" -> Validation test passed: domain field preserved with no validation flags")

    print("[SUCCESS] All domain flow tests passed successfully!")

if __name__ == "__main__":
    test_domain_flow()
