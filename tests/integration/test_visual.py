"""Integration tests for Visual Search (Phase 55)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.indexing.visual_indexer import (
    VisualIndexer,
    VisualIndexConfig,
    VisualPage,
)
from src.pdf_framework.search.strategies.visual import VisualSearchStrategy
from src.pdf_framework.schemas.documents import SearchResult, DocumentChunk


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Create a minimal PDF for testing."""
    # For now, return a mock path since we can't create real PDFs in tests
    # In real tests, use a fixture PDF from test data
    return Path("tests/data/sample.pdf")


@pytest.fixture
def visual_index_config():
    """Visual index configuration."""
    return VisualIndexConfig(
        collection_name="test_visual_pages",
        model_name="colpali-v1.3",
        render_dpi=150,
        batch_size=2,
        store_thumbnails=False,  # Disable for faster tests
    )


@pytest.fixture
def mock_colpali():
    """Mock ColPali provider for testing."""
    provider = MagicMock()

    import torch
    # Mock multi-vector embeddings
    provider.embed_image = MagicMock(
        return_value=torch.randn(128, 128)  # (n_tokens, dim)
    )
    provider.embed_query = MagicMock(
        return_value=torch.randn(32, 128)  # (query_tokens, dim)
    )
    provider.dimensions = 128
    provider.model = MagicMock()

    return provider


@pytest.fixture
def mock_page_renderer():
    """Mock page renderer."""
    from PIL import Image

    renderer = MagicMock()

    # Create mock images
    mock_images = [
        (0, Image.new("RGB", (800, 600), color="white")),
        (1, Image.new("RGB", (800, 600), color="gray")),
    ]

    renderer.render_pages = MagicMock(return_value=mock_images)
    renderer.render_page = MagicMock(
        side_effect=lambda doc, n: mock_images[n][1]
    )

    return renderer


@pytest.fixture
def visual_indexer(visual_index_config, mock_colpali, mock_page_renderer):
    """Visual indexer fixture with mocked dependencies."""
    indexer = VisualIndexer(
        config=visual_index_config,
        colpali_provider=mock_colpali,
        page_renderer=mock_page_renderer,
    )
    return indexer


@pytest.mark.integration
class TestVisualIndexer:
    """Integration tests for VisualIndexer."""

    def test_index_pdf(self, visual_indexer, sample_pdf_path, mock_page_renderer):
        """Test indexing a PDF document."""
        pages = visual_indexer.index_pdf(
            pdf_path=sample_pdf_path,
            document_id="test_doc_001",
        )

        assert len(pages) == 2  # From mock renderer
        assert all(isinstance(p, VisualPage) for p in pages)
        assert pages[0].document_id == "test_doc_001"
        assert pages[0].page_number == 0
        assert pages[0].embedding.shape[1] == 128  # ColPali dimension

    def test_index_single_page(self, visual_indexer):
        """Test indexing a single page."""
        from PIL import Image

        img = Image.new("RGB", (800, 600))
        page = visual_indexer.index_page(
            image=img,
            document_id="test_doc",
            page_number=0,
        )

        assert isinstance(page, VisualPage)
        assert page.page_number == 0
        assert page.embedding.shape[1] == 128

    def test_search_indexed_pages(self, visual_indexer):
        """Test searching within indexed pages."""
        # Create mock indexed pages
        import numpy as np

        pages = [
            VisualPage(
                page_id=f"page_{i}",
                document_id="test_doc",
                page_number=i,
                embedding=np.random.randn(64, 128),
            )
            for i in range(3)
        ]

        results = visual_indexer.search("table query", pages, top_k=2)

        assert len(results) == 2
        assert all(isinstance(p, VisualPage) for p, _ in results)


@pytest.mark.integration
class TestVisualSearchStrategy:
    """Integration tests for VisualSearchStrategy."""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store with visual support."""
        store = AsyncMock()

        # Mock visual_search method
        store.visual_search = AsyncMock(
            return_value=[
                SearchResult(
                    chunk=DocumentChunk(
                        id="page_001",
                        content="Visual page 0",
                        document_id="doc1",
                        page_number=0,
                        section="visual",
                        metadata={"thumbnail_path": "/thumbs/page_001.jpg"},
                    ),
                    score=0.92,
                    source="qdrant_visual",
                ),
                SearchResult(
                    chunk=DocumentChunk(
                        id="page_005",
                        content="Visual page 5",
                        document_id="doc1",
                        page_number=5,
                        section="visual",
                        metadata={"thumbnail_path": "/thumbs/page_005.jpg"},
                    ),
                    score=0.87,
                    source="qdrant_visual",
                ),
            ]
        )

        # Mock regular search for text
        store.search = AsyncMock(
            return_value=[
                SearchResult(
                    chunk=DocumentChunk(
                        id="chunk_text_1",
                        content="Text result about tables",
                        document_id="doc1",
                        page_number=2,
                        section="text",
                    ),
                    score=0.75,
                    source="qdrant",
                ),
            ]
        )

        return store

    @pytest.fixture
    def visual_strategy(self, mock_colpali, mock_vector_store):
        """Visual search strategy fixture."""
        return VisualSearchStrategy(
            colpali_provider=mock_colpali,
            vector_store=mock_vector_store,
            visual_collection="test_visual_pages",
        )

    @pytest.mark.asyncio
    async def test_visual_search(self, visual_strategy):
        """Test visual search query."""
        response = await visual_strategy.search("table showing revenue")

        assert response.query == "table showing revenue"
        assert response.search_type == "visual"
        assert response.total_found == 2
        assert response.results[0].score > 0.9

    @pytest.mark.asyncio
    async def test_hybrid_search(self, visual_strategy):
        """Test hybrid visual+text search."""
        response = await visual_strategy.hybrid_visual_text_search(
            query="chart with sales data",
            text_embedding=[0.1] * 128,
            k=5,
            visual_weight=0.7,
            text_weight=0.3,
        )

        assert response.search_type == "hybrid_visual_text"
        assert response.total_found > 0
        assert response.metadata.get("visual_weight") == 0.7
        assert response.metadata.get("text_weight") == 0.3

    @pytest.mark.asyncio
    async def test_search_with_document_filter(self, visual_strategy):
        """Test visual search with document filtering."""
        response = await visual_strategy.search(
            "diagram",
            document_id="doc1",
            k=3,
        )

        assert response.total_found >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_visual_workflow(
    visual_indexer,
    mock_vector_store,
    sample_pdf_path,
):
    """End-to-end test: index PDF → search visual pages."""
    # Step 1: Index PDF
    pages = visual_indexer.index_pdf(
        pdf_path=sample_pdf_path,
        document_id="e2e_test_doc",
    )

    assert len(pages) > 0

    # Step 2: Add to vector store (mock)
    mock_vector_store.add_visual_pages = AsyncMock(return_value=[p.page_id for p in pages])
    ids = await mock_vector_store.add_visual_pages(pages)

    assert len(ids) == len(pages)

    # Step 3: Search visual pages
    mock_vector_store.visual_search = AsyncMock(
        return_value=[
            SearchResult(
                chunk=DocumentChunk(
                    id=pages[0].page_id,
                    content=f"Visual page {pages[0].page_number}",
                    document_id=pages[0].document_id,
                    page_number=pages[0].page_number,
                    section="visual",
                ),
                score=0.88,
                source="qdrant_visual",
            ),
        ]
    )

    strategy = VisualSearchStrategy(
        colpali_provider=visual_indexer._colpali,
        vector_store=mock_vector_store,
    )

    response = await strategy.search("table query")

    assert response.total_found == 1
    assert response.results[0].chunk.page_number == pages[0].page_number


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
