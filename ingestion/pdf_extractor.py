"""
PDF extraction utilities.

Handles:
- text-based PDF text extraction
- PDF table extraction
- scanned PDF pages via image rendering

The output is intentionally raw. Schema interpretation,
normalization, and validation happen later in the pipeline.
"""

import fitz
import pdfplumber
import pandas as pd


def extract_pdf_text(pdf_path: str):
    """
    Extract text from each PDF page.

    Returns:
        list[dict]:
            [
                {
                    "page": 1,
                    "text": "..."
                },
                ...
            ]
    """
    pages = []

    with fitz.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()

            pages.append(
                {
                    "page": page_number,
                    "text": text,
                }
            )

    return pages


def extract_pdf_tables(pdf_path: str):
    """
    Extract tables from a PDF using pdfplumber.

    Returns:
        list[dict]:
            [
                {
                    "page": 1,
                    "table": [[...], [...]]
                },
                ...
            ]
    """
    tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_tables = page.extract_tables()

            for table in page_tables:
                if table:
                    tables.append(
                        {
                            "page": page_number,
                            "table": table,
                        }
                    )

    return tables


def render_pdf_pages(pdf_path: str, output_dir: str):
    """
    Render PDF pages as PNG images.

    This is used for scanned PDFs or pages where normal
    text/table extraction does not produce useful content.

    Returns:
        list[dict]:
            [
                {
                    "page": 1,
                    "image_path": "..."
                },
                ...
            ]
    """
    import os

    os.makedirs(output_dir, exist_ok=True)

    rendered_pages = []

    with fitz.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            image_path = os.path.join(
                output_dir,
                f"page_{page_number}.png",
            )

            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            pixmap.save(image_path)

            rendered_pages.append(
                {
                    "page": page_number,
                    "image_path": image_path,
                }
            )

    return rendered_pages