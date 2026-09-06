"""
End-to-end pipeline for a .docx source file:

docx -> [native tables] -> schema map (Gemini) -> normalize -> validate -> store
     -> [embedded images] -> OCR extract -> schema map (Gemini) -> normalize -> validate -> store
     -> [plain text] -> saved as-is for reference (not parsed into rows yet)

Run: python pipeline.py data/raw/yourfile.docx
Requires: GEMINI_API_KEY environment variable set.
"""

import sys
import os
import json

from ingestion.docx_extractor import extract_text_and_native_tables, extract_embedded_images
from ingestion.ocr import extract_table_from_image
from processing.schema_mapper import map_columns_with_gemini
from processing.normalize_table import normalize_table
from processing.validate import validate
from processing.table_structure import detect_header_and_data_start
from db.models import init_db, load_dataframe

import pandas as pd


def process_raw_table(raw_df, source_document, source_page, extraction_method, default_year):
    """Shared logic for both native tables and OCR'd image tables."""
    headers, data_start = detect_header_and_data_start(raw_df)
    sample_rows = raw_df.iloc[data_start:data_start + 5].values.tolist()

    print(f"      Detected headers: {headers}")
    print(f"      Asking Gemini to map columns for {source_page} ...")
    mapping = map_columns_with_gemini(headers, sample_rows)
    print(f"      Mapping: {json.dumps(mapping)}")

    clean_df = normalize_table(
        raw_df,
        column_mapping=mapping,
        source_document=source_document,
        source_page=source_page,
        default_year=default_year,
        extraction_method=extraction_method,
        skip_rows=data_start,
    )
    if clean_df.empty:
        print(f"      -> no usable rows extracted from {source_page}")
        return None

    validated_df = validate(clean_df)
    flagged = validated_df["validation_flag"].sum()
    print(f"      -> {len(validated_df)} rows, {flagged} flagged for review")
    return validated_df


def run_pipeline(docx_path: str, default_year: int):
    source_document = os.path.basename(docx_path)
    init_db()

    print(f"[1/3] Extracting text and native tables from {docx_path} ...")
    paragraphs, native_tables = extract_text_and_native_tables(docx_path)
    print(f"      -> {len(paragraphs)} paragraphs, {len(native_tables)} native tables")

    # save plain text for reference — not parsed into rows in this version
    os.makedirs("data/processed", exist_ok=True)
    with open(f"data/processed/{source_document}.text.txt", "w") as f:
        f.write("\n".join(paragraphs))

    print("[2/3] Processing native Word tables (no OCR needed, high confidence) ...")
    for i, table_rows in enumerate(native_tables):
        raw_df = pd.DataFrame(table_rows)
        validated_df = process_raw_table(
            raw_df,
            source_document=source_document,
            source_page=f"native-table-{i}",
            extraction_method="native_docx_table",
            default_year=default_year,
        )
        if validated_df is not None:
            load_dataframe(validated_df)

    print("[3/3] Processing embedded images (needs OCR) ...")
    image_paths = extract_embedded_images(docx_path, "data/processed/extracted_images")
    for img_path in image_paths:
        print(f"   -> {img_path}")
        tables = extract_table_from_image(img_path)
        for i, raw_df in enumerate(tables):
            validated_df = process_raw_table(
                raw_df,
                source_document=source_document,
                source_page=f"{os.path.basename(img_path)}-table-{i}",
                extraction_method="ocr_img2table",
                default_year=default_year,
            )
            if validated_df is not None:
                load_dataframe(validated_df)

    print("\nDone. Query via: uvicorn api.main:app --reload")


if __name__ == "__main__":
    docx_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/Kharif2025SeasonalConditionason25072025Eng.docx"
    run_pipeline(docx_path, default_year=2025)
