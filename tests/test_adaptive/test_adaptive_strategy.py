"""Tests for AdaptiveSearchStrategy (Phase 8.4).

Tests orchestration with mocked classifier, router, and search manager.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.pdf_framework.config import AdaptiveRAGSettings
from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    SearchResponse,
    SearchResult,
)
from src.pdf_framework.search.routing.classifier import QueryClassification
from src.pdf_framework.search.routing.router import RoutingDecision
from src.pdf_framework.search.strategies.adaptive import AdaptiveSearchStrategy


def _make_search_response(query: str = "test", n_results: int = 2) -> SearchResponse:
    results = [
        SearchResult(
            chunk=DocumentChunk(
                id=f"chunk_{i}",
                content=f"Content {i}",
                document_id="doc1",
            ),
            score=0.9 - i * 0.1,
        )
        for i in range(n_results)
    ]
    return SearchResponse(
        query=query,
        results=results,
        total_found=n_results,
        search_type="vector",
        elapsed_ms=50.0,
    )


def _make_adaptive(
    decomposition_enabled: bool = False,
    available_strategies: list[str] | None = None,
) -> AdaptiveSearchStrategy:
    """Create AdaptiveSearchStrategy with mocked dependencies."""
    search_manager = MagicMock()
    search_manager.available_strategies = available_strategies or ["vector", "hybrid", "two_stage"]
    search_manager.search = AsyncMock(return_value=_make_search_response())

    settings = AdaptiveRAGSettings(decomposition_enabled=decomposition_enabled)

    strategy = AdaptiveSearchStrategy(
        search_manager=search_manager,
        settings=settings,
    )
    return strategy


class TestAdaptiveInit:
    """Test initialization."""

    def test_creates_classifier(self):
        s = _make_adaptive()
        assert s._classifier is not None

    def test_creates_router(self):
        s = _make_adaptive()
        assert s._router is not None

    def test_decomposer_disabled_by_default(self):
        s = _make_adaptive(decomposition_enabled=False)
        assert s._decomposer is None

    def test_decomposer_enabled(self):
        s = _make_adaptive(decomposition_enabled=True)
        assert s._decomposer is not None


class TestForceRoute:
    """Test force_route parameter."""

    def test_create_forced_classification_vector(self):
        s = _make_adaptive()
        classification = s._create_forced_classification("vector")
        assert classification.complexity == "simple"
        assert classification.confidence == 1.0
        assert "Force routed" in classification.reasoning

    def test_create_forced_classification_hybrid(self):
        s = _make_adaptive()
        classification = s._create_forced_classification("hybrid")
        assert classification.complexity == "moderate"

    def test_create_forced_classification_two_stage(self):
        s = _make_adaptive()
        classification = s._create_forced_classification("two_stage")
        assert classification.complexity == "complex"

    def test_create_forced_classification_graphrag_global(self):
        s = _make_adaptive()
        classification = s._create_forced_classification("graphrag_global")
        assert classification.complexity == "thematic"

    def test_create_forced_classification_unknown(self):
        s = _make_adaptive()
        classification = s._create_forced_classification("unknown")
        assert classification.complexity == "moderate"  # default


class TestAdaptiveSearch:
    """Test search orchestration."""

    @pytest.mark.asyncio
    async def test_standard_search_with_force_route(self):
        s = _make_adaptive()

        # Mock classifier to not be called (force_route bypasses it)
        s._classifier.classify = AsyncMock()

        # Mock router
        decision = RoutingDecision(
            strategy="vector", use_reranking=False, k=5
        )
        s._router.route = AsyncMock(return_value=decision)

        response = await s.search("test query", k=5, force_route="vector")

        # Classifier should NOT be called when force_route is specified
        s._classifier.classify.assert_not_called()
        # Router should be called with forced classification
        s._router.route.assert_called_once()
        # Search manager should be called
        s._search_manager.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_standard_search_calls_classifier(self):
        s = _make_adaptive()

        classification = QueryClassification(
            complexity="simple", query_type="factual", confidence=0.9
        )
        s._classifier.classify = AsyncMock(return_value=classification)

        decision = RoutingDecision(strategy="vector", use_reranking=False, k=3)
        s._router.route = AsyncMock(return_value=decision)

        response = await s.search("What is the version?", k=5)

        s._classifier.classify.assert_called_once_with("What is the version?")
        s._router.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_standard_search_uses_decision_k(self):
        s = _make_adaptive()

        classification = QueryClassification(
            complexity="complex", query_type="comparative", confidence=0.8
        )
        s._classifier.classify = AsyncMock(return_value=classification)

        decision = RoutingDecision(strategy="hybrid", use_reranking=True, k=10)
        s._router.route = AsyncMock(return_value=decision)

        await s.search("Compare A and B", k=5)

        # Should use decision.k (10) not the passed k (5)
        call_kwargs = s._search_manager.search.call_args
        assert call_kwargs.kwargs.get("k") == 10 or call_kwargs[1].get("k") == 10

    @pytest.mark.asyncio
    async def test_standard_search_passes_reranking(self):
        s = _make_adaptive()

        classification = QueryClassification(
            complexity="moderate", query_type="analytical", confidence=0.85
        )
        s._classifier.classify = AsyncMock(return_value=classification)

        decision = RoutingDecision(
            strategy="hybrid", use_reranking=True, use_query_expansion=True, k=5
        )
        s._router.route = AsyncMock(return_value=decision)

        await s.search("How does X work?")

        call_kwargs = s._search_manager.search.call_args
        assert call_kwargs.kwargs.get("rerank") is True
        assert call_kwargs.kwargs.get("expand_query") is True

    @pytest.mark.asyncio
    async def test_response_includes_adaptive_metadata(self):
        s = _make_adaptive()

        classification = QueryClassification(
            complexity="simple", query_type="factual", confidence=0.95
        )
        s._classifier.classify = AsyncMock(return_value=classification)

        decision = RoutingDecision(strategy="vector", k=3)
        s._router.route = AsyncMock(return_value=decision)

        response = await s.search("test")

        assert "adaptive_routing" in response.metadata
        routing = response.metadata["adaptive_routing"]
        assert routing["complexity"] == "simple"
        assert routing["query_type"] == "factual"
        assert routing["confidence"] == 0.95
        assert routing["routed_strategy"] == "vector"
        assert routing["decomposed"] is False

class TestDecomposedSearch:
    """Test decomposed search flow."""

    @pytest.mark.asyncio
    async def test_decompose_triggered_for_complex(self):
        s = _make_adaptive(decomposition_enabled=True)

        classification = QueryClassification(
            complexity="complex", query_type="comparative", confidence=0.9
        )
        s._classifier.classify = AsyncMock(return_value=classification)

        decision = RoutingDecision(
            strategy="hybrid", decompose=True, k=5
        )
        s._router.route = AsyncMock(return_value=decision)

        # Mock decomposer
        s._decomposer.should_decompose = MagicMock(return_value=True)
        s._decomposer.decompose = AsyncMock(return_value=[
            "What are the features of A?",
            "What are the features of B?",
        ])
        s._decomposer.synthesize = AsyncMock(return_value="A and B differ in...")

        response = await s.search("Compare A and B")

        s._decomposer.decompose.assert_called_once()
        s._decomposer.synthesize.assert_called_once()
        assert response.search_type == "adaptive_decomposed"
        assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_single_subquery(self):
        """If decomposition yields only 1 sub-query, fall back to standard."""
        s = _make_adaptive(decomposition_enabled=True)

        classification = QueryClassification(
            complexity="complex", query_type="comparative", confidence=0.9
        )
        s._classifier.classify = AsyncMock(return_value=classification)

        decision = RoutingDecision(strategy="hybrid", decompose=True, k=5)
        s._router.route = AsyncMock(return_value=decision)

        s._decomposer.should_decompose = MagicMock(return_value=True)
        s._decomposer.decompose = AsyncMock(return_value=["Just one query"])

        response = await s.search("test query")

        # Should fall back to standard search (SearchManager called)
        s._search_manager.search.assert_called()

    @pytest.mark.asyncio
    async def test_decompose_not_triggered_when_should_decompose_false(self):
        s = _make_adaptive(decomposition_enabled=True)

        classification = QueryClassification(
            complexity="complex", query_type="comparative", confidence=0.5
        )
        s._classifier.classify = AsyncMock(return_value=classification)

        decision = RoutingDecision(strategy="hybrid", decompose=True, k=5)
        s._router.route = AsyncMock(return_value=decision)

        s._decomposer.should_decompose = MagicMock(return_value=False)

        await s.search("test query")

        # Falls back to standard search
        s._search_manager.search.assert_called_once()
