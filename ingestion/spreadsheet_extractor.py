"""
Spreadsheet extraction utilities.

Supports:
- XLSX
- CSV

Returns raw pandas DataFrames.
Schema interpretation, normalization, and validation happen
later in the common pipeline.
"""

import pandas as pd


def extract_xlsx(xlsx_path: str):
    """
    Extract all sheets from an XLSX file.

    Returns:
        list[dict]:
            [
                {
                    "sheet": "Sheet1",
                    "data": DataFrame
                },
                ...
            ]
    """
    sheets = pd.read_excel(
        xlsx_path,
        sheet_name=None,
    )

    return [
        {
            "sheet": sheet_name,
            "data": df,
        }
        for sheet_name, df in sheets.items()
        if not df.empty
    ]


def extract_csv(csv_path: str):
    """
    Extract a CSV file into a pandas DataFrame.

    Returns:
        DataFrame
    """
    return pd.read_csv(csv_path)