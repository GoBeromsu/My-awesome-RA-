#!/usr/bin/env python3
"""
Regenerate seed data with ChromaDB.

Usage:
    cd apps/api && python ../../scripts/regenerate_seed.py          # Resume mode
    cd apps/api && python ../../scripts/regenerate_seed.py --reset  # Fresh start
"""

import asyncio
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Setup paths
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root / "apps" / "api"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import chromadb
import numpy as np

from src.services.embedding import EmbeddingService
from src.services.solar import SolarService

# Configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "3"))


def log(msg: str) -> None:
    """Print with immediate flush."""
    print(msg, flush=True)


def chunk_text_iter(text: str):
    """Yield overlapping text chunks."""
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            for sep in [". ", ".\n", "\n\n"]:
                pos = text.rfind(sep, start, end)
                if pos > start:
                    end = pos + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            yield {"text": chunk, "start": start, "end": end}
        start = end - CHUNK_OVERLAP if end < len(text) else len(text)


def merge_chunks(chunks: list[dict], target: int, min_merge: int | None = None, max_merge: int | None = None) -> list[dict]:
    """Greedy merge of adjacent small chunks to reduce count."""
    if not chunks:
        return chunks
    if min_merge is None:
        min_merge = int(target * 0.6)
    if max_merge is None:
        max_merge = int(target * 1.3)

    merged: list[dict] = []
    buffer = chunks[0].copy()

    for chunk in chunks[1:]:
        combined_len = len(buffer["text"]) + 1 + len(chunk["text"])
        if combined_len <= max_merge and (len(buffer["text"]) < min_merge or len(chunk["text"]) < min_merge):
            buffer["text"] = buffer["text"] + " " + chunk["text"]
            buffer["end"] = chunk["end"]
        else:
            merged.append(buffer)
            buffer = chunk.copy()

    merged.append(buffer)
    return merged


def make_doc_id(cite_key: str, content: bytes) -> str:
    """Generate document ID: citeKey_hash12."""
    h = hashlib.sha256(content).hexdigest()[:12]
    safe = re.sub(r"[^\w\-\.]", "_", cite_key)
    safe = re.sub(r"_+", "_", safe).strip("_")
    return f"{safe}_{h}"


def estimate_page(start: int, end: int, total_chars: int, total_pages: int) -> int:
    """Estimate page number from character position."""
    if total_chars <= 0 or total_pages <= 1:
        return 1
    ratio = ((start + end) / 2) / total_chars
    return min(int(ratio * total_pages) + 1, total_pages)


def extract_paper_metadata(cite_key: str, pdf_path: str) -> dict:
    """Extract metadata from cite_key pattern: Author2024Title."""
    match = re.match(r'^([A-Za-z\-]+)(\d{4})(.+)$', cite_key)
    if match:
        author = match.group(1)
        year = int(match.group(2))
        title = match.group(3)
        return {
            "title": title,
            "authors": author,
            "year": year,
            "source_pdf": pdf_path,
        }
    return {"title": cite_key, "authors": "", "year": None, "source_pdf": pdf_path}


async def process_pdf(
    pdf_path: Path,
    cite_key: str,
    solar: SolarService,
    embedder: EmbeddingService,
    collection: chromadb.Collection,
    pdf_out: Path,
    skip_existing: set[str],
    batch_size: int,
) -> dict:
    """Process single PDF and add to ChromaDB."""
    # Read and generate ID
    content = pdf_path.read_bytes()
    doc_id = make_doc_id(cite_key, content)

    # Skip if already indexed
    if doc_id in skip_existing:
        log(f"  SKIP: Already indexed ({doc_id[:30]}...)")
        return {"doc_id": doc_id, "status": "skipped", "chunks": 0}

    log(f"  ID: {doc_id}")

    # Copy PDF
    target = pdf_out / f"{doc_id}.pdf"
    if not target.exists():
        shutil.copy(pdf_path, target)

    # Parse with SOLAR
    log(f"  Parsing {len(content) // 1024}KB...")
    parsed = await solar.parse_document(content, pdf_path.name)
    del content

    text = parsed.get("content", "").strip()
    if not text:
        log("  SKIP: No text")
        return {"doc_id": doc_id, "status": "empty", "chunks": 0}

    pages = parsed.get("pages", 1)
    total_chars = len(text)

    # Chunk + merge + embed + upsert in batches
    raw_chunks = list(chunk_text_iter(text))
    merged_chunks = merge_chunks(raw_chunks, target=CHUNK_SIZE)
    log(f"  Chunking: raw={len(raw_chunks)} merged={len(merged_chunks)} size={CHUNK_SIZE} overlap={CHUNK_OVERLAP}")
    log(f"  Embedding chunks (batch={batch_size})...")
    now = datetime.now(timezone.utc).isoformat()
    chunk_index = 0
    pending: list[tuple[int, dict]] = []

    def upsert_with_retry(ids, embeddings, documents, metadatas, max_retries: int = 5, base_sleep: float = 0.5):
        import time
        attempt = 0
        while True:
            try:
                collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
                return
            except Exception as e:
                msg = str(e).lower()
                if ("readonly" in msg or "locked" in msg or "busy" in msg) and attempt < max_retries:
                    sleep_for = base_sleep * (2 ** attempt)
                    time.sleep(sleep_for)
                    attempt += 1
                    continue
                raise

    async def upsert_batch() -> None:
        if not pending:
            return

        texts = [c["text"] for _, c in pending]
        embs = await embedder.embed_documents(texts)

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for (idx, chunk), emb in zip(pending, embs):
            ids.append(f"{doc_id}_{idx}")
            embeddings.append((emb / np.linalg.norm(emb)).tolist())
            documents.append(chunk["text"])
            paper_meta = extract_paper_metadata(cite_key, str(target))
            metadatas.append({
                "document_id": doc_id,
                "cite_key": cite_key,
                "start_idx": chunk["start"],
                "end_idx": chunk["end"],
                "page": estimate_page(chunk["start"], chunk["end"], total_chars, pages),
                "page_count": pages,
                "indexed_at": now,
                **paper_meta,
            })

        upsert_with_retry(ids, embeddings, documents, metadatas)
        pending.clear()

    for chunk in merged_chunks:
        pending.append((chunk_index, chunk))
        chunk_index += 1
        if len(pending) >= batch_size:
            await upsert_batch()

    if pending:
        await upsert_batch()

    return {"doc_id": doc_id, "status": "ok", "chunks": chunk_index}


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

    batch_size = metadata.get("hnsw:batch_size")
    sync_threshold = metadata.get("hnsw:sync_threshold")
    if isinstance(batch_size, int) and isinstance(sync_threshold, int):
        if batch_size > sync_threshold:
            metadata["hnsw:batch_size"] = sync_threshold

    return metadata


async def main():
    """Main entry point."""
    papers_dir = project_root / "fixtures" / "papers"
    mapping_file = project_root / "fixtures" / "pdf_citekey_mapping.json"
    seed_dir = project_root / "fixtures" / "seed"
    pdf_out = seed_dir / "pdfs"

    # Load mapping
    if not mapping_file.exists():
        log(f"Error: {mapping_file} not found")
        sys.exit(1)

    mapping = {k: v for k, v in json.loads(mapping_file.read_text()).items() if v}
    log(f"PDFs to process: {len(mapping)}")

    if not os.getenv("UPSTAGE_API_KEY"):
        log("Error: UPSTAGE_API_KEY not set")
        sys.exit(1)

    # Check for --reset flag
    reset_mode = "--reset" in sys.argv
    if reset_mode and seed_dir.exists():
        log("Reset mode: Clearing existing seed data...")
        shutil.rmtree(seed_dir)

    # Setup directories (don't clear - support resume)
    seed_dir.mkdir(parents=True, exist_ok=True)
    pdf_out.mkdir(exist_ok=True)

    # Initialize
    embedder = EmbeddingService()
    solar = SolarService()
    client = chromadb.PersistentClient(path=str(seed_dir))
    collection = client.get_or_create_collection(
        "documents",
        metadata=build_collection_metadata(),
    )
    max_batch_size = getattr(client, "max_batch_size", None)
    effective_batch_size = EMBED_BATCH_SIZE
    if isinstance(max_batch_size, int):
        effective_batch_size = max(1, min(effective_batch_size, max_batch_size))

    # Get already indexed documents for resume (based on saved PDFs)
    existing_docs = {p.stem for p in pdf_out.glob("*.pdf")}
    if existing_docs:
        log(f"Resuming: {len(existing_docs)} docs already indexed")

    log(f"\nChunk: {CHUNK_SIZE} chars, Batch: {effective_batch_size}")
    log("=" * 40)

    success = 0
    failed = 0

    try:
        for i, (filename, cite_key) in enumerate(mapping.items(), 1):
            pdf = papers_dir / filename
            if not pdf.exists():
                log(f"\n[{i}/{len(mapping)}] SKIP: {cite_key} (not found)")
                continue

            log(f"\n[{i}/{len(mapping)}] {cite_key}")

            try:
                result = await process_pdf(
                    pdf,
                    cite_key,
                    solar,
                    embedder,
                    collection,
                    pdf_out,
                    existing_docs,
                    effective_batch_size,
                )
                if result["status"] == "skipped":
                    success += 1  # Count as success
                    continue
                if result["status"] == "ok":
                    success += 1
                    log(f"  OK: {result['chunks']} chunks (total: {collection.count()})")
                else:
                    log(f"  {result['status']}")
            except Exception as e:
                log(f"  ERROR: {e}")
                failed += 1

            # Rate limit delay
            if i < len(mapping):
                await asyncio.sleep(2)

    finally:
        await embedder.close()
        await solar.close()

    # Summary
    log("\n" + "=" * 40)
    log(f"Done: {success} success, {failed} failed")
    log(f"Total vectors: {collection.count()}")
    log(f"Seed: {seed_dir}")


if __name__ == "__main__":
    asyncio.run(main())
