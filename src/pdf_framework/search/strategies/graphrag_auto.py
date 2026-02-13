"""GraphRAG Auto-Selection Strategy (Phase 38).

Routes queries between LightRAG (cheap) and Full GraphRAG Global (expensive)
based on query complexity classification.

Auto-selection logic:
- simple/moderate queries → LightRAG (~100 tokens, <500ms)
- complex/thematic queries → Full GraphRAG Global (~5000 tokens, ~5-10s)

Reuses the existing QueryClassifier from Phase 8/26.
"""

import logging
import time
from typing import Any

from src.pdf_framework.config import LightRAGSettings
from src.pdf_framework.schemas.documents import SearchResponse

logger = logging.getLogger(__name__)


class GraphRAGAutoStrategy:
    """Auto-selects between LightRAG and Full GraphRAG based on query complexity.

    Wraps both strategies and delegates to the appropriate one.
    """

    def __init__(
        self,
        light_strategy: Any,
        global_strategy: Any,
        classifier: Any,
        settings: LightRAGSettings | None = None,
    ):
        """Initialize auto-selection strategy.

        Args:
            light_strategy: LightRAGStrategy instance.
            global_strategy: GraphRAGGlobalStrategy instance.
            classifier: QueryClassifier instance.
            settings: LightRAG settings with complexity routing config.
        """
        self._light = light_strategy
        self._global = global_strategy
        self._classifier = classifier
        self._settings = settings or LightRAGSettings()

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Route query to LightRAG or Full GraphRAG based on complexity.

        Args:
            query: Search query.
            k: Number of results.
            filter: Optional metadata filters.

        Returns:
            SearchResponse from the chosen strategy.
        """
        start = time.perf_counter()

        # Classify query complexity
        classification = await self._classifier.classify(query)

        use_light = classification.complexity in self._settings.light_complexities

        logger.info(
            "[GRAPHRAG_AUTO] Query '%s' classified as %s/%s (confidence=%.2f) → %s",
            query[:50],
            classification.complexity,
            classification.query_type,
            classification.confidence,
            "LightRAG" if use_light else "Full GraphRAG",
        )

        # Route to appropriate strategy
        if use_light:
            response = await self._light.search(
                query=query, k=k, filter=filter, **kwargs,
            )
            response.search_type = "graphrag_auto_light"
        else:
            response = await self._global.search(
                query=query, k=k, filter=filter, **kwargs,
            )
            response.search_type = "graphrag_auto_full"

        # Add routing metadata
        classify_ms = (time.perf_counter() - start) * 1000 - response.elapsed_ms
        response.metadata = response.metadata or {}
        response.metadata.update({
            "auto_route": "light" if use_light else "full",
            "classification": {
                "complexity": classification.complexity,
                "query_type": classification.query_type,
                "confidence": classification.confidence,
                "reasoning": classification.reasoning,
            },
            "classify_ms": round(classify_ms, 1),
        })

        total_ms = (time.perf_counter() - start) * 1000
        response.elapsed_ms = total_ms

        logger.info(
            "[GRAPHRAG_AUTO] Completed in %.0fms (classify: %.0fms, search: %.0fms)",
            total_ms, classify_ms, total_ms - classify_ms,
        )

        return response
