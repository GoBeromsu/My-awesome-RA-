#!/usr/bin/env python3
"""
Regenerate seed data with citeKey-based document IDs using ChromaDB.

This script:
1. Reads pdf_citekey_mapping.json for PDF ↔ citeKey mapping
2. Indexes all PDFs with citeKey_hash document IDs
3. Stores extended metadata (cite_key, page_count, year)
4. Validates the indexed data
5. Saves to fixtures/seed/ (ChromaDB format)

Usage:
    cd apps/api && uv run python ../../scripts/regenerate_seed.py
"""

import asyncio
import gc
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Add the api src to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
api_src = project_root / "apps" / "api"
sys.path.insert(0, str(api_src))

# Load .env file from project root
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import chromadb
import numpy as np
from numpy.typing import NDArray

from src.services.embedding import EmbeddingService
from src.services.solar import SolarService


# Configuration
EMBEDDING_BATCH_SIZE = 5  # Reduced from 10 for stability
MAX_CHUNK_SIZE = 400
CHUNK_OVERLAP = 50
DIMENSION = 4096
INTER_DOC_DELAY = 2  # Seconds between documents for rate limiting


@dataclass
class ValidationIssue:
    """Single validation issue."""
    document_id: str
    field: str
    message: str
    severity: str  # 'error' | 'warning'


@dataclass
class ValidationReport:
    """Validation report for indexed data."""
    total_documents: int
    valid_documents: int
    total_chunks: int
    issues: list[ValidationIssue]

    def print_summary(self) -> None:
        """Print validation summary."""
        print("\n" + "=" * 50)
        print("Validation Report")
        print("=" * 50)
        print(f"Documents: {self.valid_documents}/{self.total_documents} valid")
        print(f"Total chunks: {self.total_chunks}")

        if not self.issues:
            print("No issues found.")
            return

        errors = sum(1 for i in self.issues if i.severity == 'error')
        warnings = len(self.issues) - errors
        print(f"Errors: {errors}, Warnings: {warnings}")
        for issue in self.issues:
            icon = "ERROR" if issue.severity == 'error' else "WARN"
            print(f"  [{icon}] {issue.document_id}: {issue.field} - {issue.message}")


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_maxrss / 1024 / 1024
    except Exception:
        return 0.0


def chunk_text(text: str, chunk_size: int = MAX_CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
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
) -> list[NDArray[np.float32]]:
    """Embed texts in small batches to control memory."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = await embedding_service.embed_documents(batch)
        all_embeddings.extend(embeddings)
        gc.collect()
    return all_embeddings


def generate_document_id(cite_key: str, content: bytes) -> str:
    r"""Generate document ID in citeKey_hash format.

    Pattern: ^[\w\-\.]+_[a-f0-9]{12}$
    Example: Vaswani2017Attention_a1b2c3d4e5f6
    """
    file_hash = hashlib.sha256(content).hexdigest()[:12]
    safe_key = re.sub(r"[^\w\-\.]", "_", cite_key)
    safe_key = re.sub(r"_+", "_", safe_key).strip("_")
    return f"{safe_key}_{file_hash}"


def parse_year_from_filename(filename: str) -> int | None:
    """Extract year from filename like 'Author - 2024 - Title.pdf'."""
    match = re.search(r"[\s\-]+(\d{4})[\s\-]+", filename)
    if match:
        year = int(match.group(1))
        if 1900 <= year <= 2100:
            return year
    return None


def find_grounding_for_chunk(
    chunk: dict,
    grounding: dict | None,
    total_chars: int,
    total_pages: int,
) -> dict:
    """Find page number for a chunk using position estimation."""
    if not grounding or total_pages <= 1 or total_chars <= 0:
        return {"page": 1}

    chunk_midpoint = (chunk["start_idx"] + chunk["end_idx"]) / 2
    position_ratio = chunk_midpoint / total_chars
    estimated_page = int(position_ratio * total_pages) + 1
    return {"page": min(estimated_page, total_pages)}


def validate_indexed_data(collection: chromadb.Collection) -> ValidationReport:
    """Validate indexed data against expected schema."""
    issues: list[ValidationIssue] = []
    documents: dict[str, list[dict]] = {}

    results = collection.get(include=["metadatas"])

    for meta in results["metadatas"]:
        doc_id = meta.get("document_id", "unknown")
        documents.setdefault(doc_id, []).append(meta)

    valid_count = 0
    doc_id_pattern = re.compile(r"^[\w\-\.]+_[a-f0-9]{12}$")

    def add_issue(doc_id: str, field: str, message: str, severity: str) -> None:
        issues.append(ValidationIssue(doc_id, field, message, severity))

    for doc_id, chunks in documents.items():
        doc_valid = True
        first_chunk = chunks[0]

        if not doc_id_pattern.match(doc_id):
            add_issue(doc_id, "document_id", f"Invalid format: '{doc_id}' does not match pattern", "error")
            doc_valid = False

        if not first_chunk.get("cite_key"):
            add_issue(doc_id, "cite_key", "Missing cite_key", "warning")

        page_count = first_chunk.get("page_count") or first_chunk.get("pages")
        if not page_count or page_count < 1:
            add_issue(doc_id, "page_count", "Missing or invalid page_count", "warning")

        if len(chunks) < 1:
            add_issue(doc_id, "chunk_count", "No chunks for document", "error")
            doc_valid = False
        elif len(chunks) > 500:
            add_issue(doc_id, "chunk_count", f"Unusually high chunk count: {len(chunks)}", "warning")

        if doc_valid:
            valid_count += 1

    return ValidationReport(
        total_documents=len(documents),
        valid_documents=valid_count,
        total_chunks=collection.count(),
        issues=issues,
    )


async def process_single_pdf(
    pdf_path: Path,
    cite_key: str,
    solar_service: SolarService,
    embedding_service: EmbeddingService,
    collection: chromadb.Collection,
    pdf_storage_path: Path,
) -> dict:
    """Process a single PDF with citeKey-based document ID."""
    mem_before = get_memory_usage_mb()
    print(f"  [MEM] Before: {mem_before:.1f} MB")

    # Read PDF
    with open(pdf_path, "rb") as f:
        content = f.read()

    # Generate document ID from cite_key
    document_id = generate_document_id(cite_key, content)
    print(f"  [ID] {document_id}")

    # Copy PDF to storage
    pdf_storage_path.mkdir(parents=True, exist_ok=True)
    target_pdf = pdf_storage_path / f"{document_id}.pdf"
    if not target_pdf.exists():
        shutil.copy(pdf_path, target_pdf)
        print(f"  [COPY] {target_pdf.name}")

    # Parse PDF
    file_size_kb = len(content) / 1024
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
    total_chars = len(text_content)

    # Extract year from filename
    year = parse_year_from_filename(pdf_path.name)

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

    # Prepare data for ChromaDB upsert
    indexed_at = datetime.now(timezone.utc).isoformat()
    ids = []
    embeddings_list = []
    documents = []
    metadatas = []

    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{document_id}_{i}"
        chunk_grounding = find_grounding_for_chunk(chunk, grounding, total_chars, pages)

        # Normalize for cosine similarity
        normalized = embedding / np.linalg.norm(embedding)

        ids.append(chunk_id)
        embeddings_list.append(normalized.tolist())
        documents.append(chunk["text"])
        metadatas.append({
            # Document identification
            "document_id": document_id,
            "chunk_id": chunk_id,
            "cite_key": cite_key,

            # Chunk content & position
            "start_idx": chunk["start_idx"],
            "end_idx": chunk["end_idx"],
            "page": chunk_grounding.get("page", 1),

            # Metadata
            "title": pdf_path.stem,
            "year": year,
            "pages": pages,
            "page_count": pages,
            "source_pdf": pdf_path.name,
            "indexed_at": indexed_at,
        })

    # Upsert to ChromaDB
    collection.upsert(
        ids=ids,
        embeddings=embeddings_list,
        documents=documents,
        metadatas=metadatas,
    )

    chunk_count = len(chunks)
    del chunks, embeddings, grounding
    gc.collect()

    mem_after = get_memory_usage_mb()
    print(f"  [DONE] {chunk_count} chunks | MEM: {mem_after:.1f} MB (+{mem_after - mem_before:.1f})")

    return {
        "document_id": document_id,
        "cite_key": cite_key,
        "status": "indexed",
        "chunk_count": chunk_count,
        "page_count": pages,
    }


async def main():
    """Regenerate seed data with citeKey-based document IDs using ChromaDB."""
    fixtures_dir = project_root / "fixtures" / "papers"
    mapping_file = project_root / "fixtures" / "pdf_citekey_mapping.json"
    seed_dir = project_root / "fixtures" / "seed"
    seed_pdfs_dir = seed_dir / "pdfs"
    data_dir = project_root / "data" / "chroma"

    # Load mapping
    if not mapping_file.exists():
        print(f"Error: Mapping file not found: {mapping_file}")
        sys.exit(1)

    with open(mapping_file) as f:
        mapping = json.load(f)

    # Filter out null mappings (duplicate PDFs)
    mapping = {k: v for k, v in mapping.items() if v is not None}
    print(f"Mapping: {len(mapping)} PDFs with cite keys")

    if not os.getenv("UPSTAGE_API_KEY"):
        print("Error: UPSTAGE_API_KEY not set")
        sys.exit(1)

    # Clear existing seed data
    print("\nClearing existing seed data...")
    if seed_dir.exists():
        shutil.rmtree(seed_dir)
    seed_dir.mkdir(parents=True, exist_ok=True)
    seed_pdfs_dir.mkdir(parents=True, exist_ok=True)

    # Also clear data/chroma to force fresh load
    if data_dir.exists():
        print(f"Clearing {data_dir}...")
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nChunk size: {MAX_CHUNK_SIZE} chars")
    print(f"Embed batch: {EMBEDDING_BATCH_SIZE}")
    print("=" * 50)

    # Initialize services
    embedding_service = EmbeddingService()
    solar_service = SolarService()

    # Create fresh ChromaDB collection
    client = chromadb.PersistentClient(path=str(seed_dir))
    collection = client.get_or_create_collection(
        name="documents",
        metadata={"hnsw:space": "cosine"},
    )

    results = []
    processed = 0

    try:
        for pdf_filename, cite_key in mapping.items():
            pdf_path = fixtures_dir / pdf_filename
            if not pdf_path.exists():
                print(f"\n[SKIP] Not found: {pdf_filename}")
                continue

            processed += 1
            print(f"\n[{processed}/{len(mapping)}] {cite_key}")
            print(f"  File: {pdf_filename[:60]}...")

            try:
                result = await process_single_pdf(
                    pdf_path,
                    cite_key,
                    solar_service,
                    embedding_service,
                    collection,
                    seed_pdfs_dir,
                )
                results.append(result)

                # ChromaDB auto-persists, but we can log progress
                print(f"  [SAVE] Checkpoint saved ({collection.count()} vectors)")

                # Force garbage collection after each document
                gc.collect()

                # Delay between documents for API rate limiting
                if processed < len(mapping):
                    await asyncio.sleep(INTER_DOC_DELAY)

            except Exception as e:
                print(f"  [ERROR] {e}")
                results.append({
                    "document_id": cite_key,
                    "cite_key": cite_key,
                    "status": "error",
                    "chunk_count": 0,
                    "error": str(e),
                })
                gc.collect()

        # Validate
        validation = validate_indexed_data(collection)
        validation.print_summary()

        # Summary
        print("\n" + "=" * 50)
        print("Summary")
        print("=" * 50)
        indexed = sum(1 for r in results if r["status"] == "indexed")
        errors = sum(1 for r in results if r["status"] == "error")
        total_chunks = collection.count()

        print(f"  Indexed: {indexed}/{len(mapping)}")
        print(f"  Errors: {errors}")
        print(f"  Total chunks: {total_chunks}")
        print(f"  Seed files saved to: {seed_dir}")
        print(f"  Final memory: {get_memory_usage_mb():.1f} MB")

        if validation.valid_documents == validation.total_documents:
            print("\n  All documents passed validation!")
        else:
            print(f"\n  WARNING: {validation.total_documents - validation.valid_documents} documents have issues")

    finally:
        await embedding_service.close()
        await solar_service.close()


if __name__ == "__main__":
    asyncio.run(main())
