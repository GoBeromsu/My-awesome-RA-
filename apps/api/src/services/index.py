"""Vector index service using ChromaDB."""

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Iterable

import chromadb
import numpy as np
from numpy.typing import NDArray

from src.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class IndexService:
    """Service for managing vector index using ChromaDB."""

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.index_path = Path(os.getenv("VECTOR_STORE_PATH", "data/chroma"))
        self.index_path.mkdir(parents=True, exist_ok=True)

        self.chunk_size = int(os.getenv("CHUNK_SIZE", "500"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "100"))
        self.dimension = 4096  # SOLAR embedding dimension (solar-embedding-1-large)

        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None
        # Use provided EmbeddingService or create a new one (for backward compatibility)
        self._embedding_service = embedding_service or EmbeddingService()

        self._load_or_create_index()

    def _build_collection_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {"hnsw:space": os.getenv("HNSW_SPACE", "cosine")}
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
                try:
                    metadata[meta_key] = int(value)
                except ValueError:
                    logger.warning(f"Invalid integer for {env_key}: {value}, skipping")

        resize_factor = os.getenv("HNSW_RESIZE_FACTOR")
        if resize_factor:
            try:
                metadata["hnsw:resize_factor"] = float(resize_factor)
            except ValueError:
                logger.warning(f"Invalid float for HNSW_RESIZE_FACTOR: {resize_factor}, skipping")

        batch_size = metadata.get("hnsw:batch_size")
        sync_threshold = metadata.get("hnsw:sync_threshold")
        if isinstance(batch_size, int) and isinstance(sync_threshold, int):
            if batch_size > sync_threshold:
                logger.warning(
                    "HNSW_BATCH_SIZE (%s) > HNSW_SYNC_THRESHOLD (%s); "
                    "clamping batch size to sync threshold.",
                    batch_size,
                    sync_threshold,
                )
                metadata["hnsw:batch_size"] = sync_threshold

        return metadata

    def _init_client_and_collection(self) -> None:
        """Initialize ChromaDB client and collection at self.index_path."""
        self._client = chromadb.PersistentClient(path=str(self.index_path))
        self._collection = self._client.get_or_create_collection(
            name="documents",
            metadata=self._build_collection_metadata(),
        )

    def _load_or_create_index(self) -> None:
        """Load existing index, seed index, or create new one."""
        chroma_db_file = self.index_path / "chroma.sqlite3"
        seed_dir = Path(os.getenv("SEED_INDEX_PATH", "fixtures/seed"))
        seed_chroma_db = seed_dir / "chroma.sqlite3"
        reset_to_seed = os.getenv("RESET_TO_SEED", "false").lower() == "true"

        # 1. If RESET_TO_SEED=true and seed exists, always reset to seed state
        if reset_to_seed and seed_chroma_db.exists():
            self._reset_to_seed(seed_dir)
            return

        # 2. Load existing local index if available
        if chroma_db_file.exists():
            self._init_client_and_collection()
            logger.info(f"Loaded existing ChromaDB with {self._collection.count()} vectors")
            return

        # 3. Load seed index for demo (copy from fixtures/seed/)
        if seed_chroma_db.exists():
            self._copy_seed_files(seed_dir)
            self._init_client_and_collection()
            self._copy_seed_pdfs(seed_dir)
            logger.info(f"Loaded seed ChromaDB with {self._collection.count()} vectors")
            return

        # 4. Create new empty collection
        self._init_client_and_collection()
        logger.info("Created new empty ChromaDB collection")

    def _reset_to_seed(self, seed_dir: Path) -> None:
        """Reset index to seed state by clearing and copying from seed."""
        logger.info("RESET_TO_SEED=true, resetting to seed state...")

        # Clear existing data
        if self.index_path.exists():
            for item in self.index_path.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)

        # Clear PDF storage
        pdf_storage_path = Path(os.getenv("PDF_STORAGE_PATH", "data/pdfs"))
        if pdf_storage_path.exists():
            for pdf in pdf_storage_path.glob("*.pdf"):
                pdf.unlink()

        # Copy seed files
        self._copy_seed_files(seed_dir)
        self._init_client_and_collection()
        self._copy_seed_pdfs(seed_dir)
        logger.info(f"Reset to seed ChromaDB with {self._collection.count()} vectors")

    def _copy_seed_files(self, seed_dir: Path) -> None:
        """Copy ChromaDB files from seed directory to local index path."""
        for item in seed_dir.iterdir():
            if item.is_file():
                shutil.copy(item, self.index_path / item.name)
            elif item.is_dir() and item.name != "pdfs":
                target_dir = self.index_path / item.name
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(item, target_dir)

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

    def _iter_chunks(self, text: str) -> Iterable[dict[str, Any]]:
        """
        Yield overlapping chunks.

        Args:
            text: Text to chunk.

        Yields:
            Chunk dictionaries with text and position info.
        """
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
                yield {
                    "text": chunk_text,
                    "start_idx": start,
                    "end_idx": end,
                }

            start = end - self.chunk_overlap if end < len(text) else len(text)

    def _chunk_text(self, text: str) -> list[dict[str, Any]]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk.

        Returns:
            List of chunk dictionaries with text and position info.
        """
        return list(self._iter_chunks(text))

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
        if self._collection is None:
            self._load_or_create_index()

        total_chars = len(content)
        batch_size = max(1, int(os.getenv("INDEX_BATCH_SIZE", str(self._embedding_service.BATCH_SIZE))))

        chunk_count = 0
        batch_chunks: list[dict[str, Any]] = []
        batch_indices: list[int] = []

        async def upsert_batch() -> None:
            if not batch_chunks:
                return

            texts = [c["text"] for c in batch_chunks]
            embeddings = await self._embedding_service.embed_documents(texts)

            ids: list[str] = []
            embeddings_list: list[list[float]] = []
            documents: list[str] = []
            metadatas: list[dict[str, Any]] = []

            for idx, chunk, embedding in zip(batch_indices, batch_chunks, embeddings):
                chunk_id = f"{document_id}_{idx}"

                # Find grounding info for this chunk using position-based estimation
                chunk_grounding = self._find_grounding_for_chunk(chunk, grounding, total_chars)

                # Normalize for cosine similarity
                normalized = embedding / np.linalg.norm(embedding)

                ids.append(chunk_id)
                embeddings_list.append(normalized.tolist())
                documents.append(chunk["text"])
                metadatas.append({
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "start_idx": chunk["start_idx"],
                    "end_idx": chunk["end_idx"],
                    "page": chunk_grounding.get("page", 1),
                    "bbox": str(chunk_grounding.get("box")) if chunk_grounding.get("box") else None,
                    **(metadata or {}),
                })

            # Upsert batch
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings_list,
                documents=documents,
                metadatas=metadatas,
            )

            batch_chunks.clear()
            batch_indices.clear()

        for chunk in self._iter_chunks(content):
            batch_chunks.append(chunk)
            batch_indices.append(chunk_count)
            chunk_count += 1

            if len(batch_chunks) >= batch_size:
                await upsert_batch()

        if batch_chunks:
            await upsert_batch()

        return {
            "document_id": document_id,
            "chunk_count": chunk_count,
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

        # Get page numbers from grounding info
        pages = {
            info["page"]
            for info in grounding.values()
            if isinstance(info, dict) and "page" in info
        }

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
        if self._collection is None or self._collection.count() == 0:
            return []

        # Normalize query embedding
        normalized = embedding / np.linalg.norm(embedding)

        results = self._collection.query(
            query_embeddings=[normalized.tolist()],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                # ChromaDB returns cosine distance, convert to similarity score
                distance = results["distances"][0][i] if results["distances"] else 0
                score = 1.0 - distance

                if score < threshold:
                    continue

                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                text = results["documents"][0][i] if results["documents"] else ""

                search_results.append({
                    "document_id": meta.get("document_id", ""),
                    "chunk_id": chunk_id,
                    "text": text,
                    "start_idx": meta.get("start_idx", 0),
                    "end_idx": meta.get("end_idx", 0),
                    "page": meta.get("page", 1),
                    "bbox": meta.get("bbox"),
                    "score": float(score),
                    # Include any additional metadata
                    **{k: v for k, v in meta.items() if k not in [
                        "document_id", "chunk_id", "start_idx", "end_idx", "page", "bbox"
                    ]},
                })

        # Sort by score descending (should already be sorted, but ensure it)
        search_results.sort(key=lambda x: x["score"], reverse=True)

        return search_results

    async def get_chunks(self, document_id: str) -> list[dict[str, Any]]:
        """
        Get all chunks for a document.

        Args:
            document_id: Document identifier.

        Returns:
            List of chunks for the document.
        """
        if self._collection is None:
            return []

        results = self._collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"],
        )

        chunks = []
        if results["ids"]:
            for i, chunk_id in enumerate(results["ids"]):
                meta = results["metadatas"][i] if results["metadatas"] else {}
                text = results["documents"][i] if results["documents"] else ""

                chunks.append({
                    "chunk_id": chunk_id,
                    "text": text,
                    "page": meta.get("page"),
                    "start_idx": meta.get("start_idx", 0),
                    "end_idx": meta.get("end_idx", 0),
                })

        return chunks

    def _parse_cite_key_metadata(self, cite_key: str | None) -> dict[str, Any]:
        """
        Parse metadata from cite_key pattern: Author2024Title.

        Args:
            cite_key: Citation key string (e.g., "Vaswani2017Attention").

        Returns:
            Dict with parsed authors, year, and title (may be empty).
        """
        import re

        if not cite_key:
            return {}

        # Pattern: Author(s)Year(4 digits)Title
        # Examples: Vaswani2017Attention, BrownMann2020Language
        match = re.match(r"^([A-Za-z\-]+)(\d{4})(.+)$", cite_key)
        if match:
            authors_part = match.group(1)
            year_str = match.group(2)
            title_part = match.group(3)

            # Convert CamelCase to readable: "BrownMann" -> "Brown, Mann"
            # Split on uppercase letters
            authors = re.sub(r"([a-z])([A-Z])", r"\1, \2", authors_part)

            # Convert CamelCase title to readable: "Attention" -> "Attention"
            # Add spaces before capitals: "LanguageModels" -> "Language Models"
            title = re.sub(r"([a-z])([A-Z])", r"\1 \2", title_part)

            return {
                "authors": authors,
                "year": int(year_str),
                "title": title,
            }
        return {}

    def list_documents(self) -> list[dict[str, Any]]:
        """
        List all indexed documents with their metadata.

        Returns:
            List of document info dictionaries.
        """
        if self._collection is None or self._collection.count() == 0:
            return []

        # Get all items from collection
        results = self._collection.get(include=["metadatas"])

        documents: dict[str, dict[str, Any]] = {}

        if results["metadatas"]:
            for meta in results["metadatas"]:
                doc_id = meta.get("document_id", "")
                if not doc_id:
                    continue

                if doc_id not in documents:
                    cite_key = meta.get("cite_key")

                    # Fallback: parse metadata from cite_key if not stored
                    parsed = self._parse_cite_key_metadata(cite_key)

                    documents[doc_id] = {
                        "document_id": doc_id,
                        "cite_key": cite_key,
                        "title": meta.get("title") or parsed.get("title"),
                        "authors": meta.get("authors") or parsed.get("authors"),
                        "year": meta.get("year") or parsed.get("year"),
                        "page_count": meta.get("page_count") or meta.get("pages"),
                        "chunk_count": 0,
                        "indexed_at": meta.get("indexed_at"),
                        "has_pdf": True,  # Documents in ChromaDB came from indexed PDFs
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
        if self._collection is None:
            return 0

        # First count how many chunks exist for this document
        existing = self._collection.get(
            where={"document_id": document_id},
            include=[],  # We only need the count
        )

        if not existing["ids"]:
            return 0

        deleted_count = len(existing["ids"])

        # Delete by IDs (more reliable than where clause for some versions)
        self._collection.delete(ids=existing["ids"])

        return deleted_count
