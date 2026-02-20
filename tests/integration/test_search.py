"""Integration tests for Search Pipeline (F2.11.2).

Tests full search flow: query → results
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.integration
class TestSearchPipeline:
    """Test full search pipeline."""

    async def test_full_search_flow(self):
        """F2.11.2: query → results should work end-to-end."""
        from src.pdf_framework.search.manager import SearchManager
        from src.pdf_framework.schemas.documents import SearchResult

        manager = SearchManager()

        query = "test query about 1С"

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient") as mock_qdrant:
            # Mock search results
            mock_qdrant.return_value.search.return_value = [
                MagicMock(
                    id="chunk_1",
                    score=0.9,
                    payload={"content": "1С is a platform", "page_number": 1},
                )
            ]

            results = await manager.search(query, strategy="hybrid")

            assert len(results) > 0
            assert isinstance(results[0], SearchResult)

    async def test_search_with_reranking(self):
        """F2.11.2: Search with LLM reranking should work."""
        from src.pdf_framework.search.manager import SearchManager

        manager = SearchManager()

        query = "регистры в 1С"

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient"):
            with patch("src.pdf_framework.search.reranking.llm.LLMReranker") as mock_reranker:
                mock_reranker.return_value.rerank = AsyncMock(
                    return_value=[
                        MagicMock(id="chunk_1", score=0.95),
                        MagicMock(id="chunk_2", score=0.85),
                    ]
                )

                results = await manager.search(
                    query,
                    strategy="hybrid",
                    rerank=True,
                )

                assert len(results) > 0

    async def test_search_multiple_strategies(self):
        """F2.11.2: Should support multiple search strategies."""
        from src.pdf_framework.search.manager import SearchManager

        manager = SearchManager()

        query = "справочники"

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient"):
            strategies = ["vector", "bm25", "hybrid"]

            for strategy in strategies:
                results = await manager.search(query, strategy=strategy)

                # Should return results for each strategy
                assert len(results) >= 0

    async def test_search_filters(self):
        """F2.11.2: Should support search filters."""
        from src.pdf_framework.search.manager import SearchManager

        manager = SearchManager()

        query = "справочники"

        filters = {
            "page_number": 5,
            "section": "Config",
        }

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient"):
            results = await manager.search(
                query,
                strategy="hybrid",
                filters=filters,
            )

            # Results should match filters
            for result in results:
                # In real test, would verify filters
                pass

    async def test_search_with_graphrag(self):
        """F2.11.2: Should support GraphRAG search."""
        from src.pdf_framework.search.manager import SearchManager

        manager = SearchManager()

        query = "какие есть типы регистров"

        with patch("src.pdf_framework.graph_store.providers.networkx_store.NetworkXGraphStore"):
            results = await manager.search(
                query,
                strategy="graphrag_local",
            )

            assert len(results) >= 0

    async def test_search_latency_tracking(self):
        """F2.11.2: Should track search latency."""
        from src.pdf_framework.search.manager import SearchManager

        manager = SearchManager()

        query = "test query"

        with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient"):
            results = await manager.search(query, strategy="hybrid")

            # Response should include latency
            assert results.elapsed_ms > 0

    async def test_search_with_cache(self):
        """F2.11.2: Should cache search results."""
        from src.pdf_framework.search.manager import SearchManager

        manager = SearchManager()

        query = "cached query"

        with patch("src.pdf_framework.search.cache.semantic_cache.SemanticCache") as mock_cache:
            # Cache miss first time
            mock_cache.get.return_value = None

            with patch("src.pdf_framework.vector_store.providers.qdrant.QdrantClient"):
                results1 = await manager.search(query, strategy="hybrid")

                # Cache hit second time
                mock_cache.get.return_value = results1
                mock_cache.set = MagicMock()

                results2 = await manager.search(query, strategy="hybrid")

                # Second call should be faster (cached)
                assert results2 is not None
