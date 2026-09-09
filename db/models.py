"""
Supabase (Postgres) storage for validated observations.

Uses the SERVICE ROLE key — this file is only ever called from the
pipeline (server-side/your own machine), never from a frontend. The
frontend uses the anon key instead and only has read access, enforced
by the RLS policy in db/supabase_schema.sql.
"""

import os
import math
import pandas as pd
from supabase import create_client, Client

TABLE_NAME = "observations"
CHUNKS_TABLE_NAME = "document_chunks"


def _get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set as environment variables. "
            "See .env.example. Get these from Supabase dashboard -> Project Settings -> API."
        )
    return create_client(url, key)


def init_db():
    """
    No-op for Supabase — the table is created once via db/supabase_schema.sql
    run in the Supabase SQL Editor, not per pipeline run. Kept as a function
    so pipeline.py doesn't need to change.
    """
    pass


def _clean_for_json(record: dict) -> dict:
    """Postgres/JSON can't represent NaN — convert to None."""
    cleaned = {}
    for k, v in record.items():
        if isinstance(v, float) and math.isnan(v):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def load_dataframe(df: pd.DataFrame, batch_size: int = 500):
    """Insert a validated DataFrame into Supabase, in batches."""
    if df.empty:
        return

    client = _get_client()
    df = df.copy()
    df["validation_flag"] = df["validation_flag"].astype(bool)

    records = [_clean_for_json(r) for r in df.to_dict(orient="records")]

    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        client.table(TABLE_NAME).insert(batch).execute()


def load_document_chunks(chunks: list, source_document: str, domain: str = None, batch_size: int = 500):
    """
    Insert chunked narrative text into document_chunks.
    chunks: list of plain-text strings, in document order.
    """
    if not chunks:
        return

    client = _get_client()
    records = [
        {
            "source_document": source_document,
            "domain": domain,
            "chunk_text": chunk,
            "chunk_index": i,
        }
        for i, chunk in enumerate(chunks)
    ]

    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        client.table(CHUNKS_TABLE_NAME).insert(batch).execute()
