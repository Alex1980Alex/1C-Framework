"""Tests for Strategy Router (Phase 8.2).

Tests routing decisions, fallback logic, and route management.
"""

import pytest

from src.pdf_framework.search.routing.classifier import QueryClassification
from src.pdf_framework.search.routing.router import (
    RouteConfig,
    RoutingDecision,
    StrategyRouter,
)


def _make_classification(
    complexity: str = "moderate",
    query_type: str = "analytical",
    confidence: float = 0.8,
) -> QueryClassification:
    return QueryClassification(
        complexity=complexity,
        query_type=query_type,
        confidence=confidence,
    )


class TestRoutingDecision:
    """Test RoutingDecision Pydantic model."""

    def test_defaults(self):
        d = RoutingDecision(strategy="vector")
        assert d.strategy == "vector"
        assert d.use_reranking is False
        assert d.use_query_expansion is False
        assert d.decompose is False
        assert d.k == 5
        assert d.extra_params == {}

    def test_extra_params_mutable(self):
        d = RoutingDecision(strategy="hybrid")
        d.extra_params["test"] = "value"
        assert d.extra_params["test"] == "value"

    def test_full_construction(self):
        d = RoutingDecision(
            strategy="two_stage",
            use_reranking=True,
            use_query_expansion=True,
            decompose=True,
            k=10,
            extra_params={"key": "val"},
        )
        assert d.strategy == "two_stage"
        assert d.use_reranking is True
        assert d.decompose is True
        assert d.k == 10


class TestRouteConfig:
    """Test RouteConfig dataclass."""

    def test_defaults(self):
        rc = RouteConfig(strategy="vector")
        assert rc.use_reranking is False
        assert rc.k == 5
        assert rc.extra_params == {}

    def test_custom_values(self):
        rc = RouteConfig(
            strategy="graphrag_global",
            k=10,
            extra_params={"max_communities": 20},
        )
        assert rc.strategy == "graphrag_global"
        assert rc.extra_params["max_communities"] == 20


class TestStrategyRouterInit:
    """Test StrategyRouter initialization."""

    def test_default_routes(self):
        router = StrategyRouter()
        routes = router.get_routes()
        assert "simple" in routes
        assert "moderate" in routes
        assert "complex" in routes
        assert "thematic" in routes

    def test_custom_routes(self):
        custom = {"simple": RouteConfig(strategy="vector", k=3)}
        router = StrategyRouter(routes=custom)
        routes = router.get_routes()
        assert len(routes) == 1
        assert routes["simple"].strategy == "vector"

    def test_available_strategies(self):
        router = StrategyRouter(available_strategies=["vector", "hybrid"])
        assert "vector" in router._available_strategies
        assert "hybrid" in router._available_strategies
        assert "mmr" not in router._available_strategies


class TestStrategyRouterRouting:
    """Test route() method."""

    @pytest.mark.asyncio
    async def test_simple_routes_to_vector(self):
        router = StrategyRouter()
        classification = _make_classification(complexity="simple", query_type="factual")
        decision = await router.route(classification)
        assert decision.strategy == "vector"
        assert decision.use_reranking is False
        assert decision.k == 3

    @pytest.mark.asyncio
    async def test_moderate_routes_to_hybrid(self):
        router = StrategyRouter()
        classification = _make_classification(complexity="moderate")
        decision = await router.route(classification)
        assert decision.strategy == "hybrid"
        assert decision.use_reranking is True
        assert decision.k == 5

    @pytest.mark.asyncio
    async def test_complex_routes_to_two_stage(self):
        router = StrategyRouter()
        classification = _make_classification(complexity="complex", query_type="comparative")
        decision = await router.route(classification)
        assert decision.strategy == "two_stage"
        assert decision.use_reranking is True
        assert decision.use_query_expansion is True
        assert decision.decompose is True
        assert decision.k == 10

    @pytest.mark.asyncio
    async def test_thematic_routes_to_graphrag_global(self):
        router = StrategyRouter()
        classification = _make_classification(complexity="thematic", query_type="thematic")
        decision = await router.route(classification)
        assert decision.strategy == "graphrag_global"
        assert decision.decompose is False
        assert "max_communities" in decision.extra_params

    @pytest.mark.asyncio
    async def test_unknown_complexity_falls_back_to_moderate(self):
        router = StrategyRouter()
        classification = _make_classification(complexity="moderate")
        classification.complexity = "unknown"  # type: ignore
        decision = await router.route(classification)
        # Falls back to moderate route → hybrid
        assert decision.strategy == "hybrid"

    @pytest.mark.asyncio
    async def test_classification_metadata_in_extra_params(self):
        router = StrategyRouter()
        classification = _make_classification(
            complexity="simple", query_type="factual", confidence=0.95
        )
        decision = await router.route(classification)
        assert decision.extra_params["classification_complexity"] == "simple"
        assert decision.extra_params["classification_query_type"] == "factual"
        assert decision.extra_params["classification_confidence"] == 0.95


class TestFallbackStrategy:
    """Test _find_fallback_strategy method."""

    def test_unavailable_strategy_falls_back(self):
        router = StrategyRouter(available_strategies=["vector"])
        rc = RouteConfig(strategy="two_stage")
        fallback = router._find_fallback_strategy(rc)
        # two_stage → hybrid → vector; only vector available
        assert fallback == "vector"

    def test_graphrag_global_falls_back_to_hybrid(self):
        router = StrategyRouter(available_strategies=["hybrid", "vector"])
        rc = RouteConfig(strategy="graphrag_global")
        fallback = router._find_fallback_strategy(rc)
        assert fallback == "hybrid"

    def test_graphrag_global_falls_back_to_vector(self):
        router = StrategyRouter(available_strategies=["vector"])
        rc = RouteConfig(strategy="graphrag_global")
        fallback = router._find_fallback_strategy(rc)
        assert fallback == "vector"

    def test_preferred_available_returns_preferred(self):
        router = StrategyRouter(available_strategies=["two_stage", "hybrid", "vector"])
        rc = RouteConfig(strategy="two_stage")
        fallback = router._find_fallback_strategy(rc)
        assert fallback == "two_stage"

    def test_unknown_strategy_falls_back_to_vector(self):
        router = StrategyRouter(available_strategies=["vector"])
        rc = RouteConfig(strategy="unknown_strategy")
        fallback = router._find_fallback_strategy(rc)
        # unknown not in available, not in fallback_map → ultimate fallback = "vector"
        assert fallback == "vector"

    @pytest.mark.asyncio
    async def test_routing_with_unavailable_strategy(self):
        """Integration: route uses fallback when strategy unavailable."""
        router = StrategyRouter(available_strategies=["vector", "hybrid"])
        classification = _make_classification(complexity="complex")
        decision = await router.route(classification)
        # complex → two_stage (unavailable) → hybrid (available)
        assert decision.strategy == "hybrid"


class TestAddRoute:
    """Test add_route method."""

    def test_add_new_route(self):
        router = StrategyRouter()
        router.add_route("custom", RouteConfig(strategy="mmr", k=7))
        routes = router.get_routes()
        assert "custom" in routes
        assert routes["custom"].strategy == "mmr"
        assert routes["custom"].k == 7

    def test_update_existing_route(self):
        router = StrategyRouter()
        router.add_route("simple", RouteConfig(strategy="hybrid", use_reranking=True))
        routes = router.get_routes()
        assert routes["simple"].strategy == "hybrid"
        assert routes["simple"].use_reranking is True
