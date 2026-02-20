"""Unit tests for Visual Search Strategy (Phase 55)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

from src.pdf_framework.search.strategies.visual import VisualSearchStrategy
from src.pdf_framework.schemas.documents import SearchResult, DocumentChunk


@pytest.fixture
def mock_colpali():
    """Mock ColPali provider."""
    provider = MagicMock()
    provider.embed_query = MagicMock(return_value=Mock())
    return provider


@pytest.fixture
def mock_vector_store():
    """Mock vector store."""
    store = AsyncMock()
    store.search = AsyncMock(return_value=[
        SearchResult(
            chunk=DocumentChunk(
                id="page_001",
                content="Visual page 0",
                document_id="doc1",
                page_number=0,
                section="visual",
            ),
            score=0.85,
            source="qdrant_visual",
        ),
    ])
    store.visual_search = AsyncMock(return_value=[
        SearchResult(
            chunk=DocumentChunk(
                id="page_001",
                content="Visual page 0",
                document_id="doc1",
                page_number=0,
                section="visual",
            ),
            score=0.90,
            source="qdrant_visual",
        ),
    ])
    return store


@pytest.fixture
def visual_strategy(mock_colpali, mock_vector_store):
    """Visual search strategy fixture."""
    return VisualSearchStrategy(
        colpali_provider=mock_colpali,
        vector_store=mock_vector_store,
        visual_collection="visual_pages",
    )


class TestVisualSearchStrategy:
    """Tests for VisualSearchStrategy."""

    @pytest.mark.asyncio
    async def test_search_basic(self, visual_strategy, mock_colpali):
        """Test basic visual search."""
        # Mock query embedding
        import torch
        mock_tensor = torch.randn(32, 128)
        mock_colpali.embed_query.return_value = mock_tensor

        response = await visual_strategy.search("table with revenue")

        assert response.query == "table with revenue"
        assert response.search_type == "visual"
        assert len(response.results) > 0
        assert response.results[0].source == "qdrant_visual"

    @pytest.mark.asyncio
    async def test_search_with_document_filter(self, visual_strategy):
        """Test visual search with document filter."""
        response = await visual_strategy.search(
            "chart showing sales",
            document_id="doc123",
        )

        assert response.total_found >= 0

    @pytest.mark.asyncio
    async def test_hybrid_visual_text_search(self, visual_strategy, mock_colpali):
        """Test hybrid visual+text search with RRF fusion."""
        import torch
        mock_tensor = torch.randn(32, 128)
        mock_colpali.embed_query.return_value = mock_tensor

        response = await visual_strategy.hybrid_visual_text_search(
            query="diagram showing process",
            text_embedding=[0.1] * 128,
            k=5,
            visual_weight=0.6,
            text_weight=0.4,
        )

        assert response.search_type == "hybrid_visual_text"
        assert response.metadata.get("visual_weight") == 0.6
        assert response.metadata.get("text_weight") == 0.4

    def test_rrf_fusion(self, visual_strategy):
        """Test RRF fusion algorithm."""
        from src.pdf_framework.schemas.documents import SearchResult

        visual_results = [
            SearchResult(
                chunk=DocumentChunk(
                    id="chunk1",
                    content="Visual result",
                    document_id="doc1",
                    page_number=1,
                    section="visual",
                ),
                score=0.9,
                source="visual",
            ),
            SearchResult(
                chunk=DocumentChunk(
                    id="chunk2",
                    content="Another visual",
                    document_id="doc1",
                    page_number=2,
                    section="visual",
                ),
                score=0.8,
                source="visual",
            ),
        ]

        text_results = [
            SearchResult(
                chunk=DocumentChunk(
                    id="chunk2",
                    content="Text result",
                    document_id="doc1",
                    page_number=2,
                    section="text",
                ),
                score=0.85,
                source="text",
            ),
            SearchResult(
                chunk=DocumentChunk(
                    id="chunk3",
                    content="Another text",
                    document_id="doc1",
                    page_number=3,
                    section="text",
                ),
                score=0.75,
                source="text",
            ),
        ]

        fused = visual_strategy._rrf_fusion(
            visual_results=visual_results,
            text_results=text_results,
            visual_weight=0.5,
            text_weight=0.5,
        )

        # chunk2 appears in both results, should have highest combined score
        assert len(fused) == 3  # chunk1, chunk2, chunk3
        assert fused[0].chunk.id == "chunk2"  # Should be ranked first (RRF boost)

    @pytest.mark.asyncio
    async def test_search_fallback_without_visual_method(self, mock_colpali):
        """Test fallback when visual_search method is not available."""
        store = AsyncMock()
        store.search = AsyncMock(return_value=[])
        del store.visual_search  # Remove visual_search method

        strategy = VisualSearchStrategy(
            colpali_provider=mock_colpali,
            vector_store=store,
        )

        import torch
        mock_tensor = torch.randn(32, 128)
        mock_colpali.embed_query.return_value = mock_tensor

        response = await strategy.search("table")

        assert response.total_found == 0


@pytest.mark.unit
def test_create_visual_search_strategy(mock_colpali, mock_vector_store):
    """Test factory function."""
    from src.pdf_framework.search.strategies.visual import create_visual_search_strategy

    strategy = create_visual_search_strategy(
        colpali_provider=mock_colpai,
        vector_store=mock_vector_store,
        visual_collection="test_visual",
    )

    assert strategy._visual_collection == "test_visual"
