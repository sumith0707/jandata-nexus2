"""
Table extraction from image files using img2table + Tesseract.
Input: a table image (PNG/JPG). Output: raw pandas DataFrame(s), unprocessed.
"""

from img2table.document import Image
from img2table.ocr import TesseractOCR


def extract_table_from_image(image_path: str, min_confidence: int = 50):
    """Returns a list of pandas DataFrames, one per table detected in the image."""
    img = Image(src=image_path)
    ocr = TesseractOCR(lang="eng")

    tables = img.extract_tables(
        ocr=ocr,
        implicit_rows=False,
        borderless_tables=False,
        min_confidence=min_confidence,
    )
    return [t.df for t in tables]
