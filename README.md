# JanData Nexus — Prototype v2

Interoperability layer for fragmented Karnataka public data. No frontend —
this is a data pipeline + API. The Swagger docs page is your demo screen.

## What changed from v1

- Works on ANY `.docx`, not just one file's layout. Handles three content
  types automatically: plain text, native Word tables (no OCR needed), and
  embedded images (OCR'd via img2table + Tesseract).
- Column-to-schema mapping is no longer hardcoded per report. Gemini Flash
  (free tier) looks at each table's headers/sample rows and figures out
  what each column means.
- Schema renamed `district_name`→`entity_name` with an `entity_type` field,
  since not every table is district-shaped (e.g. crop-category summary
  tables have no district column at all).

## Setup

```bash
pip install -r requirements.txt
```

You also need Tesseract itself installed (separate from the Python package):
- Windows: https://github.com/UB-Mannheim/tesseract/wiki, then add its folder to PATH
- Mac: `brew install tesseract`
- Linux: `sudo apt-get install tesseract-ocr`

Get a free Gemini API key (no credit card): https://aistudio.google.com/apikey

Set it as an environment variable:
```bash
# Mac/Linux
export GEMINI_API_KEY=your_key_here

# Windows (PowerShell)
$env:GEMINI_API_KEY="your_key_here"
```
(See `.env.example` for the variable name.)

## Run the full pipeline (any docx)

```bash
python pipeline.py data/raw/yourfile.docx
```

This does, automatically:
1. Extracts plain text (saved for reference, not parsed into rows yet)
2. Extracts native Word tables → asks Gemini to map columns → normalizes → validates → stores
3. Extracts embedded images → OCR's each → asks Gemini to map columns → normalizes → validates → stores

## Run the API

```bash
uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. Try:
- `GET /entities/Belagavi`
- `POST /query?entity_type=district&indicator=area_sown_total_lakh_ha`
- `POST /query?entity_type=row_label` (non-district data, e.g. crop categories)

## Pipeline stages (file map)

| Stage | File |
|---|---|
| Docx text/native-table/image extraction | `ingestion/docx_extractor.py` |
| OCR table extraction from images | `ingestion/ocr.py` |
| Dynamic column-to-schema mapping (Gemini) | `processing/schema_mapper.py` |
| Entity resolution (district aliases) | `processing/district_aliases.py` |
| Generic normalization to canonical schema | `processing/normalize_table.py` |
| Validation | `processing/validate.py` |
| Database | `db/models.py` |
| API | `api/main.py` |
| Orchestration | `pipeline.py` |

## Testing note

`schema_mapper.py`'s actual Gemini API call was NOT tested in this build
environment (no network access to Google's API here). Everything downstream
of it — `normalize_table.py`, `validate.py`, `db/models.py`, `api/main.py` —
was tested end to end using a hand-written mapping that mimics what Gemini
should return, on the real district-wise sowing table from your file, and
produced correct values. Run `pipeline.py` yourself with a real
`GEMINI_API_KEY` to confirm the mapping step itself; if Gemini's JSON output
doesn't parse cleanly, check `_extract_json()` in `schema_mapper.py` first.

## Known limitations

- Plain text extracted from docx is saved to a `.txt` file but not parsed
  into structured rows — it's reference-only for now.
- Merged/blank cells in OCR'd tables carry forward the previous row's entity
  name as a best guess; `validate.py`'s duplicate check catches most
  resulting errors, but doesn't fix them — flagged rows need manual review.
- One Gemini call per detected table. A document with many tables makes
  many calls — still well within the free tier's daily limit for normal use,
  but worth knowing if you batch-process a large folder of documents at once.
- No cross-source join endpoint yet — add a second dataset and I can build
  a `/query/join` style endpoint that combines two indicator sources by
  entity + year.

## Adding a new source

Nothing to write per-source anymore — `pipeline.py` handles any docx.
For non-docx formats (PDF, XLSX, CSV), you'd add a new extractor in
`ingestion/` following the same pattern as `docx_extractor.py`, feeding
into the same `schema_mapper.py` → `normalize_table.py` → `validate.py`
→ `db.models` chain.
