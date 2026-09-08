from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from processing.schema_mapper import map_columns_with_gemini
from processing.normalize_table import normalize_table
from processing.validate import validate


def test_multiyear_domain_consistency():
    print("============================================================")
    print("Test 1: Multi-Year Indicator Consistency (fully_immunized_children)")
    print("============================================================")
    
    # Document title context representing child health monitoring dataset
    source_doc = "Karnataka_Child_Health_Immunization_Report_2021_2023.docx"
    doc_context = "Annual progress report on maternal and child immunization across Karnataka districts."

    # Year 2021 Table (with full context)
    headers_2021 = ["District", "Fully Immunized Children (Count)"]
    rows_2021 = [["Belagavi", "45200"], ["Mysuru", "38900"]]

    mapping_2021 = map_columns_with_gemini(
        headers=headers_2021,
        sample_rows=rows_2021,
        source_document=source_doc,
        doc_context=doc_context,
    )
    domain_2021 = mapping_2021.get("_domain")
    print(f"2021 Table Domain: {domain_2021}")

    # Year 2022 Table (minimal header/slice, exact same indicator concept)
    headers_2022 = ["District", "fully_immunized_children"]
    rows_2022 = [["Belagavi", "46100"], ["Mysuru", "39500"]]

    mapping_2022 = map_columns_with_gemini(
        headers=headers_2022,
        sample_rows=rows_2022,
        source_document=source_doc,
        doc_context=doc_context,
    )
    domain_2022 = mapping_2022.get("_domain")
    print(f"2022 Table Domain: {domain_2022}")

    # Year 2023 Table
    headers_2023 = ["District", "fully_immunized_children"]
    rows_2023 = [["Belagavi", "47300"], ["Mysuru", "40200"]]

    mapping_2023 = map_columns_with_gemini(
        headers=headers_2023,
        sample_rows=rows_2023,
        source_document=source_doc,
        doc_context=doc_context,
    )
    domain_2023 = mapping_2023.get("_domain")
    print(f"2023 Table Domain: {domain_2023}")

    assert domain_2021 == "health", f"Expected 'health', got {domain_2021}"
    assert domain_2022 == "health", f"Expected 'health' for 2022, got {domain_2022}"
    assert domain_203 == "health" if False else domain_2023 == "health", f"Expected 'health' for 2023, got {domain_2023}"
    assert domain_2021 == domain_2022 == domain_2023, f"Inconsistent domains across years: {domain_2021}, {domain_2022}, {domain_2023}"

    print("[PASS] Multi-year consistency check passed: all years resolved to 'health'")

    print("\n============================================================")
    print("Test 2: Distinct Domains for Distinct Indicators")
    print("============================================================")

    # Agriculture dataset
    agri_doc = "Kharif_Crop_Sown_Area_Report.docx"
    agri_mapping = map_columns_with_gemini(
        headers=["District", "Crop", "Targeted Area (Ha)"],
        sample_rows=[["Haveri", "Paddy", "12500"]],
        source_document=agri_doc,
        doc_context="Department of Agriculture crop coverage statistics."
    )
    agri_domain = agri_mapping.get("_domain")
    print(f"Agriculture Table Domain: {agri_domain}")
    assert agri_domain == "agriculture", f"Expected 'agriculture', got {agri_domain}"

    # Education dataset
    edu_doc = "Primary_School_Enrolment_Statistics.docx"
    edu_mapping = map_columns_with_gemini(
        headers=["District", "Total Enrolment Classes I to V"],
        sample_rows=[["Kolar", "84300"]],
        source_document=edu_doc,
        doc_context="Department of Public Instruction school enrolment statistics."
    )
    edu_domain = edu_mapping.get("_domain")
    print(f"Education Table Domain: {edu_domain}")
    assert edu_domain == "education", f"Expected 'education', got {edu_domain}"

    assert agri_domain != edu_domain != domain_2021, "Distinct indicators incorrectly received identical domains"
    print("[PASS] Distinct domain resolution check passed")

    print("\n============================================================")
    print("Test 3: Genuinely Ambiguous Data Returns Null")
    print("============================================================")

    ambiguous_mapping = map_columns_with_gemini(
        headers=["Col_A", "Col_B"],
        sample_rows=[["X123", "99"]],
        source_document="Unknown_Unlabeled_Dump.csv",
        doc_context="No context available. Synthetic numerical values with arbitrary identifiers."
    )
    ambiguous_domain = ambiguous_mapping.get("_domain")
    print(f"Ambiguous Data Domain: {ambiguous_domain}")
    assert ambiguous_domain is None or ambiguous_domain in ("other", "null"), f"Expected None/other for ambiguous data, got {ambiguous_domain}"
    print("[PASS] Genuinely ambiguous data check passed")

    print("\n[SUCCESS] All multi-year and domain consistency tests passed successfully!")


if __name__ == "__main__":
    test_multiyear_domain_consistency()
