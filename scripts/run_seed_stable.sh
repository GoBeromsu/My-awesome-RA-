#!/bin/bash
# Stable seed build - each PDF in separate process (memory-safe)
# Resume supported: skips already-processed PDFs (checks by cite_key prefix)
# Usage: ./run_seed_stable.sh [--force] [--reverse] [--batch-size N] [--log-every N] [--chunk-size N] [--overlap N]
set -e

cd "$(dirname "$0")/.."
SEED_DIR="fixtures/seed"
MAPPING="fixtures/pdf_citekey_mapping.json"
PAPERS="fixtures/papers"
VENV="apps/api/.venv/bin/activate"

# Parse args
FORCE=false
REVERSE=false
EMBED_BATCH_SIZE="${EMBED_BATCH_SIZE:-3}"
LOG_EVERY_N_BATCHES="${LOG_EVERY_N_BATCHES:-5}"
CHUNK_SIZE="${CHUNK_SIZE:-1800}"
CHUNK_OVERLAP="${CHUNK_OVERLAP:-200}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        --batch-size|--embed-batch-size)
            EMBED_BATCH_SIZE="$2"
            shift 2
            ;;
        --reverse)
            REVERSE=true
            shift
            ;;
        --log-every)
            LOG_EVERY_N_BATCHES="$2"
            shift 2
            ;;
        --chunk-size)
            CHUNK_SIZE="$2"
            shift 2
            ;;
        --overlap)
            CHUNK_OVERLAP="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: ./run_seed_stable.sh [--force] [--reverse] [--batch-size N] [--log-every N] [--chunk-size N] [--overlap N]"
            echo "  --batch-size N   Embedding batch size per PDF (default: 3)"
            echo "  --log-every N    Log every N embed batches (default: 5, 1 = every batch)"
            echo "  --chunk-size N   Chunk size in characters (default: 1800)"
            echo "  --overlap N      Chunk overlap in characters (default: 200)"
            echo "  --reverse        Process mapping in reverse order (end to start)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Clear seed only with --force
if $FORCE; then
    echo "Force rebuild: clearing seed directory"
    rm -rf "$SEED_DIR"
fi
mkdir -p "$SEED_DIR/pdfs"

echo "=== Stable Seed Build ==="
source "$VENV"
export EMBED_BATCH_SIZE
export LOG_EVERY_N_BATCHES
export CHUNK_SIZE
export CHUNK_OVERLAP

ORDER_FILTER=""
if $REVERSE; then
    ORDER_FILTER="| reverse"
fi

total=$(jq 'to_entries | map(select(.value != null)) | length' "$MAPPING")
current=0
success=0
skipped=0
failed=0

for row in $(jq -r "to_entries | map(select(.value != null)) ${ORDER_FILTER} | .[] | @base64" "$MAPPING"); do
    pdf=$(echo "$row" | base64 -d | jq -r '.key')
    cite_key=$(echo "$row" | base64 -d | jq -r '.value')
    current=$((current + 1))

    if [[ ! -f "$PAPERS/$pdf" ]]; then
        echo "[$current/$total] SKIP (not found): $cite_key"
        skipped=$((skipped + 1))
        continue
    fi

    # Resume: check if PDF with this cite_key prefix already exists
    safe_key=$(echo "$cite_key" | sed 's/[^a-zA-Z0-9_.-]/_/g')
    if ls "$SEED_DIR/pdfs/${safe_key}_"*.pdf 1>/dev/null 2>&1; then
        echo "[$current/$total] SKIP (indexed): $cite_key"
        skipped=$((skipped + 1))
        continue
    fi

    echo "[$current/$total] Processing: $cite_key"

    # Run in subprocess - memory released after each
    if python scripts/_process_one.py "$PAPERS/$pdf" "$cite_key" "$SEED_DIR" 2>&1; then
        success=$((success + 1))
    else
        echo "  FAILED"
        failed=$((failed + 1))
    fi

    # Brief pause for API rate limiting
    sleep 2
done

echo ""
echo "=== Summary ==="
echo "Processed: $success"
echo "Skipped: $skipped"
echo "Failed: $failed"
echo "Total: $total"
echo "Seed: $SEED_DIR"
