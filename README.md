# My Awesome RA

> **AI Agent for Reference-Grounded LaTeX Paper Writing**
> Powered by [Upstage SOLAR API](https://console.upstage.ai/)

논문 작성 시 현재 문단에 맞는 참고문헌 근거를 자동으로 찾아주는 Evidence Panel을 Overleaf CE에 통합한 MVP 프로젝트입니다.

## Demo

![References Panel Demo](docs/images/demo.png)

## Features

| Feature | Description | Status |
|---------|-------------|--------|
| **Reference Library** | .bib 파일 기반 참고문헌 목록 관리 | ✅ 완료 |
| **PDF Upload & Index** | PDF 업로드 → SOLAR 파싱 → ChromaDB 인덱싱 | ✅ 완료 |
| **Evidence Search** | 현재 문단 기반 관련 근거 자동 검색 | ✅ 완료 |
| **Overleaf Integration** | Rail Panel로 통합된 UI | ✅ 완료 |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Overleaf CE                          │
│  ┌──────────────────┐    ┌────────────────────────────┐    │
│  │   LaTeX Editor   │    │    Evidence Panel          │    │
│  │  (CodeMirror)    │───▶│  - .bib 파일 파싱          │    │
│  │                  │    │  - PDF 업로드/인덱싱       │    │
│  └──────────────────┘    │  - Evidence 검색           │    │
│                          └────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   /evidence  │  │  /documents  │  │  /citations  │      │
│  │    /search   │  │   /upload    │  │   /extract   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         ▼                 ▼                 ▼               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Upstage SOLAR API                      │   │
│  │  • Embedding (solar-embedding-1-large, 4096-dim)    │   │
│  │  • Document Parse                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────┐                                          │
│  │  ChromaDB    │  (persistent vector store)               │
│  └──────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- [Upstage API Key](https://console.upstage.ai/)

### One-Command Demo (Recommended)

```bash
# Clone
git clone --recursive https://github.com/GoBeromsu/my-awesome-ra.git
cd my-awesome-ra

# Environment
cp .env.example .env
# Edit .env and set UPSTAGE_API_KEY

# Start demo (auto-initializes everything)
cd deployment && docker compose --profile demo up

# Access: http://localhost
# Login: demo@example.com / Demo@2024!Secure
```

### Development Mode

```bash
# With webpack hot reload
cd deployment && docker compose --profile dev up

# Access: http://localhost (Overleaf)
# API: http://localhost:8000 (FastAPI)
# Webpack: http://localhost:3808
```

### Manual Setup (Advanced)

```bash
# Install API dependencies
cd apps/api && uv sync

# Run API server
uv run uvicorn src.main:app --reload --port 8000

# Run Overleaf (in another terminal)
cd overleaf/develop && bin/dev web webpack
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/documents` | List indexed documents |
| `POST` | `/documents/parse` | Parse PDF (SOLAR API) |
| `POST` | `/documents/index` | Index to ChromaDB |
| `GET` | `/documents/{id}/chunks` | Get document chunks |
| `DELETE` | `/documents/{id}` | Remove from index |
| `POST` | `/evidence/search` | Search evidence by query |

## Project Structure

```
my-awesome-ra/
├── apps/api/                      # FastAPI Backend
│   └── src/
│       ├── routers/               # API endpoints
│       ├── services/              # SOLAR, ChromaDB, Embedding
│       └── models/                # Pydantic schemas
│
├── overleaf/                      # Forked Overleaf CE (submodule)
│   └── services/web/modules/
│       └── evidence-panel/        # Evidence Panel Module
│           ├── frontend/js/
│           │   ├── components/    # React UI
│           │   ├── contexts/      # State management
│           │   └── hooks/         # Custom hooks
│           └── stylesheets/
│
├── deployment/                    # Docker Compose files
│   └── docker-compose.dev.yml     # Development environment
│
├── fixtures/
│   ├── latex/                     # Demo LaTeX files
│   └── seed/                      # Pre-built ChromaDB index (29 papers)
│
└── scripts/
    ├── regenerate_seed.py         # Seed data regenerator
    └── setup-demo.sh              # Demo user/project setup
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| **AI/ML** | Upstage SOLAR (Embedding 4096-dim, Document Parse) |
| **Backend** | FastAPI, ChromaDB, Python 3.11 |
| **Frontend** | React 18, TypeScript, CodeMirror 6 |
| **Editor** | Overleaf Community Edition |
| **Infra** | Docker Compose, uv |

## Credentials

| Environment | Email | Password |
|-------------|-------|----------|
| Demo | `demo@example.com` | `Demo@2024!Secure` |

## License

AGPL-3.0 (Overleaf CE 호환)

---

Built with [Upstage SOLAR API](https://console.upstage.ai/) | [GoBeromsu](https://github.com/GoBeromsu)
