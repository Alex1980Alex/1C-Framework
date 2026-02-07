"""Adaptive Search Strategy for Adaptive RAG.

Orchestrates query classification, routing, and optional decomposition
for automatic strategy selection.

Author: Claude Code
Version: 0.9.0 - Phase 8.4: AdaptiveSearchStrategy
"""

import logging
import time
from typing import Any

from src.pdf_framework.config import AdaptiveRAGSettings
from src.pdf_framework.schemas.documents import SearchResponse, SearchResult, DocumentChunk
from src.pdf_framework.search.manager import SearchManager
from src.pdf_framework.search.routing.classifier import QueryClassifier, QueryClassification
from src.pdf_framework.search.routing.decomposer import SubQuestionDecomposer
from src.pdf_framework.search.routing.router import StrategyRouter

logger = logging.getLogger(__name__)


class AdaptiveSearchStrategy:
    """
    Adaptive search strategy that automatically selects optimal approach.

    Pipeline:
    1. Classify query complexity
    2. Route to optimal strategy
    3a. If decompose: decompose → multi-search → synthesize
    3b. Otherwise: single search with routed strategy
    """

    def __init__(
        self,
        search_manager: SearchManager,
        settings: AdaptiveRAGSettings | None = None,
    ):
        """
        Initialize adaptive search strategy.

        Args:
            search_manager: SearchManager for executing searches
            settings: AdaptiveRAG configuration
        """
        self._search_manager = search_manager
        self._settings = settings or AdaptiveRAGSettings()

        # Initialize components
        self._classifier = QueryClassifier()
        self._router = StrategyRouter(
            available_strategies=search_manager.available_strategies
        )

        # Initialize decomposer if enabled
        self._decomposer = None
        if self._settings.decomposition_enabled:
            self._decomposer = SubQuestionDecomposer(
                max_sub_questions=self._settings.max_sub_questions
            )

        logger.info("[ADAPTIVE] Initialized with classification, routing, decomposition")

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        force_route: str | None = None,
        **kwargs,
    ) -> SearchResponse:
        """
        Perform adaptive search with automatic strategy selection.

        Args:
            query: Search query
            k: Number of results to return
            filter: Optional metadata filters
            force_route: Force specific route (bypass classifier)
            **kwargs: Additional parameters

        Returns:
            SearchResponse with results and metadata
        """
        start = time.perf_counter()

        # Step 1: Classify query (unless force_route specified)
        if force_route:
            logger.info(f"[ADAPTIVE] Force route: {force_route}")
            classification = self._create_forced_classification(force_route)
        else:
            classification = await self._classifier.classify(query)

        # Step 2: Route to optimal strategy
        decision = await self._router.route(classification)

        # Override k if decision specifies different k
        final_k = decision.k or k

        # Step 3a: Decompose if needed
        if decision.decompose and self._decomposer:
            if self._decomposer.should_decompose(classification):
                return await self._execute_decomposed_search(
                    query, final_k, filter, decision, start
                )

        # Step 3b: Standard single search
        return await self._execute_standard_search(
            query, final_k, filter, decision, classification, start
        )

    async def _execute_standard_search(
        self,
        query: str,
        k: int,
        filter: dict[str, Any] | None,
        decision,
        classification: QueryClassification,
        start_time: float,
    ) -> SearchResponse:
        """Execute standard single search with routed strategy."""
        strategy = decision.strategy
        use_reranking = decision.use_reranking
        use_expansion = decision.use_query_expansion

        logger.info(
            f"[ADAPTIVE] Standard search: strategy={strategy}, "
            f"rerank={use_reranking}, expand={use_expansion}"
        )

        # Execute search via SearchManager
        response = await self._search_manager.search(
            query=query,
            strategy=strategy,
            k=k,
            filter=filter,
            rerank=use_reranking,
            expand_query=use_expansion,
        )

        # Add adaptive metadata
        response.metadata = {
            "adaptive_routing": {
                "complexity": classification.complexity,
                "query_type": classification.query_type,
                "confidence": classification.confidence,
                "routed_strategy": strategy,
                "reranking_used": use_reranking,
                "query_expansion_used": use_expansion,
                "decomposed": False,
            }
        }

        elapsed = (time.perf_counter() - start_time) * 1000
        response.elapsed_ms = elapsed

        return response

    async def _execute_decomposed_search(
        self,
        query: str,
        k: int,
        filter: dict[str, Any] | None,
        decision,
        start_time: float,
    ) -> SearchResponse:
        """Execute decomposed multi-search for complex queries."""
        # Decompose query
        sub_queries = await self._decomposer.decompose(query)

        if len(sub_queries) <= 1:
            # Decomposition failed, fall back to standard search
            logger.warning("[ADAPTIVE] Decomposition failed, using standard search")
            return await self._execute_standard_search(
                query, k, filter, decision, QueryClassification(
                    complexity="moderate", query_type="unknown", confidence=0.0
                ), start_time
            )

        logger.info(f"[ADAPTIVE] Decomposed into {len(sub_queries)} sub-queries")

        # Execute search for each sub-query
        all_results: list[SearchResult] = []
        sub_responses: list[SearchResponse] = []

        for i, sub_query in enumerate(sub_queries):
            logger.info(f"[ADAPTIVE] Sub-query {i + 1}/{len(sub_queries)}: {sub_query[:40]}...")

            sub_response = await self._search_manager.search(
                query=sub_query,
                strategy=decision.strategy,
                k=k,
                filter=filter,
                rerank=decision.use_reranking,
            )

            sub_responses.append(sub_response)
            all_results.extend(sub_response.results)

        # Synthesize answers
        sub_answers = [r.results[0].chunk.content if r.results else "" for r in sub_responses]
        synthesized_answer = await self._decomposer.synthesize(query, sub_answers)

        # Create synthesized result
        synthesized_chunk = DocumentChunk(
            id="adaptive_synthesized",
            document_id="multi_search",
            content=synthesized_answer,
            metadata={
                "search_type": "adaptive_decomposed",
                "sub_queries_count": len(sub_queries),
                "total_results_count": len(all_results),
                "classification": "complex",
            },
        )

        # Score = average of best scores from each sub-query
        avg_score = 0.0
        if sub_responses:
            scores = [
                r.results[0].score if r.results else 0.5
                for r in sub_responses
            ]
            avg_score = sum(scores) / len(scores)

        final_result = SearchResult(
            chunk=synthesized_chunk,
            score=avg_score,
            source="adaptive_decomposed",
        )

        elapsed = (time.perf_counter() - start_time) * 1000

        return SearchResponse(
            query=query,
            results=[final_result],
            total_found=1,
            search_type="adaptive_decomposed",
            elapsed_ms=elapsed,
        )

    def _create_forced_classification(self, route: str) -> QueryClassification:
        """Create a classification for forced routing."""
        # Map route names to complexity levels
        route_to_complexity = {
            "vector": "simple",
            "graph": "moderate",
            "hybrid": "moderate",
            "two_stage": "complex",
            "global": "thematic",
            "graphrag_local": "moderate",
            "graphrag_global": "thematic",
        }

        complexity = route_to_complexity.get(route, "moderate")

        return QueryClassification(
            complexity=complexity,  # type: ignore
            query_type="unknown",
            confidence=1.0,  # Forced route = high confidence
            reasoning=f"Force routed to {route}",
        )
