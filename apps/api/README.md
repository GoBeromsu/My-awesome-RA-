# My Awesome RA API

FastAPI backend for AI Agent service providing reference-grounded LaTeX paper writing.

## Features

- Evidence search via FAISS vector index
- Document parsing via Upstage SOLAR API
- Citation extraction

## Quick Start

```bash
# Install dependencies
uv sync

# Run server
uv run uvicorn src.main:app --reload
```

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/evidence/search` | Search evidence by query |
| POST | `/documents/parse` | Parse PDF via SOLAR API |
| POST | `/documents/index` | Index document to FAISS |
| GET | `/documents/{id}/chunks` | Get document chunks |
| POST | `/citations/extract` | Extract citation info |
| GET | `/health` | Health check |
