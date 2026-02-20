"""Unified search manager: single entry point for all search strategies."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

from src.pdf_framework.config import AgentSettings, SearchSettings
from src.pdf_framework.schemas.documents import SearchResponse, SearchResult

if TYPE_CHECKING:
    from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
    from src.pdf_framework.search.semantic_cache import SemanticSearchCache

logger = logging.getLogger(__name__)


class SearchManager:
    """Route search requests to the appropriate strategy.

    All consumers (chains, agents, API, CLI) use SearchManager
    instead of calling strategies directly.

    Phase 1.1: Supports optional reranking with CrossEncoder.
    Phase 2.3: Supports optional query expansion.
    Phase 25: Supports LLM-based reranking via Claude.
    """

    def __init__(
        self,
        agent_settings: AgentSettings | None = None,
        search_settings: SearchSettings | None = None,
        api_key: str = "",
        embedding_engine: BaseEmbeddingEngine | None = None,
        semantic_cache: SemanticSearchCache | None = None,
    ) -> None:
        self._strategies: dict[str, Any] = {}
        self._agent_settings = agent_settings or AgentSettings()
        self._search_settings = search_settings or SearchSettings()
        self._api_key = api_key
        self._embedding_engine = embedding_engine
        self._semantic_cache = semantic_cache

        # Phase 30: Section-first pipeline (set from components.py when BM25 available)
        self._section_first_pipeline: Any = None

        # Initialize reranker if enabled (Phase 1.1 / Phase 25)
        self._reranker = None
        if self._agent_settings.reranker_enabled:
            self._reranker = self._create_reranker()

        # Initialize query expander if enabled (Phase 2.3)
        self._query_expander = None
        if self._search_settings.query_expansion_enabled:
            from src.pdf_framework.search.query_expansion import QueryExpander

            self._query_expander = QueryExpander(
                settings=self._agent_settings, api_key=self._api_key,
            )

    def _create_reranker(self):
        """Create reranker based on config type."""
        reranker_type = self._agent_settings.reranker_type

        if reranker_type == "llm":
            from src.pdf_framework.search.reranking.llm_reranker import LLMReranker

            return LLMReranker(
                api_key=self._api_key,
                base_url=self._agent_settings.base_url,
                model=self._agent_settings.reranker_llm_model,
            )

        if reranker_type == "colbert":
            from src.pdf_framework.search.reranking.colbert import ColBERTReranker

            return ColBERTReranker(
                model_name=self._agent_settings.colbert_model,
            )

        # Default: cross_encoder
        from src.pdf_framework.search.reranking.cross_encoder import (
            CrossEncoderReranker,
        )

        return CrossEncoderReranker(
            model_name=self._agent_settings.reranker_model,
        )

    def register_strategy(self, name: str, strategy: Any) -> None:
        """Register a search strategy by name."""
        self._strategies[name] = strategy

    @staticmethod
    def _chunk_matches_section(metadata: dict, section_prefix: str) -> bool:
        """Check if chunk belongs to a given section prefix.

        Tries section_number first, then extracts number from section_title.
        E.g. section_prefix="5.8" matches section_title="**5.8.Справочники**".
        """
        # Try explicit section_number first
        sn = metadata.get("section_number", "")
        if sn and sn.startswith(section_prefix):
            return True
        # Fallback: extract number from section_title (e.g. "**5.8.Справочники**")
        st = metadata.get("section_title", "") or metadata.get("section", "")
        if st:
            import re
            cleaned = st.strip().strip("*")
            match = re.match(r"(\d+(?:\.\d+)*)", cleaned)
            if match:
                extracted = match.group(1)
                return extracted.startswith(section_prefix)
        return False

    async def search(
        self,
        query: str,
        strategy: str = "vector",
        k: int = 5,
        filter: dict[str, Any] | None = None,
        rerank: bool = True,
        expand_query: bool = False,
        section_prefix: str | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Execute a search using the named strategy.

        Args:
            query: Search query text
            strategy: Strategy name ("vector", "graph", "hybrid", "mmr")
            k: Number of final results to return
            filter: Optional metadata filters
            rerank: Whether to apply reranking (default: True if enabled in config)
            expand_query: Whether to expand the query before searching
            section_prefix: Filter results to a section prefix (e.g. "5.14" for all 5.14.*)
            **kwargs: Additional strategy-specific parameters

        Returns:
            SearchResponse with results (reranked if enabled)
        """
        if strategy not in self._strategies:
            available = list(self._strategies.keys())
            raise ValueError(
                f"Unknown search strategy '{strategy}'. Available: {available}"
            )

        # Phase 17: Semantic cache pre-check
        query_embedding: list[float] | None = None
        if self._semantic_cache and not expand_query and self._embedding_engine:
            query_embedding = await self._embedding_engine.embed_text(query)
            cached = await self._semantic_cache.get(
                query_embedding=query_embedding,
                strategy=strategy,
                k=k,
                filter=filter,
                rerank=rerank,
            )
            if cached is not None:
                return cached

        # Phase 2.3: Query expansion
        queries = [query]
        if expand_query:
            # Lazy-init expander if CLI --expand-query flag is used but config disabled
            if self._query_expander is None:
                from src.pdf_framework.search.query_expansion import QueryExpander

                self._query_expander = QueryExpander(
                    settings=self._agent_settings, api_key=self._api_key,
                )
            queries = await self._query_expander.expand(
                query, method=self._search_settings.query_expansion_method,
            )
            logger.debug("Expanded query into %d variants: %s", len(queries), queries)

        # Get more results if reranking is enabled
        retrieval_k = self._agent_settings.reranker_top_k if (rerank and self._reranker) else k

        strat = self._strategies[strategy]

        if len(queries) == 1:
            # Standard single-query path
            response = await strat.search(query=queries[0], k=retrieval_k, filter=filter, **kwargs)
        else:
            # Multi-query: search all expanded queries in parallel (Phase 26)
            tasks = [
                strat.search(query=q, k=retrieval_k, filter=filter, **kwargs)
                for q in queries
            ]
            responses = await asyncio.gather(*tasks)

            all_results: dict[str, SearchResult] = {}
            for resp in responses:
                for r in resp.results:
                    if r.chunk.id not in all_results or r.score > all_results[r.chunk.id].score:
                        all_results[r.chunk.id] = r

            # Sort by score, take top retrieval_k
            merged = sorted(all_results.values(), key=lambda r: r.score, reverse=True)[:retrieval_k]
            response = responses[0]
            response.results = list(merged)
            response.total_found = len(merged)

        # Apply reranking if enabled
        if rerank and self._reranker and response.results:
            reranked_results = await self._reranker.rerank(
                query=query,  # Always rerank against original query
                results=response.results,
                top_k=k,
            )
            response.results = reranked_results
            response.total_found = len(reranked_results)

        # Phase 29: Section-prefix post-filter
        if section_prefix and response.results:
            filtered = [
                r for r in response.results
                if self._chunk_matches_section(r.chunk.metadata or {}, section_prefix)
            ]
            response.results = filtered
            response.total_found = len(filtered)

        # Phase 17: Semantic cache post-write
        if self._semantic_cache and not expand_query and self._embedding_engine:
            try:
                if query_embedding is None:
                    query_embedding = await self._embedding_engine.embed_text(query)
                await self._semantic_cache.set(
                    query=query,
                    query_embedding=query_embedding,
                    strategy=strategy,
                    k=k,
                    filter=filter,
                    rerank=rerank,
                    response=response,
                )
            except Exception as e:
                logger.warning("[SEARCH] Semantic cache write failed: %s", e)

        return response

    async def search_section_first(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Section-first search: locate section via BM25, then search within.

        Falls back to regular hybrid search if pipeline is not configured
        or no dominant section is found.
        """
        if self._section_first_pipeline is not None:
            return await self._section_first_pipeline.search(
                query=query, k=k, filter=filter, **kwargs,
            )
        # Fallback: regular hybrid search
        logger.info("[SEARCH] Section-first pipeline not configured — using hybrid")
        return await self.search(
            query=query, strategy="hybrid", k=k, filter=filter, rerank=True, **kwargs,
        )

    @property
    def available_strategies(self) -> list[str]:
        """Return names of registered strategies."""
        return list(self._strategies.keys())

    def register_visual_strategy(
        self,
        colpali_provider: Any,
        vector_store: Any,
        collection_name: str = "visual_pages",
    ) -> None:
        """Register visual search strategy (Phase 55).

        Args:
            colpali_provider: ColPali embedding provider
            vector_store: Vector store with visual collection
            collection_name: Name of visual pages collection
        """
        from src.pdf_framework.search.strategies.visual import VisualSearchStrategy

        strategy = VisualSearchStrategy(
            colpali_provider=colpali_provider,
            vector_store=vector_store,
            visual_collection=collection_name,
        )
        self.register_strategy("visual", strategy)
        logger.info("[SEARCH] Registered visual search strategy")

    async def search_visual(
        self,
        query: str,
        k: int = 5,
        document_id: str | None = None,
        **kwargs,
    ) -> SearchResponse:
        """Search visual pages (Phase 55).

        Args:
            query: Text description of visual content
            k: Number of results
            document_id: Optional document filter
            **kwargs: Additional parameters

        Returns:
            SearchResponse with visual page results
        """
        strategy = self._strategies.get("visual")
        if strategy is None:
            raise ValueError("Visual search strategy not registered")

        return await strategy.search(query, k=k, document_id=document_id, **kwargs)

    async def search_hybrid_visual_text(
        self,
        query: str,
        k: int = 5,
        visual_weight: float = 0.5,
        text_weight: float = 0.5,
        **kwargs,
    ) -> SearchResponse:
        """Hybrid visual + text search (Phase 55).

        Args:
            query: Search query
            k: Number of results
            visual_weight: Weight for visual results
            text_weight: Weight for text results
            **kwargs: Additional parameters

        Returns:
            SearchResponse with fused results
        """
        strategy = self._strategies.get("visual")
        if strategy is None:
            raise ValueError("Visual search strategy not registered")

        # Get text embedding for fusion
        if self._embedding_engine:
            text_embedding = await self._embedding_engine.embed_text(query)
        else:
            text_embedding = None

        return await strategy.hybrid_visual_text_search(
            query=query,
            text_embedding=text_embedding,
            k=k,
            visual_weight=visual_weight,
            text_weight=text_weight,
            **kwargs,
        )
