# My Awesome RA API - Multi-stage build
# Stage 1: Build dependencies (includes build-essential for chromadb)
# Stage 2: Slim runtime (no build tools, non-root user)

# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies (only needed for compilation)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies with cache (creates .venv in /app)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies (curl for healthcheck in compose)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create data directories
RUN mkdir -p /data/pdfs /data/chroma

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY src/ ./src/

# Note: Running as root for volume mount compatibility
# For production, use init container or entrypoint to fix permissions

# Add .venv/bin to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
