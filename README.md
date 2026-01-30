# My Awesome RA

AI Agent service for reference-grounded LaTeX paper writing.

Evidence Panel overlay for Overleaf CE that provides semantic search across your reference PDFs, powered by Upstage SOLAR API.

## Quick Start

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Docker](https://www.docker.com/) & Docker Compose
- [Node.js](https://nodejs.org/) 18+
- [Upstage API Key](https://console.upstage.ai/)

### 1. Clone & Setup

```bash
git clone --recursive https://github.com/yourusername/my-awesome-ra.git
cd my-awesome-ra

# Copy environment template
cp .env.example .env
# Edit .env and set UPSTAGE_API_KEY

# Run setup
./scripts/setup.sh
```

### 2. Run Development Server

```bash
# API server only
./scripts/dev.sh

# Or with Docker (full stack)
docker-compose -f deployment/docker-compose.dev.yml up
```

### 3. Test API

```bash
# Health check
curl http://localhost:8000/health

# Search evidence
curl -X POST http://localhost:8000/evidence/search \
  -H "Content-Type: application/json" \
  -d '{"query": "neural network architecture"}'
```

## Features

- **Evidence Search**: Semantic search across indexed reference PDFs
- **Document Parsing**: PDF parsing via Upstage Document Parse API
- **Citation Extraction**: Structured citation extraction from text
- **FAISS Indexing**: Fast vector similarity search

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Browser                        │
├─────────────────────────────────────────────────┤
│  Overleaf Web                                   │
│  ┌──────────┬────────────┬─────────────────┐   │
│  │ File Tree│   Editor   │ Evidence Panel  │   │
│  └──────────┴────────────┴─────────────────┘   │
├─────────────────────────────────────────────────┤
│  apps/api (FastAPI)     │   Upstage SOLAR API   │
│  :8000                  │                       │
│  ├─ /evidence/search    │◀── Embedding API      │
│  ├─ /documents/parse    │◀── Document Parse     │
│  └─ /citations/extract  │◀── Info Extraction    │
├─────────────────────────┴───────────────────────┤
│         FAISS Index    │    File Cache          │
└─────────────────────────────────────────────────┘
```

## Project Structure

```
my-awesome-ra/
├── overleaf/              # Overleaf CE (git submodule)
├── apps/api/              # FastAPI backend
├── packages/
│   ├── solar-client/      # SOLAR API wrapper
│   └── evidence-types/    # Shared TypeScript types
├── deployment/            # Docker Compose configs
├── scripts/               # Setup & dev scripts
└── data/                  # Local data (gitignored)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/evidence/search` | Search evidence by query |
| `POST` | `/documents/parse` | Parse PDF document |
| `POST` | `/documents/index` | Index document for search |
| `GET` | `/documents/{id}/chunks` | Get document chunks |
| `POST` | `/citations/extract` | Extract citations |
| `GET` | `/health` | Health check |

## Configuration

Environment variables (`.env`):

| Variable | Required | Description |
|----------|----------|-------------|
| `UPSTAGE_API_KEY` | Yes | Upstage API key |
| `VECTOR_STORE_PATH` | No | FAISS index path (default: `data/faiss`) |
| `CHUNK_SIZE` | No | Text chunk size (default: 500) |
| `CHUNK_OVERLAP` | No | Chunk overlap (default: 100) |

## Development

```bash
# Run tests
cd apps/api && uv run pytest

# Type check
cd apps/api && uv run mypy src

# Lint
cd apps/api && uv run ruff check src
```

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This license is required because the project integrates with [Overleaf Community Edition](https://github.com/overleaf/overleaf), which is licensed under AGPL-3.0. Any modifications or derivative works that interact with Overleaf must also be released under AGPL-3.0.

See [LICENSE](LICENSE) for the full license text.

## Acknowledgments

- [Overleaf](https://www.overleaf.com/) - LaTeX editor
- [Upstage](https://www.upstage.ai/) - SOLAR API
- [FAISS](https://github.com/facebookresearch/faiss) - Vector search
