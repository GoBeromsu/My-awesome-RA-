#!/bin/bash
# My Awesome RA - One-Command Demo Build
#
# This script builds the complete demo environment from scratch.
# Run this from any directory in the project.
#
# Usage:
#   ./scripts/build-demo.sh           # Full build (first time)
#   ./scripts/build-demo.sh --skip-base   # Skip base image (subsequent runs)

set -e

# Navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "=============================================="
echo "  My Awesome RA - Demo Environment Builder"
echo "=============================================="
echo -e "${NC}"

SKIP_BASE=false
for arg in "$@"; do
    case $arg in
        --skip-base)
            SKIP_BASE=true
            shift
            ;;
    esac
done

# Check if base image exists
BASE_IMAGE_EXISTS=$(docker images -q sharelatex/sharelatex-base:latest 2>/dev/null)

if [ "$SKIP_BASE" = true ]; then
    echo -e "${YELLOW}Skipping base image build (--skip-base flag)${NC}"
elif [ -n "$BASE_IMAGE_EXISTS" ]; then
    echo -e "${GREEN}Base image already exists, skipping build.${NC}"
    echo -e "${YELLOW}Use 'docker rmi sharelatex/sharelatex-base:latest' to force rebuild.${NC}"
    echo
else
    echo -e "${YELLOW}Step 1/2: Building base image...${NC}"
    echo -e "This includes Node.js 22.x and TexLive. May take 15-20 minutes."
    echo

    docker build \
        -f overleaf/server-ce/Dockerfile-base \
        -t sharelatex/sharelatex-base:latest \
        overleaf/

    echo
    echo -e "${GREEN}Base image built successfully!${NC}"
fi

# Verify base image has correct Node version
echo
echo -e "${YELLOW}Verifying Node.js version in base image...${NC}"
NODE_VERSION=$(docker run --rm sharelatex/sharelatex-base:latest node --version 2>/dev/null || echo "failed")

if [[ "$NODE_VERSION" == v22* ]] || [[ "$NODE_VERSION" == v20* ]] || [[ "$NODE_VERSION" == v18* ]]; then
    echo -e "${GREEN}Node.js version: $NODE_VERSION${NC}"
else
    echo -e "${RED}Error: Unexpected Node.js version: $NODE_VERSION${NC}"
    echo -e "${RED}Expected v18.x, v20.x, or v22.x${NC}"
    echo -e "${YELLOW}Try rebuilding the base image:${NC}"
    echo "  docker rmi sharelatex/sharelatex-base:latest"
    echo "  ./scripts/build-demo.sh"
    exit 1
fi

echo
echo -e "${YELLOW}Step 2/2: Building and starting demo environment...${NC}"
echo -e "This builds Overleaf + Evidence Panel. May take 10-15 minutes."
echo

cd deployment
docker compose up --build -d

echo
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
echo -e "This may take a few minutes while services initialize."
echo

# Wait for Overleaf to be healthy (up to 5 minutes)
TIMEOUT=300
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' overleaf-web 2>/dev/null || echo "not_found")

    if [ "$STATUS" = "healthy" ]; then
        echo -e "${GREEN}Overleaf is healthy!${NC}"
        break
    fi

    if [ "$STATUS" = "not_found" ]; then
        echo -e "${YELLOW}Waiting for container to start...${NC}"
    else
        echo -e "${YELLOW}Status: $STATUS (${ELAPSED}s/${TIMEOUT}s)${NC}"
    fi

    sleep 10
    ELAPSED=$((ELAPSED + 10))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo -e "${RED}Timeout waiting for Overleaf to become healthy${NC}"
    echo "Check logs with: docker compose -f deployment/docker-compose.yml logs overleaf-web"
    exit 1
fi

echo
echo -e "${YELLOW}Setting up demo user and project...${NC}"
cd "$PROJECT_DIR"
./scripts/setup-demo.sh

echo
echo -e "${GREEN}=============================================="
echo "  Demo Environment Ready!"
echo "==============================================${NC}"
echo
echo "Access Overleaf at: ${GREEN}http://localhost${NC}"
echo
echo "Login credentials:"
echo "  Email:    demo@example.com"
echo "  Password: Demo@2024!Secure"
echo
echo -e "${BLUE}To stop:${NC}  cd deployment && docker compose down"
echo -e "${BLUE}To restart:${NC} cd deployment && docker compose up -d"
echo -e "${BLUE}View logs:${NC} cd deployment && docker compose logs -f"
echo
