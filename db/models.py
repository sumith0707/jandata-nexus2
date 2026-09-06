"""
SQLite schema for validated data. One table, long format — every row is
one (entity, year, indicator) observation with full provenance.

entity_type lets you tell districts apart from other row types (crop
categories, scheme names, etc.) that different tables may use.
"""

import sqlite3
import pandas as pd

DB_PATH = "db/jandata.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_resolution_method TEXT,
    year INTEGER NOT NULL,
    indicator TEXT NOT NULL,
    value REAL,
    unit TEXT,
    source_document TEXT,
    source_page TEXT,
    extraction_method TEXT,
    confidence REAL,
    extracted_at TEXT,
    validation_flag INTEGER DEFAULT 0,
    validation_reason TEXT
);
"""


def init_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()


def load_dataframe(df: pd.DataFrame, db_path: str = DB_PATH):
    if df.empty:
        return
    conn = sqlite3.connect(db_path)
    df = df.copy()
    df["validation_flag"] = df["validation_flag"].astype(int)
    df.to_sql("observations", conn, if_exists="append", index=False)
    conn.close()
