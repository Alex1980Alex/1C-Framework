"""Tests for AutoMergeStrategy (Phase 7.3).

Tests merge logic and statistics without actual vector search.
"""

import pytest

from src.pdf_framework.schemas.documents import DocumentChunk, SearchResult


def _child_result(
    child_id: str,
    parent_id: str,
    score: float = 0.9,
    content: str = "child content",
) -> SearchResult:
    return SearchResult(
        chunk=DocumentChunk(
            id=child_id,
            document_id="doc1",
            content=content,
            metadata={
                "chunk_type": "child",
                "parent_id": parent_id,
                "parent_index": 0,
            },
        ),
        score=score,
    )


def _orphan_result(chunk_id: str, score: float = 0.8) -> SearchResult:
    return SearchResult(
        chunk=DocumentChunk(
            id=chunk_id,
            document_id="doc1",
            content="orphan content",
            metadata={"chunk_type": "child"},
        ),
        score=score,
    )


def _parent_chunk(parent_id: str, content: str = "parent content") -> DocumentChunk:
    return DocumentChunk(
        id=parent_id,
        document_id="doc1",
        content=content,
        metadata={
            "chunk_type": "parent",
            "child_count": 5,
            "child_ids": [f"{parent_id}_c{i}" for i in range(5)],
        },
    )


def _make_strategy(merge_threshold: int = 3, fetch_multiplier: float = 3.0):
    """Create strategy with mock dependencies."""
    from unittest.mock import AsyncMock, MagicMock

    from src.pdf_framework.search.strategies.auto_merge import AutoMergeStrategy

    strategy = object.__new__(AutoMergeStrategy)
    strategy._embedding = MagicMock()
    strategy._vector_store = MagicMock()
    strategy._parent_store = AsyncMock()
    strategy._threshold = merge_threshold
    strategy._fetch_multiplier = fetch_multiplier
    return strategy


class TestMergeStatistics:
    @pytest.mark.asyncio
    async def test_stats_empty(self):
        s = _make_strategy()
        stats = await s.get_merge_statistics([])
        assert stats["parent_chunks"] == 0
        assert stats["child_chunks"] == 0
        assert stats["total_chunks"] == 0

    @pytest.mark.asyncio
    async def test_stats_only_children(self):
        results = [
            _child_result("c1", "p1"),
            _child_result("c2", "p1"),
        ]
        s = _make_strategy()
        stats = await s.get_merge_statistics(results)
        assert stats["child_chunks"] == 2
        assert stats["parent_chunks"] == 0
        assert stats["unique_parents"] == 1

    @pytest.mark.asyncio
    async def test_stats_with_parents(self):
        parent = _parent_chunk("p1")
        results = [
            SearchResult(
                chunk=parent,
                score=0.95,
                source="auto_merge_parent",
            ),
            _child_result("c3", "p2"),
        ]
        s = _make_strategy()
        stats = await s.get_merge_statistics(results)
        assert stats["parent_chunks"] == 1
        assert stats["child_chunks"] == 1
        assert stats["merged_into_parents"] == 5  # child_count from parent


class TestSearchLogic:
    @pytest.mark.asyncio
    async def test_merge_when_above_threshold(self):
        """When >= threshold children from same parent, merge to parent."""
        from unittest.mock import AsyncMock

        s = _make_strategy(merge_threshold=2)

        # Mock embedding
        s._embedding.embed_text = AsyncMock(return_value=[0.1] * 384)

        # Mock vector store to return 3 children from same parent
        children = [
            _child_result("c1", "p1", score=0.9),
            _child_result("c2", "p1", score=0.85),
            _child_result("c3", "p1", score=0.8),
        ]
        s._vector_store.search = AsyncMock(return_value=children)

        # Mock parent store
        parent = _parent_chunk("p1", "full parent content")
        s._parent_store.get_parent = AsyncMock(return_value=parent)

        response = await s.search("test query", k=5)

        assert len(response.results) == 1
        assert response.results[0].chunk.id == "p1"
        assert response.results[0].score == 0.9  # max of children
        assert response.search_type == "auto_merge"

    @pytest.mark.asyncio
    async def test_no_merge_below_threshold(self):
        """When < threshold children, keep individual children."""
        from unittest.mock import AsyncMock

        s = _make_strategy(merge_threshold=5)  # High threshold

        s._embedding.embed_text = AsyncMock(return_value=[0.1] * 384)

        children = [
            _child_result("c1", "p1", score=0.9),
            _child_result("c2", "p1", score=0.85),
        ]
        s._vector_store.search = AsyncMock(return_value=children)

        response = await s.search("test query", k=5)

        assert len(response.results) == 2
        assert all(r.chunk.metadata["chunk_type"] == "child" for r in response.results)

    @pytest.mark.asyncio
    async def test_orphan_children_kept(self):
        """Children without parent_id are kept as-is."""
        from unittest.mock import AsyncMock

        s = _make_strategy(merge_threshold=2)

        s._embedding.embed_text = AsyncMock(return_value=[0.1] * 384)
        s._vector_store.search = AsyncMock(return_value=[
            _orphan_result("o1", score=0.9),
            _orphan_result("o2", score=0.8),
        ])

        response = await s.search("test query", k=5)

        assert len(response.results) == 2

    @pytest.mark.asyncio
    async def test_mixed_merge_and_keep(self):
        """Some groups merge, others don't, orphans kept."""
        from unittest.mock import AsyncMock

        s = _make_strategy(merge_threshold=2)
        s._embedding.embed_text = AsyncMock(return_value=[0.1] * 384)

        results = [
            # p1: 3 children -> merge
            _child_result("c1", "p1", 0.95),
            _child_result("c2", "p1", 0.90),
            _child_result("c3", "p1", 0.85),
            # p2: 1 child -> keep
            _child_result("c4", "p2", 0.80),
            # orphan
            _orphan_result("o1", 0.75),
        ]
        s._vector_store.search = AsyncMock(return_value=results)
        s._parent_store.get_parent = AsyncMock(
            return_value=_parent_chunk("p1", "merged parent")
        )

        response = await s.search("test query", k=5)

        # Should have: 1 merged parent (p1) + 1 child (c4) + 1 orphan (o1)
        assert len(response.results) == 3
        types = [r.chunk.metadata.get("chunk_type") for r in response.results]
        assert "parent" in types

    @pytest.mark.asyncio
    async def test_results_sorted_by_score(self):
        """Final results should be sorted by score descending."""
        from unittest.mock import AsyncMock

        s = _make_strategy(merge_threshold=100)  # No merging
        s._embedding.embed_text = AsyncMock(return_value=[0.1] * 384)

        results = [
            _child_result("c1", "p1", 0.5),
            _child_result("c2", "p2", 0.9),
            _child_result("c3", "p3", 0.7),
        ]
        s._vector_store.search = AsyncMock(return_value=results)

        response = await s.search("test query", k=3)

        scores = [r.score for r in response.results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_results_trimmed_to_k(self):
        """Results should be trimmed to k."""
        from unittest.mock import AsyncMock

        s = _make_strategy(merge_threshold=100)
        s._embedding.embed_text = AsyncMock(return_value=[0.1] * 384)

        results = [_child_result(f"c{i}", f"p{i}", 0.9 - i * 0.01) for i in range(10)]
        s._vector_store.search = AsyncMock(return_value=results)

        response = await s.search("test query", k=3)

        assert len(response.results) == 3

    @pytest.mark.asyncio
    async def test_parent_not_found_keeps_children(self):
        """If parent store returns None, keep individual children."""
        from unittest.mock import AsyncMock

        s = _make_strategy(merge_threshold=2)
        s._embedding.embed_text = AsyncMock(return_value=[0.1] * 384)

        results = [
            _child_result("c1", "missing_parent", 0.9),
            _child_result("c2", "missing_parent", 0.8),
        ]
        s._vector_store.search = AsyncMock(return_value=results)
        s._parent_store.get_parent = AsyncMock(return_value=None)

        response = await s.search("test query", k=5)

        # Children should be kept since parent not found
        assert len(response.results) == 2
        assert all(r.chunk.metadata["chunk_type"] == "child" for r in response.results)
