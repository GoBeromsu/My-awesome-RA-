#!/usr/bin/env python3
"""Process a single PDF - called by wrapper script.

## Memory Management Strategy (2026-02-01)

Problem: ChromaDB HNSW uses C++ memory that Python GC cannot reclaim.
See: https://github.com/chroma-core/chroma/issues/5843

Solutions applied:
1. **Subprocess isolation**: Each PDF runs in separate process (run_seed_stable.sh)
   - All native memory released when process exits
2. **LRU cache policy**: ChromaDB Settings with memory limit
   - Evicts old segments when limit reached
   - See: https://cookbook.chromadb.dev/strategies/memory-management/
3. **Explicit gc.collect()**: Called after each batch upsert
   - Helps Python release references faster
4. **Batch streaming**: Embed and upsert in small batches (default 3)
   - Avoids loading all embeddings into memory at once
5. **Retry with backoff**: SQLite/FS lock errors handled gracefully
"""
import asyncio
import gc
import hashlib
import os
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Setup paths
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root / "apps" / "api"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import chromadb
from chromadb.config import Settings
import numpy as np
from src.services.embedding import EmbeddingService
from src.services.solar import SolarService

# =============================================================================
# Configuration (all overridable via environment variables)
# =============================================================================

# ChromaDB memory limit per subprocess (default 10GB for Apple Silicon)
# Triggers LRU eviction when exceeded
CHROMA_MEMORY_LIMIT = int(os.getenv("CHROMA_MEMORY_LIMIT", str(10 * 1024 * 1024 * 1024)))

# Chunk size ~1800 chars ≈ 450 tokens, fits well within embedding model context
# Overlap 200 chars ensures sentence continuity across chunks
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

# Embed batch size 3 balances API calls vs memory usage
# Larger batches = fewer API calls but more memory per batch
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "3"))
LOG_EVERY_N_BATCHES = int(os.getenv("LOG_EVERY_N_BATCHES", "5"))


def chunk_text_iter(text: str):
    """Split text into overlapping chunks at sentence boundaries.

    Bug fix (2026-02-01): Ensure start always advances to prevent infinite loop.
    If separator is found too early, end could become small, making
    (end - CHUNK_OVERLAP) less than current start.
    """
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            # Find sentence boundary, but only in the last 30% of chunk
            # to avoid creating tiny chunks
            search_start = start + int(CHUNK_SIZE * 0.7)
            for sep in [". ", ".\n", "\n\n"]:
                last_sep = text.rfind(sep, search_start, end)
                if last_sep > search_start:
                    end = last_sep + len(sep)
                    break
        chunk_text = text[start:end].strip()
        if chunk_text:
            yield {"text": chunk_text, "start": start, "end": end}
        # Ensure start always advances (at least by 1 char to prevent infinite loop)
        next_start = end - CHUNK_OVERLAP if end < len(text) else len(text)
        start = max(start + 1, next_start)


def merge_chunks(chunks: list[dict], target: int, min_merge: int | None = None, max_merge: int | None = None) -> list[dict]:
    """Greedy merge of adjacent small chunks to reduce total chunk count.

    Why: Sentence boundary splitting can create very short chunks (e.g., 200 chars).
    Merging reduces embedding API calls and improves semantic coherence.

    Strategy: If either adjacent chunk is below min_merge (60% of target),
    merge them if combined length stays under max_merge (130% of target).
    """
    if not chunks:
        return chunks
    min_merge = min_merge if min_merge is not None else int(target * 0.6)
    max_merge = max_merge if max_merge is not None else int(target * 1.3)

    merged: list[dict] = []
    buffer = chunks[0].copy()

    for chunk in chunks[1:]:
        combined_len = len(buffer["text"]) + 1 + len(chunk["text"])
        if combined_len <= max_merge and (len(buffer["text"]) < min_merge or len(chunk["text"]) < min_merge):
            # merge with a space
            buffer["text"] = buffer["text"] + " " + chunk["text"]
            buffer["end"] = chunk["end"]
        else:
            merged.append(buffer)
            buffer = chunk.copy()

    merged.append(buffer)
    return merged


def estimate_page(start: int, end: int, total_chars: int, total_pages: int) -> int:
    if total_chars <= 0 or total_pages <= 1:
        return 1
    ratio = ((start + end) / 2) / total_chars
    return min(int(ratio * total_pages) + 1, total_pages)


def build_collection_metadata() -> dict:
    metadata: dict[str, object] = {"hnsw:space": os.getenv("HNSW_SPACE", "cosine")}
    int_fields = {
        "HNSW_M": "hnsw:M",
        "HNSW_CONSTRUCTION_EF": "hnsw:construction_ef",
        "HNSW_SEARCH_EF": "hnsw:search_ef",
        "HNSW_BATCH_SIZE": "hnsw:batch_size",
        "HNSW_SYNC_THRESHOLD": "hnsw:sync_threshold",
        "HNSW_NUM_THREADS": "hnsw:num_threads",
    }
    for env_key, meta_key in int_fields.items():
        value = os.getenv(env_key)
        if value:
            metadata[meta_key] = int(value)

    resize_factor = os.getenv("HNSW_RESIZE_FACTOR")
    if resize_factor:
        metadata["hnsw:resize_factor"] = float(resize_factor)

    # Ensure batch_size does not exceed sync_threshold (ChromaDB constraint)
    batch_size = metadata.get("hnsw:batch_size")
    sync_threshold = metadata.get("hnsw:sync_threshold")
    if isinstance(batch_size, int) and isinstance(sync_threshold, int) and batch_size > sync_threshold:
        metadata["hnsw:batch_size"] = sync_threshold

    return metadata


async def process(pdf_path: str, cite_key: str, seed_dir: str):
    pdf_path = Path(pdf_path)
    seed_dir = Path(seed_dir)

    # Read PDF
    content = pdf_path.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()[:12]
    safe_key = re.sub(r"[^\w\-\.]", "_", cite_key)
    doc_id = f"{safe_key}_{file_hash}"
    print(f"[START] {pdf_path.name} -> {doc_id}", flush=True)

    # Init services
    solar = SolarService()
    embed_svc = EmbeddingService()

    try:
        # Parse PDF via SOLAR API
        print("[PARSE] Sending to SOLAR...", flush=True)
        parsed = await solar.parse_document(content, pdf_path.name)
        text = parsed.get("content", "")
        if not text.strip():
            print(f"EMPTY:{doc_id}", flush=True)
            return
        pages = parsed.get("pages", 1)

        total_chars = len(text)
        print(f"[PARSE] Done: chars={total_chars:,} pages={pages}", flush=True)

        # Chunk and merge to control count
        print("[DEBUG] Starting chunking...", flush=True)
        raw_chunks = list(chunk_text_iter(text))
        print(f"[DEBUG] Raw chunks: {len(raw_chunks)}", flush=True)
        chunks = merge_chunks(raw_chunks, target=CHUNK_SIZE)
        print(f"[CHUNK] raw={len(raw_chunks)} merged={len(chunks)} size={CHUNK_SIZE} overlap={CHUNK_OVERLAP}", flush=True)

        # Open ChromaDB with LRU cache policy and memory limit
        print("[DEBUG] Initializing ChromaDB...", flush=True)
        settings = Settings(
            chroma_segment_cache_policy="LRU",
            chroma_memory_limit_bytes=CHROMA_MEMORY_LIMIT,
            anonymized_telemetry=False,
        )
        client = chromadb.PersistentClient(path=str(seed_dir), settings=settings)
        collection = client.get_or_create_collection(
            "documents",
            metadata=build_collection_metadata(),
        )
        # Clamp batch size to client limit if specified
        max_batch_size = getattr(client, "max_batch_size", None)
        batch_size = max(1, min(EMBED_BATCH_SIZE, max_batch_size)) if isinstance(max_batch_size, int) else EMBED_BATCH_SIZE
        print(f"[INDEX] batch_size={batch_size}", flush=True)
        now = datetime.now(timezone.utc).isoformat()
        total_chunks = 0

        pending: list[tuple[int, dict]] = []
        chunk_index = 0
        batch_no = 0

        def upsert_with_retry(ids, embeddings, documents, metadatas, max_retries: int = 5, base_sleep: float = 0.5):
            """Upsert with backoff to avoid transient SQLite/FS locks."""
            attempt = 0
            while True:
                try:
                    collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
                    return
                except Exception as e:  # chromadb raises wrapped errors; string-inspect
                    msg = str(e).lower()
                    if ("readonly" in msg or "locked" in msg or "busy" in msg) and attempt < max_retries:
                        sleep_for = base_sleep * (2 ** attempt)
                        print(f"[UPSERT-RETRY] attempt={attempt+1} sleep={sleep_for:.2f}s reason={msg}", flush=True)
                        time.sleep(sleep_for)
                        attempt += 1
                        continue
                    raise

        async def upsert_batch() -> None:
            nonlocal total_chunks, batch_no
            if not pending:
                return

            batch_texts = [c["text"] for _, c in pending]
            embs = await embed_svc.embed_documents(batch_texts)

            ids = []
            emb_list = []
            docs = []
            metas = []

            for (idx, chunk), emb in zip(pending, embs):
                norm = emb / np.linalg.norm(emb)
                ids.append(f"{doc_id}_{idx}")
                emb_list.append(norm.tolist())
                docs.append(chunk["text"])
                metas.append({
                    "document_id": doc_id,
                    "cite_key": cite_key,
                    "start_idx": chunk["start"],
                    "end_idx": chunk["end"],
                    "page": estimate_page(chunk["start"], chunk["end"], total_chars, pages),
                    "page_count": pages,
                    "indexed_at": now,
                })

            upsert_with_retry(ids, emb_list, docs, metas)
            total_chunks += len(pending)
            batch_no += 1
            if LOG_EVERY_N_BATCHES > 0 and (batch_no == 1 or batch_no % LOG_EVERY_N_BATCHES == 0):
                print(f"[EMBED] batches={batch_no} chunks={total_chunks}", flush=True)
            pending.clear()
            # Release memory after each batch to avoid accumulation
            # See: https://cookbook.chromadb.dev/strategies/memory-management/
            gc.collect()

        for chunk in chunks:
            pending.append((chunk_index, chunk))
            chunk_index += 1

            if len(pending) >= batch_size:
                await upsert_batch()

        if pending:
            await upsert_batch()

        # Copy PDF only after successful indexing (used as resume marker)
        pdf_dir = seed_dir / "pdfs"
        pdf_dir.mkdir(exist_ok=True)
        target_pdf = pdf_dir / f"{doc_id}.pdf"
        if not target_pdf.exists():
            shutil.copy(pdf_path, target_pdf)
            print(f"[COPY] {target_pdf.name}", flush=True)

        print(f"OK:{doc_id}:{total_chunks}", flush=True)

    finally:
        await embed_svc.close()
        await solar.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: _process_one.py <pdf_path> <cite_key> <seed_dir>")
        sys.exit(1)
    asyncio.run(process(sys.argv[1], sys.argv[2], sys.argv[3]))
