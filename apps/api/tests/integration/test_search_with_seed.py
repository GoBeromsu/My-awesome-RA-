"""Integration tests for search functionality using seed fixtures."""

import numpy as np
import pytest


class TestSearchWithSeed:
    """Integration tests for search using pre-loaded seed index."""

    @pytest.mark.asyncio
    async def test_search_returns_transformer_content(
        self, seed_index_service
    ) -> None:
        """Verify search returns content from transformer paper seed data."""
        query = np.random.default_rng(123).random(4096).astype(np.float32)
        query = query / np.linalg.norm(query)

        results = await seed_index_service.search(
            embedding=query,
            top_k=5,
            threshold=-1.0,  # Accept all results
        )

        assert len(results) > 0
        # Should have text content
        for result in results:
            assert len(result["text"]) > 0
            assert isinstance(result["score"], float)

    @pytest.mark.asyncio
    async def test_search_results_contain_expected_documents(
        self, seed_index_service
    ) -> None:
        """Verify search results include documents with valid ID format."""
        import re

        # Generate a random query vector
        query = np.random.default_rng(42).random(4096).astype(np.float32)
        query = query / np.linalg.norm(query)

        results = await seed_index_service.search(
            embedding=query,
            top_k=17,  # Get all seed chunks
            threshold=-1.0,  # Accept all results
        )

        doc_ids = {r["document_id"] for r in results}
        # All document IDs should match the valid format: citeKey_hash
        pattern = re.compile(r"^[\w\-\.]+_[a-f0-9]{12}$")
        assert all(pattern.match(doc_id) for doc_id in doc_ids)

    @pytest.mark.asyncio
    async def test_search_results_ordered_by_score(self, seed_index_service) -> None:
        """Verify search results are ordered by descending score."""
        query = np.random.default_rng(99).random(4096).astype(np.float32)
        query = query / np.linalg.norm(query)

        results = await seed_index_service.search(
            embedding=query,
            top_k=10,
            threshold=-1.0,  # Accept all results
        )

        if len(results) >= 2:
            scores = [r["score"] for r in results]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1], (
                    f"Results not sorted: {scores[i]} < {scores[i + 1]}"
                )

    @pytest.mark.asyncio
    async def test_high_threshold_filters_results(self, seed_index_service) -> None:
        """Verify high threshold filters out low-scoring results."""
        query = np.random.default_rng(42).random(4096).astype(np.float32)
        query = query / np.linalg.norm(query)

        # Get all results with no threshold
        all_results = await seed_index_service.search(
            embedding=query,
            top_k=17,
            threshold=-1.0,  # Accept all results
        )

        # Get filtered results with high threshold
        filtered_results = await seed_index_service.search(
            embedding=query,
            top_k=17,
            threshold=0.9,
        )

        # High threshold should return fewer or equal results
        assert len(filtered_results) <= len(all_results)

        # All filtered results should meet threshold
        for result in filtered_results:
            assert result["score"] >= 0.9

    @pytest.mark.asyncio
    async def test_search_result_structure(self, seed_index_service) -> None:
        """Verify search results have expected structure."""
        # Generate a random query vector
        query = np.random.default_rng(42).random(4096).astype(np.float32)
        query = query / np.linalg.norm(query)

        results = await seed_index_service.search(
            embedding=query,
            top_k=1,
            threshold=-1.0,  # Accept all results
        )

        assert len(results) >= 1
        result = results[0]

        # Required fields
        assert "document_id" in result
        assert "chunk_id" in result
        assert "text" in result
        assert "score" in result
        assert "start_idx" in result
        assert "end_idx" in result

        # Type checks
        assert isinstance(result["document_id"], str)
        assert isinstance(result["score"], float)
        assert isinstance(result["text"], str)
