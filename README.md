# Güdel Terminology Checker

A lean, deterministic terminology-compliance PoC built from the supplied 24 November 2026 Güdel TermBank export.

## What works

- Imports and validates the real 315-record UTF-8/semicolon TermBank CSV.
- Extracts all 408 English entries, including 296 preferred and 112 forbidden terms.
- Flags 50 German records whose concatenated statuses cannot be mapped safely; these never become false violations.
- Checks pasted text with case-insensitive whole-word, phrase, Unicode and longest-overlap behavior.
- Returns concept-backed preferred replacements and zero-based, end-exclusive Unicode offsets.
- Searches the complete English glossary and its German concept labels.
- Extracts and checks `.docx` body paragraphs, tables, headers and footers.
- Extracts text-based PDFs and clearly flags PDFs without an extractable text layer.
- Previews repeated CSV imports using a SHA-256 checksum.
- Provides session-local check history and CSV-ready structured results through the API.

## Architecture

This tiny-app version uses the established Vercel pattern: a static, dependency-free frontend and a FastAPI serverless backend. The bundled source CSV is parsed at startup and remains the source of truth. This keeps the proof of concept transparent and deployable without operating a database.

The terminology engine lives in `api/engine.py` and is independent of document extraction. Document endpoints first produce plain text, then call the same engine used by the text API.

## Local setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest httpx
.venv/bin/uvicorn api.index:app --reload
```

Open `http://127.0.0.1:8000`. API documentation is available at `/docs` locally and in production.

## Tests

```bash
.venv/bin/pytest -q
```

Tests cover the real record counts, TermBank field parsing, boundaries, case-insensitivity, overlap resolution, replacement lookup and API offsets.

## API example

```bash
curl -X POST http://127.0.0.1:8000/api/v1/check/text \
  -H 'content-type: application/json' \
  -d '{"text":"Install the side guide.","language":"en-US"}'
```

Main endpoints:

- `POST /api/v1/check/text`
- `POST /api/v1/check/document`
- `GET /api/v1/checks/{id}`
- `GET /api/v1/checks/{id}/findings`
- `GET /api/v1/terms/search?q=...`
- `GET /api/v1/concepts/{id}`
- `POST /api/v1/imports/preview`
- `GET /api/v1/glossary/stats`
- `GET /api/v1/glossary/revisions`

## Known PoC limitations

- Hosted glossary edits and import commits are not persisted. Import preview is real, but durable revision management requires the next-stage Postgres/authentication layer.
- German checking remains inactive until TermBank can export one status per German expression.
- Word preview is readable extracted text rather than pixel-perfect Word rendering. Text boxes and embedded objects may be missed.
- PDF text is extracted, but the tiny-app frontend presents an HTML text preview rather than a full PDF.js coordinate overlay.
- OCR, authentication, automatic retention jobs and generated corrected `.docx` files are outside this PoC.
- Serverless in-memory check IDs can expire between requests; responses are complete enough for clients to retain results directly.

No document text is sent to an LLM or external AI service.

