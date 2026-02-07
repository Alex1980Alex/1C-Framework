"""Strategy Router for Adaptive RAG.

Routes queries to optimal search strategies based on classification.

Author: Claude Code
Version: 0.9.0 - Phase 8.2: Strategy Router
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from src.pdf_framework.search.routing.classifier import QueryClassification


class RoutingDecision(BaseModel):
    """Decision on which search strategy to use."""

    # Strategy name for SearchManager
    strategy: str

    # Should we use reranking?
    use_reranking: bool = False

    # Should we use query expansion?
    use_query_expansion: bool = False

    # Should we decompose the query? (for complex)
    decompose: bool = False

    # Number of results to retrieve
    k: int = 5

    # Additional parameters
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteConfig:
    """Configuration for a single route."""

    strategy: str
    use_reranking: bool = False
    use_query_expansion: bool = False
    decompose: bool = False
    k: int = 5
    extra_params: dict[str, Any] = None

    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}


class StrategyRouter:
    """
    Routes queries to optimal search strategies.

    Uses query classification to determine the best approach:
    - simple → fast vector search (no reranking)
    - moderate → hybrid with reranking
    - complex → two-stage with decomposition
    - thematic → global search (GraphRAG)
    """

    def __init__(
        self,
        routes: dict[str, RouteConfig] | None = None,
        available_strategies: list[str] | None = None,
    ):
        """
        Initialize strategy router.

        Args:
            routes: Custom route configurations (optional)
            available_strategies: List of available strategy names
        """
        self._routes = routes or self._get_default_routes()
        self._available_strategies = set(available_strategies or self._get_default_strategies())

        logger.info(
            f"[ROUTER] Initialized with {len(self._routes)} routes, "
            f"{len(self._available_strategies)} available strategies"
        )

    async def route(self, classification: QueryClassification) -> RoutingDecision:
        """
        Determine the optimal search strategy based on classification.

        Args:
            classification: Query classification from QueryClassifier

        Returns:
            RoutingDecision with strategy and parameters
        """
        complexity = classification.complexity
        query_type = classification.query_type

        # Get route configuration for this complexity
        route_config = self._routes.get(complexity)

        if route_config is None:
            # Fallback to moderate route
            logger.warning(f"[ROUTER] No route for complexity '{complexity}', using moderate")
            route_config = self._routes.get("moderate", RouteConfig(strategy="vector"))

        # Check if strategy is available
        strategy = route_config.strategy
        if strategy not in self._available_strategies:
            logger.warning(
                f"[ROUTER] Strategy '{strategy}' not available, finding fallback..."
            )
            strategy = self._find_fallback_strategy(route_config)
            if strategy:
                logger.info(f"[ROUTER] Fallback to strategy: {strategy}")

        # Build routing decision
        decision = RoutingDecision(
            strategy=strategy,
            use_reranking=route_config.use_reranking,
            use_query_expansion=route_config.use_query_expansion,
            decompose=route_config.decompose,
            k=route_config.k,
            extra_params=route_config.extra_params.copy(),
        )

        # Add classification metadata
        decision.extra_params.update({
            "classification_complexity": complexity,
            "classification_query_type": query_type,
            "classification_confidence": classification.confidence,
        })

        logger.info(
            f"[ROUTER] Routed {complexity}/{query_type} query → "
            f"strategy={decision.strategy}, k={decision.k}, "
            f"rerank={decision.use_reranking}, decompose={decision.decompose}"
        )

        return decision

    def _find_fallback_strategy(self, route_config: RouteConfig) -> str | None:
        """Find fallback strategy if preferred one is unavailable."""
        preferred = route_config.strategy

        # Fallback hierarchy
        fallback_map = {
            "global": "hybrid",
            "two_stage": "hybrid",
            "hybrid": "vector",
            "graphrag_local": "vector",
            "graphrag_global": "vector",
            "auto_merge": "vector",
        }

        for candidate in [preferred] + fallback_map.get(preferred, []):
            if candidate in self._available_strategies:
                return candidate

        return None

    def _get_default_routes(self) -> dict[str, RouteConfig]:
        """Get default route configurations."""
        return {
            "simple": RouteConfig(
                strategy="vector",
                use_reranking=False,
                use_query_expansion=False,
                decompose=False,
                k=3,
            ),
            "moderate": RouteConfig(
                strategy="hybrid",
                use_reranking=True,
                use_query_expansion=False,
                decompose=False,
                k=5,
            ),
            "complex": RouteConfig(
                strategy="two_stage",
                use_reranking=True,
                use_query_expansion=True,
                decompose=True,
                k=10,
            ),
            "thematic": RouteConfig(
                strategy="graphrag_global",
                use_reranking=False,
                use_query_expansion=False,
                decompose=False,
                k=5,
                extra_params={"max_communities": 20},
            ),
        }

    def _get_default_strategies(self) -> list[str]:
        """Get list of default available strategies."""
        return [
            "vector",
            "graph",
            "hybrid",
            "two_stage",
            "mmr",
            "graphrag_local",
            "graphrag_global",
            "auto_merge",
        ]

    def add_route(
        self,
        complexity: str,
        route_config: RouteConfig,
    ) -> None:
        """
        Add or update a route configuration.

        Args:
            complexity: Complexity level (simple/moderate/complex/thematic)
            route_config: Route configuration
        """
        self._routes[complexity] = route_config
        logger.info(f"[ROUTER] Added/Updated route for {complexity}: {route_config.strategy}")

    def get_routes(self) -> dict[str, RouteConfig]:
        """Get all route configurations."""
        return self._routes.copy()
