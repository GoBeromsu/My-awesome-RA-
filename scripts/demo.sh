#!/bin/bash
# Demo startup script - Run this to start the full demo environment
# Usage: ./scripts/demo.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "  My Awesome RA - Demo Startup"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Check Docker
echo -n "Checking Docker... "
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker is not running!${NC}"
    echo "Please start Docker Desktop and try again."
    exit 1
fi
echo -e "${GREEN}OK${NC}"

# Step 2: Copy seed data to correct location
echo -n "Copying seed data... "
# ChromaDB expects data at data/chroma/
mkdir -p apps/api/data/chroma
mkdir -p apps/api/data/pdfs

# Copy ChromaDB files to data/chroma/
cp fixtures/seed/chroma.sqlite3 apps/api/data/chroma/ 2>/dev/null || true
cp -r fixtures/seed/6fc90039-61eb-4f74-b9a0-1057ee9db942 apps/api/data/chroma/ 2>/dev/null || true

# Copy PDFs
cp -r fixtures/seed/pdfs/* apps/api/data/pdfs/ 2>/dev/null || true
echo -e "${GREEN}OK${NC}"

# Step 3: Kill existing API server if any
echo -n "Checking port 8000... "
if lsof -i :8000 > /dev/null 2>&1; then
    echo -n "stopping existing process... "
    kill -9 $(lsof -t -i :8000) 2>/dev/null || true
    sleep 1
fi
echo -e "${GREEN}OK${NC}"

# Step 4: Load environment variables
echo -n "Loading environment... "
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}.env file not found!${NC}"
    echo "Please copy .env.example to .env and set UPSTAGE_API_KEY"
    exit 1
fi

# Step 5: Start API server
echo -n "Starting API server... "
cd apps/api
source .venv/bin/activate
nohup uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/api-server.log 2>&1 &
API_PID=$!
cd "$PROJECT_ROOT"

# Wait for API to be ready
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC} (PID: $API_PID)"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo -e "${RED}FAILED${NC}"
        echo "API server failed to start. Check /tmp/api-server.log"
        exit 1
    fi
done

# Step 6: Verify API endpoints
echo ""
echo "Verifying API endpoints..."
echo -n "  /health: "
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

echo -n "  /documents: "
DOCS=$(curl -s http://localhost:8000/documents)
DOC_COUNT=$(echo "$DOCS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total', len(d.get('documents', d))))" 2>/dev/null || echo "0")
echo -e "${GREEN}${DOC_COUNT} documents${NC}"

echo -n "  /evidence/search: "
SEARCH=$(curl -s -X POST http://localhost:8000/evidence/search \
    -H "Content-Type: application/json" \
    -d '{"query": "language model", "top_k": 3}')
RESULT_COUNT=$(echo "$SEARCH" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('results', [])))" 2>/dev/null || echo "0")
echo -e "${GREEN}${RESULT_COUNT} results${NC}"

# Step 7: Check Overleaf
echo ""
echo -n "Checking Overleaf... "
if curl -s http://localhost:80 > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}Not accessible (Docker may need time)${NC}"
fi

echo ""
echo "=========================================="
echo -e "  ${GREEN}Demo Ready!${NC}"
echo "=========================================="
echo ""
echo "  API Server:  http://localhost:8000"
echo "  Overleaf:    http://localhost:80"
echo ""
echo "  Login:       demo@example.com"
echo "  Password:    Demo@2024!Secure"
echo ""
echo "  To stop:     kill $API_PID"
echo "=========================================="
