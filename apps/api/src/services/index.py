"""Vector index service using FAISS."""

import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from numpy.typing import NDArray

from src.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class IndexService:
    """Service for managing vector index using FAISS."""

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.index_path = Path(os.getenv("VECTOR_STORE_PATH", "data/faiss"))
        self.index_path.mkdir(parents=True, exist_ok=True)

        self.chunk_size = int(os.getenv("CHUNK_SIZE", "500"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "100"))
        self.dimension = 1024  # SOLAR embedding dimension (solar-embedding-1-large)

        self._index: faiss.IndexFlatIP | None = None
        self._metadata: list[dict[str, Any]] = []
        # Use provided EmbeddingService or create a new one (for backward compatibility)
        self._embedding_service = embedding_service or EmbeddingService()

        self._load_or_create_index()

    def _load_or_create_index(self) -> None:
        """Load existing index, seed index, or create new one."""
        index_file = self.index_path / "index.faiss"
        metadata_file = self.index_path / "metadata.npy"

        # 1. Load existing local index if available
        if index_file.exists() and metadata_file.exists():
            self._index = faiss.read_index(str(index_file))
            self._metadata = list(np.load(str(metadata_file), allow_pickle=True))
            return

        # 2. Load seed index for demo (copy from fixtures/seed/)
        seed_dir = Path(os.getenv("SEED_INDEX_PATH", "fixtures/seed"))
        seed_index = seed_dir / "index.faiss"
        seed_metadata = seed_dir / "metadata.npy"

        if seed_index.exists() and seed_metadata.exists():
            # Copy seed files to local index path
            shutil.copy(seed_index, index_file)
            shutil.copy(seed_metadata, metadata_file)
            self._index = faiss.read_index(str(index_file))
            self._metadata = list(np.load(str(metadata_file), allow_pickle=True))

            # Also copy seed PDFs to local storage
            self._copy_seed_pdfs(seed_dir)
            return

        # 3. Create new empty index
        self._index = faiss.IndexFlatIP(self.dimension)
        self._metadata = []

    def _copy_seed_pdfs(self, seed_dir: Path) -> None:
        """Copy PDFs from seed directory to local storage."""
        seed_pdfs_dir = seed_dir / "pdfs"
        if not seed_pdfs_dir.exists():
            return

        pdf_storage_path = Path(os.getenv("PDF_STORAGE_PATH", "data/pdfs"))
        pdf_storage_path.mkdir(parents=True, exist_ok=True)

        copied = 0
        for pdf in seed_pdfs_dir.glob("*.pdf"):
            target = pdf_storage_path / pdf.name
            if not target.exists():
                shutil.copy(pdf, target)
                copied += 1

        if copied > 0:
            logger.info(f"Copied {copied} PDFs from seed to {pdf_storage_path}")

    def _save_index(self) -> None:
        """Save index to disk."""
        if self._index is None:
            return
        faiss.write_index(self._index, str(self.index_path / "index.faiss"))
        np.save(str(self.index_path / "metadata.npy"), np.array(self._metadata, dtype=object))

    def _chunk_text(self, text: str) -> list[dict[str, Any]]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk.

        Returns:
            List of chunk dictionaries with text and position info.
        """
        chunks = []
        start = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            # Try to break at sentence boundary
            if end < len(text):
                for sep in [". ", ".\n", "\n\n"]:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start:
                        end = last_sep + len(sep)
                        break

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "start_idx": start,
                    "end_idx": end,
                })

            start = end - self.chunk_overlap if end < len(text) else len(text)

        return chunks

    async def index_document(
        self,
        document_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        grounding: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Index a document by chunking and embedding.

        Args:
            document_id: Unique document identifier.
            content: Document text content.
            metadata: Optional metadata to store with chunks.
            grounding: Optional grounding info from SOLAR (page/bbox per element).

        Returns:
            Indexing result with chunk count.
        """
        if self._index is None:
            self._load_or_create_index()

        chunks = self._chunk_text(content)
        texts = [c["text"] for c in chunks]
        total_chars = len(content)

        embeddings = await self._embedding_service.embed_documents(texts)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{document_id}_{i}"

            # Find grounding info for this chunk using position-based estimation
            chunk_grounding = self._find_grounding_for_chunk(chunk, grounding, total_chars)

            # Normalize for cosine similarity
            normalized = embedding / np.linalg.norm(embedding)
            self._index.add(normalized.reshape(1, -1))

            self._metadata.append({
                "document_id": document_id,
                "chunk_id": chunk_id,
                "text": chunk["text"],
                "start_idx": chunk["start_idx"],
                "end_idx": chunk["end_idx"],
                "page": chunk_grounding.get("page", 1),
                "bbox": chunk_grounding.get("box"),
                **(metadata or {}),
            })

        self._save_index()

        return {
            "document_id": document_id,
            "chunk_count": len(chunks),
        }

    def _find_grounding_for_chunk(
        self,
        chunk: dict[str, Any],
        grounding: dict[str, Any] | None,
        total_chars: int = 0,
    ) -> dict[str, Any]:
        """
        Find the grounding info (page, bbox) for a text chunk.

        Uses character position to estimate page number based on the
        proportional position of the chunk within the document.

        Args:
            chunk: Chunk dict with start_idx, end_idx, text.
            grounding: SOLAR grounding dict mapping element_id to page/box.
            total_chars: Total character count of the document.

        Returns:
            Dict with 'page' and optionally 'box' keys.
        """
        if not grounding:
            return {"page": 1}

        # Get sorted pages from grounding info
        pages = sorted({
            info["page"]
            for info in grounding.values()
            if isinstance(info, dict) and "page" in info
        })

        if not pages:
            return {"page": 1}

        total_pages = max(pages)

        if total_pages == 1:
            return {"page": 1}

        # Estimate page based on character position ratio
        if total_chars > 0:
            chunk_midpoint = (chunk["start_idx"] + chunk["end_idx"]) / 2
            position_ratio = chunk_midpoint / total_chars
            estimated_page = int(position_ratio * total_pages) + 1
            return {"page": min(estimated_page, total_pages)}

        return {"page": 1}

    async def search(
        self,
        embedding: NDArray[np.float32],
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> list[dict[str, Any]]:
        """
        Search for similar chunks.

        Args:
            embedding: Query embedding vector.
            top_k: Number of results to return.
            threshold: Minimum similarity threshold.

        Returns:
            List of matching chunks with scores.
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        # Normalize query embedding
        normalized = embedding / np.linalg.norm(embedding)

        scores, indices = self._index.search(normalized.reshape(1, -1), top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or score < threshold:
                continue
            meta = self._metadata[idx]
            results.append({
                **meta,
                "score": float(score),
            })

        return results

    async def get_chunks(self, document_id: str) -> list[dict[str, Any]]:
        """
        Get all chunks for a document.

        Args:
            document_id: Document identifier.

        Returns:
            List of chunks for the document.
        """
        return [
            {
                "chunk_id": m["chunk_id"],
                "text": m["text"],
                "page": m.get("page"),
                "start_idx": m["start_idx"],
                "end_idx": m["end_idx"],
            }
            for m in self._metadata
            if m["document_id"] == document_id
        ]

    def list_documents(self) -> list[dict[str, Any]]:
        """
        List all indexed documents with their metadata.

        Returns:
            List of document info dictionaries.
        """
        documents: dict[str, dict[str, Any]] = {}

        for meta in self._metadata:
            doc_id = meta["document_id"]
            if doc_id not in documents:
                documents[doc_id] = {
                    "document_id": doc_id,
                    "title": meta.get("title"),
                    "authors": meta.get("authors"),
                    "chunk_count": 0,
                    "indexed_at": meta.get("indexed_at"),
                }
            documents[doc_id]["chunk_count"] += 1

        return list(documents.values())

    def delete_document(self, document_id: str) -> int:
        """
        Delete a document and all its chunks from the index.

        Args:
            document_id: Document identifier to delete.

        Returns:
            Number of chunks deleted.
        """
        if self._index is None:
            return 0

        # Find indices to keep (not matching document_id)
        indices_to_keep = [
            i for i, m in enumerate(self._metadata)
            if m["document_id"] != document_id
        ]

        deleted_count = len(self._metadata) - len(indices_to_keep)

        if deleted_count == 0:
            return 0

        # Rebuild index with only kept vectors
        if indices_to_keep:
            # Get vectors for kept indices
            kept_vectors = np.array([
                self._index.reconstruct(i) for i in indices_to_keep
            ])
            kept_metadata = [self._metadata[i] for i in indices_to_keep]

            # Create new index
            self._index = faiss.IndexFlatIP(self.dimension)
            self._index.add(kept_vectors)
            self._metadata = kept_metadata
        else:
            # All documents deleted, create empty index
            self._index = faiss.IndexFlatIP(self.dimension)
            self._metadata = []

        self._save_index()

        return deleted_count
