"""Unit tests for ChromaDB index operations."""

import numpy as np
import pytest


class TestIndexDocument:
    """Tests for IndexService.index_document method."""

    @pytest.mark.asyncio
    async def test_index_document_creates_chunks(self, isolated_index_service) -> None:
        """Verify indexing returns correct chunk count."""
        content = "This is test content. " * 50  # ~1100 chars

        result = await isolated_index_service.index_document(
            document_id="test-doc-001",
            content=content,
            metadata={"title": "Test Document"},
        )

        assert result["document_id"] == "test-doc-001"
        assert result["chunk_count"] > 0
        assert result["chunk_count"] <= len(content) // 100  # Reasonable bound

    @pytest.mark.asyncio
    async def test_index_document_stores_in_chroma(self, isolated_index_service) -> None:
        """Verify ChromaDB collection count increases after indexing."""
        initial_count = isolated_index_service._collection.count()

        await isolated_index_service.index_document(
            document_id="test-doc-002",
            content="Document content for testing vector storage.",
        )

        final_count = isolated_index_service._collection.count()
        assert final_count > initial_count

    @pytest.mark.asyncio
    async def test_index_document_with_grounding(self, isolated_index_service) -> None:
        """Verify grounding info is stored with chunks."""
        grounding = {
            "elem_1": {"page": 1, "box": [0, 0, 100, 100]},
            "elem_2": {"page": 2, "box": [0, 100, 100, 200]},
        }

        await isolated_index_service.index_document(
            document_id="test-doc-003",
            content="Content with grounding info. " * 30,
            grounding=grounding,
        )

        chunks = await isolated_index_service.get_chunks("test-doc-003")
        assert len(chunks) > 0
        # Page info should be assigned
        for chunk in chunks:
            assert "page" in chunk


class TestSearch:
    """Tests for IndexService.search method."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, seed_index_service) -> None:
        """Verify search returns non-empty results from seed index."""
        # Generate a random query vector
        query_embedding = np.random.default_rng(42).random(4096).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        results = await seed_index_service.search(
            embedding=query_embedding,
            top_k=5,
            threshold=-1.0,  # Accept all results
        )

        assert len(results) > 0
        assert all("text" in r for r in results)
        assert all("score" in r for r in results)

    @pytest.mark.asyncio
    async def test_search_respects_top_k(self, seed_index_service) -> None:
        """Verify result count respects top_k parameter."""
        query_embedding = np.random.default_rng(42).random(4096).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        for top_k in [1, 3, 5]:
            results = await seed_index_service.search(
                embedding=query_embedding,
                top_k=top_k,
                threshold=-1.0,  # Accept all results
            )
            assert len(results) <= top_k

    @pytest.mark.asyncio
    async def test_search_respects_threshold(self, seed_index_service) -> None:
        """Verify all results meet minimum threshold."""
        query_embedding = np.random.default_rng(42).random(4096).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        threshold = 0.5
        results = await seed_index_service.search(
            embedding=query_embedding,
            top_k=10,
            threshold=threshold,
        )

        for result in results:
            assert result["score"] >= threshold, (
                f"Score {result['score']} below threshold {threshold}"
            )

    @pytest.mark.asyncio
    async def test_search_empty_index_returns_empty(
        self, isolated_index_service
    ) -> None:
        """Verify search on empty index returns empty list."""
        query_embedding = np.random.default_rng(42).random(4096).astype(np.float32)

        results = await isolated_index_service.search(
            embedding=query_embedding,
            top_k=5,
            threshold=0.0,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_search_results_ordered_by_score(self, seed_index_service) -> None:
        """Verify results are ordered by score descending."""
        query_embedding = np.random.default_rng(42).random(4096).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        results = await seed_index_service.search(
            embedding=query_embedding,
            top_k=10,
            threshold=-1.0,  # Accept all results
        )

        if len(results) >= 2:
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True), "Results not sorted by score"


class TestGrounding:
    """Tests for grounding estimation in IndexService."""

    def test_find_grounding_no_grounding_returns_page_1(
        self, isolated_index_service
    ) -> None:
        """Verify no grounding returns default page 1."""
        chunk = {"start_idx": 0, "end_idx": 100, "text": "Test"}
        result = isolated_index_service._find_grounding_for_chunk(
            chunk, grounding=None, total_chars=100
        )
        assert result == {"page": 1}

    def test_find_grounding_empty_pages_returns_page_1(
        self, isolated_index_service
    ) -> None:
        """Verify empty grounding returns default page 1."""
        chunk = {"start_idx": 0, "end_idx": 100, "text": "Test"}
        result = isolated_index_service._find_grounding_for_chunk(
            chunk, grounding={}, total_chars=100
        )
        assert result == {"page": 1}

    def test_find_grounding_single_page(self, isolated_index_service) -> None:
        """Verify single page document returns page 1."""
        chunk = {"start_idx": 50, "end_idx": 100, "text": "Test"}
        grounding = {"elem_1": {"page": 1, "box": [0, 0, 100, 100]}}
        result = isolated_index_service._find_grounding_for_chunk(
            chunk, grounding=grounding, total_chars=100
        )
        assert result == {"page": 1}

    def test_find_grounding_multi_page_estimates_page(
        self, isolated_index_service
    ) -> None:
        """Verify multi-page documents estimate page from position."""
        grounding = {
            "elem_1": {"page": 1, "box": [0, 0, 100, 100]},
            "elem_2": {"page": 2, "box": [0, 0, 100, 100]},
            "elem_3": {"page": 3, "box": [0, 0, 100, 100]},
        }

        # Chunk at the start should be page 1
        chunk_start = {"start_idx": 0, "end_idx": 100, "text": "Start"}
        result = isolated_index_service._find_grounding_for_chunk(
            chunk_start, grounding=grounding, total_chars=1000
        )
        assert result["page"] == 1

        # Chunk at the end should be page 3
        chunk_end = {"start_idx": 900, "end_idx": 1000, "text": "End"}
        result = isolated_index_service._find_grounding_for_chunk(
            chunk_end, grounding=grounding, total_chars=1000
        )
        assert result["page"] == 3

    def test_find_grounding_zero_total_chars(self, isolated_index_service) -> None:
        """Verify zero total_chars returns page 1."""
        chunk = {"start_idx": 0, "end_idx": 100, "text": "Test"}
        grounding = {
            "elem_1": {"page": 1},
            "elem_2": {"page": 2},
        }
        result = isolated_index_service._find_grounding_for_chunk(
            chunk, grounding=grounding, total_chars=0
        )
        assert result == {"page": 1}

    def test_find_grounding_invalid_grounding_entries(
        self, isolated_index_service
    ) -> None:
        """Verify invalid grounding entries are skipped."""
        chunk = {"start_idx": 0, "end_idx": 100, "text": "Test"}
        grounding = {
            "elem_1": "not a dict",
            "elem_2": {"no_page_key": True},
            "elem_3": {"page": 1, "box": [0, 0, 100, 100]},
        }
        result = isolated_index_service._find_grounding_for_chunk(
            chunk, grounding=grounding, total_chars=100
        )
        assert result == {"page": 1}


class TestDeleteDocument:
    """Tests for IndexService.delete_document method."""

    @pytest.mark.asyncio
    async def test_delete_document_removes_chunks(self, isolated_index_service) -> None:
        """Verify document deletion removes all its chunks."""
        # First index a document
        await isolated_index_service.index_document(
            document_id="delete-test-001",
            content="Content to be deleted. " * 20,
        )

        initial_count = isolated_index_service._collection.count()
        assert initial_count > 0

        # Delete the document
        deleted = isolated_index_service.delete_document("delete-test-001")

        assert deleted > 0
        assert isolated_index_service._collection.count() < initial_count

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_zero(
        self, isolated_index_service
    ) -> None:
        """Verify deleting non-existent document returns zero."""
        deleted = isolated_index_service.delete_document("nonexistent-doc")
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_delete_preserves_other_documents(
        self, isolated_index_service
    ) -> None:
        """Verify deletion only removes target document."""
        # Index multiple documents
        await isolated_index_service.index_document(
            document_id="keep-doc-001",
            content="This document should be kept. " * 20,
        )
        await isolated_index_service.index_document(
            document_id="delete-doc-001",
            content="This document will be deleted. " * 20,
        )

        # Delete one
        isolated_index_service.delete_document("delete-doc-001")

        # Check kept document is still searchable
        docs = isolated_index_service.list_documents()
        doc_ids = [d["document_id"] for d in docs]

        assert "keep-doc-001" in doc_ids
        assert "delete-doc-001" not in doc_ids

    @pytest.mark.asyncio
    async def test_delete_all_documents_creates_empty_index(
        self, isolated_index_service
    ) -> None:
        """Verify deleting all documents leaves empty collection."""
        # Index a single document
        await isolated_index_service.index_document(
            document_id="only-doc-001",
            content="Single document content. " * 10,
        )

        assert isolated_index_service._collection.count() > 0

        # Delete the only document
        deleted = isolated_index_service.delete_document("only-doc-001")

        assert deleted > 0
        assert isolated_index_service._collection.count() == 0
        assert isolated_index_service.list_documents() == []
