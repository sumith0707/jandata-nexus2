"""
Optional FastAPI layer on top of Supabase — useful if you need custom logic
(e.g. the chatbot's query-then-summarize flow) beyond what Supabase's
auto-generated REST API can do directly. For simple reads, the frontend can
also just call Supabase directly using the anon key and skip this file.

Run: uvicorn api.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

import os
from fastapi import FastAPI, HTTPException, Query
from typing import Optional
from supabase import create_client

app = FastAPI(
    title="JanData Nexus API",
    description="Unified, provenance-aware access to Karnataka public data.",
    version="0.3.0",
)


def get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")  # read-only key, safe here
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set.")
    return create_client(url, key)


@app.get("/datasets")
def list_datasets():
    client = get_client()
    res = client.table("observations").select("source_document, extraction_method").execute()
    seen = {}
    for row in res.data:
        key = (row["source_document"], row["extraction_method"])
        seen[key] = seen.get(key, 0) + 1
    return [
        {"source_document": k[0], "extraction_method": k[1], "row_count": v}
        for k, v in seen.items()
    ]


@app.get("/entities/{entity_name}")
def get_entity(entity_name: str, year: Optional[int] = None, include_flagged: bool = Query(False)):
    client = get_client()
    q = client.table("observations").select("*").eq("entity_name", entity_name)
    if year:
        q = q.eq("year", year)
    if not include_flagged:
        q = q.eq("validation_flag", False)
    res = q.execute()
    if not res.data:
        raise HTTPException(status_code=404, detail=f"No data found for '{entity_name}'")
    return res.data


@app.post("/query")
def query_data(
    indicator: Optional[str] = None,
    entity_type: Optional[str] = None,
    year: Optional[int] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    include_flagged: bool = False,
):
    client = get_client()
    q = client.table("observations").select("*")
    if indicator:
        q = q.eq("indicator", indicator)
    if entity_type:
        q = q.eq("entity_type", entity_type)
    if year:
        q = q.eq("year", year)
    if min_value is not None:
        q = q.gte("value", min_value)
    if max_value is not None:
        q = q.lte("value", max_value)
    if not include_flagged:
        q = q.eq("validation_flag", False)
    res = q.execute()
    return {"count": len(res.data), "results": res.data}


@app.get("/")
def root():
    return {
        "message": "JanData Nexus API is running (Supabase-backed).",
        "docs": "/docs",
        "try": "/entities/Belagavi or /query?indicator=area_sown_total_lakh_ha",
    }
