**Project**: My Awesome RA
**Purpose**: AI Agent service for reference-grounded LaTeX paper writing
**License**: AGPL-3.0 (due to Overleaf CE dependency)

## Core Technologies
- Upstage SOLAR API (Embedding, Document Parse, Information Extraction)
- FastAPI + FAISS (Vector search backend)
- Overleaf CE (LaTeX editor with Evidence Panel module)

## Folder Structure (Fixed)

```
my-awesome-ra/
├── overleaf/                    # Overleaf CE (git submodule)
│   └── services/web/modules/
│       └── evidence-panel/      # Evidence Panel UI module (Phase 3)
│
├── apps/
│   └── api/                     # FastAPI backend
│       ├── src/
│       │   ├── main.py          # App entry point
│       │   ├── routers/         # API endpoints
│       │   ├── services/        # Business logic
│       │   └── models/          # Pydantic models
│       ├── tests/
│       ├── pyproject.toml       # uv dependencies
│       └── Dockerfile
│
├── packages/
│   ├── solar-client/            # SOLAR API Python wrapper
│   │   ├── solar_client/
│   │   └── pyproject.toml
│   │
│   └── evidence-types/          # Shared TypeScript types
│       ├── src/
│       └── package.json
│
├── deployment/
│   ├── docker-compose.yml       # Production
│   ├── docker-compose.dev.yml   # Development
│   └── docker-compose.overleaf.yml
│
├── scripts/
│   ├── setup.sh                 # Project setup
│   ├── dev.sh                   # Dev server
│   └── build-module.sh          # Build evidence panel
│
├── data/                        # .gitignore (except .gitkeep)
│   ├── embeddings/
│   ├── faiss/
│   └── parsed/
│
├── .claude/                     # Claude Code configuration
├── .env                         # Secrets (gitignored)
├── .env.example
├── spec.md                      # MVP specification
├── context.md                   # Project context
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/evidence/search` | Search evidence by query |
| POST | `/documents/parse` | Parse PDF via SOLAR API |
| POST | `/documents/index` | Index document to FAISS |
| GET | `/documents/{id}/chunks` | Get document chunks |
| POST | `/citations/extract` | Extract citation info |
| GET | `/health` | Health check |

## Development Commands

```bash
# Setup
./scripts/setup.sh

# Run API server
./scripts/dev.sh

# Run with Docker
docker-compose -f deployment/docker-compose.dev.yml up
```

## Problem Definition

### Core Problem
During multi-file LaTeX paper writing, it is difficult to maintain a **low-friction, durable mapping** between:
- **(a) the claim currently being written** and
- **(b) the exact evidence span inside reference PDFs that supports it**

### Solution
Evidence Panel integrated into Overleaf that provides:
1. **Manual search** (default): User triggers search with selected text
2. **Auto search** (optional): Automatic context-aware search on cursor move
