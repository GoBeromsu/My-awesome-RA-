#!/usr/bin/env python3
"""
Index PDFs from fixtures/papers/ into FAISS vector store.

Memory-efficient: small batches, resource monitoring, incremental saves.

Usage:
    cd apps/api && uv run python ../../scripts/index_fixtures.py
"""

import asyncio
import gc
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

# Add the api src to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
api_src = project_root / "apps" / "api"
sys.path.insert(0, str(api_src))

# Load .env file from project root
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from src.services.embedding import EmbeddingService
from src.services.index import IndexService
from src.services.solar import SolarService


# Resource limits
EMBEDDING_BATCH_SIZE = 10  # Embed 10 chunks at a time
MAX_CHUNK_SIZE = 400  # Characters per chunk (smaller = less memory per embed)
CHUNK_OVERLAP = 50


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_maxrss / 1024 / 1024  # Convert to MB (macOS returns bytes)
    except Exception:
        return 0.0


def chunk_text(text: str, chunk_size: int = MAX_CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split text into smaller chunks for memory-efficient embedding."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Try to break at sentence boundary
        if end < len(text):
            for sep in [". ", ".\n", "\n\n", "\n"]:
                last_sep = text.rfind(sep, start, end)
                if last_sep > start:
                    end = last_sep + len(sep)
                    break
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({"text": chunk_text, "start_idx": start, "end_idx": end})
        start = end - overlap if end < len(text) else len(text)
    return chunks


async def embed_in_batches(
    texts: list[str],
    embedding_service: EmbeddingService,
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> list:
    """Embed texts in small batches to control memory."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = await embedding_service.embed_documents(batch)
        all_embeddings.extend(embeddings)
        gc.collect()  # Force garbage collection between batches
    return all_embeddings


def generate_document_id(pdf_path: Path, content: bytes) -> str:
    """Generate a valid document ID matching the API validation pattern.

    Pattern: ^[\w\-\.]+_[a-f0-9]{12}$
    Example: Vaswani_et_al_2017_a1b2c3d4e5f6
    """
    file_hash = hashlib.sha256(content).hexdigest()[:12]
    # Sanitize filename: replace non-word chars (except - and .) with underscore
    safe_name = re.sub(r"[^\w\-\.]", "_", pdf_path.stem)
    # Remove leading/trailing underscores and collapse multiple underscores
    safe_name = re.sub(r"_+", "_", safe_name).strip("_")
    return f"{safe_name}_{file_hash}"


async def process_single_pdf(
    pdf_path: Path,
    solar_service: SolarService,
    index_service: IndexService,
    embedding_service: EmbeddingService,
    pdf_storage_path: Path | None = None,
) -> dict:
    """Process a single PDF with memory-efficient embedding."""
    mem_before = get_memory_usage_mb()
    print(f"  [MEM] Before: {mem_before:.1f} MB")

    # Read and parse
    with open(pdf_path, "rb") as f:
        content = f.read()

    # Generate proper document ID
    document_id = generate_document_id(pdf_path, content)
    print(f"  [ID] {document_id}")

    file_size_kb = len(content) / 1024

    # Copy PDF to storage if path provided
    if pdf_storage_path:
        pdf_storage_path.mkdir(parents=True, exist_ok=True)
        target_pdf = pdf_storage_path / f"{document_id}.pdf"
        if not target_pdf.exists():
            shutil.copy(pdf_path, target_pdf)
            print(f"  [COPY] {target_pdf.name}")

    print(f"  [PARSE] {file_size_kb:.1f} KB...")
    parsed = await solar_service.parse_document(content, pdf_path.name)
    del content
    gc.collect()

    text_content = parsed.get("content", "")
    if not text_content.strip():
        print(f"  [SKIP] No text extracted")
        return {"document_id": document_id, "status": "empty", "chunk_count": 0}

    pages = parsed.get("pages", 1)
    grounding = parsed.get("grounding")
    del parsed
    gc.collect()

    # Chunk text
    chunks = chunk_text(text_content)
    del text_content
    gc.collect()

    print(f"  [EMBED] {len(chunks)} chunks (batch={EMBEDDING_BATCH_SIZE})...")

    # Embed in batches
    texts = [c["text"] for c in chunks]
    embeddings = await embed_in_batches(texts, embedding_service, EMBEDDING_BATCH_SIZE)
    del texts
    gc.collect()

    # Add to index one by one to minimize peak memory
    import numpy as np
    import faiss

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{document_id}_{i}"
        chunk_grounding = index_service._find_grounding_for_chunk(chunk, grounding)

        normalized = embedding / np.linalg.norm(embedding)
        index_service._index.add(normalized.reshape(1, -1))

        index_service._metadata.append({
            "document_id": document_id,
            "chunk_id": chunk_id,
            "text": chunk["text"],
            "start_idx": chunk["start_idx"],
            "end_idx": chunk["end_idx"],
            "page": chunk_grounding.get("page", 1),
            "bbox": chunk_grounding.get("box"),
            "filename": pdf_path.name,
            "pages": pages,
            "source": "fixtures",
        })

    # Save after each document
    index_service._save_index()

    del chunks, embeddings, grounding
    gc.collect()

    mem_after = get_memory_usage_mb()
    print(f"  [DONE] {len(index_service._metadata)} total chunks | MEM: {mem_after:.1f} MB (+{mem_after - mem_before:.1f})")

    return {
        "document_id": document_id,
        "status": "indexed",
        "chunk_count": len([m for m in index_service._metadata if m["document_id"] == document_id]),
    }


async def main():
    """Index PDFs with resource monitoring."""
    fixtures_dir = project_root / "fixtures" / "papers"
    data_dir = project_root / "data" / "faiss"
    seed_dir = project_root / "fixtures" / "seed"
    pdf_storage_dir = project_root / "data" / "pdfs"
    seed_pdfs_dir = project_root / "fixtures" / "seed" / "pdfs"

    data_dir.mkdir(parents=True, exist_ok=True)
    seed_dir.mkdir(parents=True, exist_ok=True)
    pdf_storage_dir.mkdir(parents=True, exist_ok=True)
    seed_pdfs_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("VECTOR_STORE_PATH", str(data_dir))

    if not os.getenv("UPSTAGE_API_KEY"):
        print("Error: UPSTAGE_API_KEY not set")
        sys.exit(1)

    pdf_files = sorted(fixtures_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs in {fixtures_dir}")
        sys.exit(0)

    print(f"PDFs: {len(pdf_files)}")
    print(f"Chunk size: {MAX_CHUNK_SIZE} chars")
    print(f"Embed batch: {EMBEDDING_BATCH_SIZE}")
    print("=" * 50)

    embedding_service = EmbeddingService()
    index_service = IndexService(embedding_service=embedding_service)
    solar_service = SolarService()

    results = []
    try:
        for i, pdf_path in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}] {pdf_path.name}")
            try:
                result = await process_single_pdf(
                    pdf_path,
                    solar_service,
                    index_service,
                    embedding_service,
                    pdf_storage_path=pdf_storage_dir,
                )
                results.append(result)
            except Exception as e:
                print(f"  [ERROR] {e}")
                results.append({
                    "document_id": pdf_path.stem,
                    "status": "error",
                    "chunk_count": 0,
                    "error": str(e),
                })
                gc.collect()

        # Summary
        print("\n" + "=" * 50)
        print("Summary")
        print("=" * 50)
        indexed = sum(1 for r in results if r["status"] == "indexed")
        total_chunks = len(index_service._metadata)
        errors = sum(1 for r in results if r["status"] == "error")

        print(f"  Indexed: {indexed}/{len(pdf_files)}")
        print(f"  Total chunks: {total_chunks}")
        print(f"  Errors: {errors}")
        print(f"  Final memory: {get_memory_usage_mb():.1f} MB")

        # Copy to seed directory (for demo/testing)
        if indexed > 0:
            # Copy FAISS index files
            for fname in ["index.faiss", "metadata.npy"]:
                src = data_dir / fname
                if src.exists():
                    shutil.copy(src, seed_dir / fname)
                    print(f"  Saved: {seed_dir / fname}")

            # Copy PDFs to seed/pdfs/ for complete seed data
            pdf_count = 0
            for pdf in pdf_storage_dir.glob("*.pdf"):
                shutil.copy(pdf, seed_pdfs_dir / pdf.name)
                pdf_count += 1
            if pdf_count > 0:
                print(f"  Copied: {pdf_count} PDFs to {seed_pdfs_dir}")

    finally:
        await embedding_service.close()
        await solar_service.close()


if __name__ == "__main__":
    asyncio.run(main())
