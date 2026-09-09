"""
End-to-end pipeline for a .docx source file:

docx -> native tables -> schema map (Groq) -> normalize -> validate -> store
     -> embedded images -> OCR -> schema map (Groq) -> normalize -> validate -> store
     -> plain text -> saved as-is for reference

Run:
    python pipeline.py data/raw/yourfile.docx

Requires:
    GROQ_API_KEY environment variable
"""
from dotenv import load_dotenv

load_dotenv()

import json
import os
import sys

import pandas as pd

from ingestion.docx_extractor import (
    extract_embedded_images,
    extract_text_and_native_tables,
)

from ingestion.ocr import extract_table_from_image

from ingestion.pdf_extractor import (
    extract_pdf_text,
    extract_pdf_tables,
    render_pdf_pages,
)

from ingestion.spreadsheet_extractor import (
    extract_xlsx,
    extract_csv,
)

from ingestion.common import (
    ExtractedDocument,
    ExtractedTable,
)

from processing.schema_mapper import (
    map_columns_with_gemini,
    determine_document_domain,
)

from processing.normalize_table import normalize_table

from processing.table_structure import detect_header_and_data_start

from processing.text_chunker import chunk_paragraphs

from processing.validate import validate

from db.models import (
    init_db,
    load_dataframe,
    load_document_chunks,
)


def process_raw_table(
    raw_df,
    source_document,
    source_page,
    extraction_method,
    default_year,
    doc_context="",
    headers_already_known=False,
):
    """Shared logic for native tables and OCR'd image tables."""

    if headers_already_known:
        headers = list(raw_df.columns)
        data_start = 0
    else:
        headers, data_start = detect_header_and_data_start(raw_df)

    sample_rows = raw_df.iloc[data_start:data_start + 5].values.tolist()

    print(f" Detected headers: {headers}")
    print(f" Asking Groq to map columns for {source_page} ...")

    mapping = map_columns_with_gemini(
        headers,
        sample_rows,
        source_document=source_document,
        doc_context=doc_context,
    )

    print(
    " Entity resolution: "
    f"type={mapping.get('_entity_type')}, "
    f"column={mapping.get('_entity_column')}, "
    f"confidence={mapping.get('_entity_type_confidence')}"
)

    print(f" Mapping: {json.dumps(mapping)}") 

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
        print(f" -> no usable rows extracted from {source_page}")
        return None

    validated_df = validate(clean_df)

    flagged = validated_df["validation_flag"].sum()

    print(f" -> {len(validated_df)} rows, {flagged} flagged for review")

    return validated_df

def run_pipeline(
    source_path: str,
    default_year: int,
    source_document: str | None = None,
):
    if source_document is None:
        source_document = os.path.basename(source_path)

    init_db()

    extension = os.path.splitext(source_path)[1].lower()

    if extension not in {".docx", ".pdf", ".xlsx", ".csv"}:
        raise ValueError(
            f"Unsupported file format: {extension}. "
            "Supported formats: .docx, .pdf, .xlsx, .csv"
        )

    print(f"[1/3] Extracting {extension} source: {source_path} ...")

    if extension == ".docx":
        document = extract_text_and_native_tables(source_path)

    elif extension == ".pdf":
        pdf_pages = extract_pdf_text(source_path)
        pdf_tables = extract_pdf_tables(source_path)

        paragraphs = [
            page["text"]
            for page in pdf_pages
            if page["text"].strip()
        ]

        tables = []

        for table in pdf_tables:
            raw_df = pd.DataFrame(table["table"])

            if not raw_df.empty:
                tables.append(
                    ExtractedTable(
                        data=raw_df,
                        source_page=f"pdf-page-{table['page']}",
                        extraction_method="pdf_table",
                    )
                )

        document = ExtractedDocument(
            paragraphs=paragraphs,
            tables=tables,
        )

    elif extension == ".xlsx":
        sheets = extract_xlsx(source_path)

        tables = [
            ExtractedTable(
                data=sheet["data"],
                source_page=f"sheet-{sheet['sheet']}",
                extraction_method="xlsx",
            )
            for sheet in sheets
        ]

        document = ExtractedDocument(
            tables=tables,
        )

    else:  # .csv
        raw_df = extract_csv(source_path)

        document = ExtractedDocument(
            tables=[
                ExtractedTable(
                    data=raw_df,
                    source_page="csv",
                    extraction_method="csv",
                )
            ]
            if not raw_df.empty
            else []
        )

    paragraphs = document.paragraphs
    native_tables = document.tables

    print(
        f" -> {len(paragraphs)} paragraphs, "
        f"{len(native_tables)} tables"
    )

    # Keep the raw text dump for local debugging/inspection.
    os.makedirs("data/processed", exist_ok=True)

    with open(
        f"data/processed/{source_document}.text.txt",
        "w",
        encoding="utf-8",
    ) as f:
        f.write("\n".join(paragraphs))

    # Chunk narrative text and store it separately from structured
    # observations, for semantic search later (Feature 3).
    chunks = chunk_paragraphs(paragraphs)
    print(
        f" -> {len(chunks)} text chunks "
        f"(from {len(paragraphs)} paragraphs)"
    )

    print(" Determining document-level domain (single Groq call) ...")
    doc_domain = determine_document_domain(
        paragraphs,
        source_document=source_document,
    )
    print(f" -> domain: {doc_domain}")

    if chunks:
        load_document_chunks(
            chunks,
            source_document=source_document,
            domain=doc_domain,
        )

    # Give table-level schema mapping the same context, so a document's
    # tables and its narrative text land on a consistent domain.
    doc_context = " ".join(paragraphs[:5])[:1500]

    print(" [2/3] Processing structured tables ...")

    for table in native_tables:
        raw_df = (
            table.data
            if isinstance(table.data, pd.DataFrame)
            else pd.DataFrame(table.data)
        )

        validated_df = process_raw_table(
            raw_df,
            source_document=source_document,
            source_page=table.source_page,
            extraction_method=table.extraction_method,
            default_year=default_year,
            doc_context=doc_context,
            headers_already_known=table.extraction_method in {"csv", "xlsx"},
        )

        if validated_df is not None:
            load_dataframe(validated_df)

    # DOCX embedded images are handled by the existing OCR path.
    if extension == ".docx":
        print("[3/3] Processing embedded images (needs OCR) ...")

        image_paths = extract_embedded_images(
            source_path,
            "data/processed/extracted_images",
        )

        for img_path in image_paths:
            print(f" -> {img_path}")

            tables = extract_table_from_image(img_path)

            for i, raw_df in enumerate(tables):
                validated_df = process_raw_table(
                    raw_df,
                    source_document=source_document,
                    source_page=(
                        f"{os.path.basename(img_path)}-table-{i}"
                    ),
                    extraction_method="ocr_img2table",
                    default_year=default_year,
                    doc_context=doc_context,
                )

                if validated_df is not None:
                    load_dataframe(validated_df)

    print("\nDone. Query via: uvicorn api.main:app --reload")
if __name__ == "__main__":
    source_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "data/raw/Kharif26.docx"
    )

    run_pipeline(source_path, default_year=2025)