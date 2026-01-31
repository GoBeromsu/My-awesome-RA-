#!/bin/bash
# Package Demo Script - Creates a self-contained demo archive
# Usage: ./scripts/package-demo.sh
#
# Output: my-awesome-ra-demo.tar.gz

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "  My Awesome RA - Demo Packager"
echo "=========================================="
echo ""

# Configuration
PACKAGE_DIR="$PROJECT_ROOT/demo-package"
OUTPUT_FILE="$PROJECT_ROOT/my-awesome-ra-demo.tar.gz"

# Step 1: Clean previous build
echo -n "Cleaning previous build... "
rm -rf "$PACKAGE_DIR/data" "$PACKAGE_DIR/api/src" "$PACKAGE_DIR/api/pyproject.toml" "$PACKAGE_DIR/api/uv.lock" 2>/dev/null || true
echo -e "${GREEN}OK${NC}"

# Step 2: Create directory structure
echo -n "Creating directory structure... "
mkdir -p "$PACKAGE_DIR/data/chroma"
mkdir -p "$PACKAGE_DIR/data/pdfs"
mkdir -p "$PACKAGE_DIR/api/src"
echo -e "${GREEN}OK${NC}"

# Step 3: Copy API source code
echo -n "Copying API source code... "
cp -r "$PROJECT_ROOT/apps/api/src/"* "$PACKAGE_DIR/api/src/"
cp "$PROJECT_ROOT/apps/api/pyproject.toml" "$PACKAGE_DIR/api/"
cp "$PROJECT_ROOT/apps/api/uv.lock" "$PACKAGE_DIR/api/" 2>/dev/null || true
echo -e "${GREEN}OK${NC}"

# Step 4: Copy seed data (ChromaDB)
echo -n "Copying ChromaDB data... "
# Copy the sqlite database
cp "$PROJECT_ROOT/fixtures/seed/chroma.sqlite3" "$PACKAGE_DIR/data/chroma/"
# Copy the UUID directories (embedding data)
for dir in "$PROJECT_ROOT/fixtures/seed/"*/; do
    dirname=$(basename "$dir")
    # Skip pdfs directory, only copy UUID directories
    if [[ "$dirname" != "pdfs" ]]; then
        cp -r "$dir" "$PACKAGE_DIR/data/chroma/"
    fi
done
echo -e "${GREEN}OK${NC}"

# Step 5: Copy PDFs
echo -n "Copying PDF files... "
cp "$PROJECT_ROOT/fixtures/seed/pdfs/"*.pdf "$PACKAGE_DIR/data/pdfs/"
PDF_COUNT=$(ls -1 "$PACKAGE_DIR/data/pdfs/"*.pdf 2>/dev/null | wc -l | tr -d ' ')
echo -e "${GREEN}${PDF_COUNT} PDFs${NC}"

# Step 6: Verify package contents
echo ""
echo "Package contents:"
echo "  - docker-compose.yml"
echo "  - .env.example"
echo "  - README.md"
echo "  - api/ (FastAPI source + Dockerfile)"
echo "  - data/chroma/ (ChromaDB index)"
echo "  - data/pdfs/ ($PDF_COUNT PDF files)"

# Step 7: Calculate sizes
CHROMA_SIZE=$(du -sh "$PACKAGE_DIR/data/chroma" | cut -f1)
PDF_SIZE=$(du -sh "$PACKAGE_DIR/data/pdfs" | cut -f1)
TOTAL_SIZE=$(du -sh "$PACKAGE_DIR" | cut -f1)
echo ""
echo "Sizes:"
echo "  - ChromaDB: $CHROMA_SIZE"
echo "  - PDFs: $PDF_SIZE"
echo "  - Total: $TOTAL_SIZE"

# Step 8: Create archive
echo ""
echo -n "Creating archive... "
cd "$PROJECT_ROOT"
tar -czf "$OUTPUT_FILE" demo-package/
ARCHIVE_SIZE=$(du -sh "$OUTPUT_FILE" | cut -f1)
echo -e "${GREEN}OK${NC}"

echo ""
echo "=========================================="
echo -e "  ${GREEN}Package Created Successfully!${NC}"
echo "=========================================="
echo ""
echo "  Output: $OUTPUT_FILE"
echo "  Size:   $ARCHIVE_SIZE"
echo ""
echo "  To test the package:"
echo "    1. cd /tmp"
echo "    2. tar xzf $OUTPUT_FILE"
echo "    3. cd demo-package"
echo "    4. cp .env.example .env"
echo "    5. # Edit .env with your UPSTAGE_API_KEY"
echo "    6. docker compose up -d"
echo ""
echo "=========================================="
