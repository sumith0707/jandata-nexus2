"""
JanData Nexus API — the consumer-facing layer.
Run: uvicorn api.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

import sqlite3
from fastapi import FastAPI, HTTPException, Query
from typing import Optional

DB_PATH = "db/jandata.db"

app = FastAPI(
    title="JanData Nexus API",
    description="Unified, provenance-aware access to Karnataka public data.",
    version="0.2.0",
)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/datasets")
def list_datasets():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT source_document, extraction_method, COUNT(*) as row_count "
        "FROM observations GROUP BY source_document, extraction_method"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/entities/{entity_name}")
def get_entity(
    entity_name: str,
    year: Optional[int] = None,
    include_flagged: bool = Query(False),
):
    conn = get_conn()
    query = "SELECT * FROM observations WHERE entity_name = ?"
    params = [entity_name]
    if year:
        query += " AND year = ?"
        params.append(year)
    if not include_flagged:
        query += " AND validation_flag = 0"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No data found for '{entity_name}'")
    return [dict(r) for r in rows]


@app.post("/query")
def query_data(
    indicator: Optional[str] = None,
    entity_type: Optional[str] = None,
    year: Optional[int] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    include_flagged: bool = False,
):
    conn = get_conn()
    query = "SELECT * FROM observations WHERE 1=1"
    params = []
    if indicator:
        query += " AND indicator = ?"
        params.append(indicator)
    if entity_type:
        query += " AND entity_type = ?"
        params.append(entity_type)
    if year:
        query += " AND year = ?"
        params.append(year)
    if min_value is not None:
        query += " AND value >= ?"
        params.append(min_value)
    if max_value is not None:
        query += " AND value <= ?"
        params.append(max_value)
    if not include_flagged:
        query += " AND validation_flag = 0"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


@app.get("/")
def root():
    return {
        "message": "JanData Nexus API is running.",
        "docs": "/docs",
        "try": "/entities/Belagavi or /query?indicator=area_sown_total_lakh_ha",
    }
