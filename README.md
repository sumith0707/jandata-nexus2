# JanData Nexus 2 — Groq update

This version replaces Gemini with Groq for the dynamic schema-mapping step.

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your Groq key:

### Windows PowerShell

```powershell
$env:GROQ_API_KEY="your_key_here"
```

### macOS/Linux

```bash
export GROQ_API_KEY="your_key_here"
```

Optional model override:

```bash
$env:GROQ_MODEL="llama-3.3-70b-versatile"
```

Then run:

```bash
python pipeline.py data/raw/yourfile.docx
```

The rest of the pipeline is unchanged.

## What changed

- Removed `google-genai`
- Added `groq`
- `processing/schema_mapper.py` now calls Groq Chat Completions
- JSON mode is enabled so the schema mapper receives a JSON object
- `pipeline.py` logging now says Groq
- The existing `map_columns_with_gemini()` function name is intentionally preserved so no downstream imports break
