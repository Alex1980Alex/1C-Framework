"""GraphRAG Global Search: map-reduce over community summaries.

Answers broad/thematic questions by processing community summaries
instead of individual chunks.

Author: Claude Code
Version: 0.7.0 - Phase 6.4: Global Search
"""

import logging
import time
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from src.pdf_framework.config import GraphRAGSettings
from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.schemas.documents import SearchResponse, SearchResult, DocumentChunk
from src.pdf_framework.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


class GraphRAGGlobalStrategy:
    """
    Global Search strategy for GraphRAG.

    Uses map-reduce over community summaries to answer broad questions:
    1. Rank communities by relevance to query
    2. Map: Generate partial answers from each community summary
    3. Reduce: Synthesize partial answers into final response
    """

    def __init__(
        self,
        embedding_engine: BaseEmbeddingEngine,
        vector_store: BaseVectorStore,
        graph_store: BaseGraphStore,
        settings: GraphRAGSettings | None = None,
        api_key: str = "",
        base_url: str = "",
    ):
        """
        Initialize GraphRAG Global Search strategy.

        Args:
            embedding_engine: For query embedding (community ranking)
            vector_store: For community summary embeddings
            graph_store: For accessing communities and summaries
            settings: GraphRAG configuration
            api_key: Anthropic API key
            base_url: Custom API endpoint (for Z.AI or other proxies)
        """
        self._embedding_engine = embedding_engine
        self._vector_store = vector_store
        self._graph_store = graph_store
        self.settings = settings or GraphRAGSettings()

        # LLMs for map and reduce phases — pass api_key and base_url for Z.AI
        map_kwargs = dict(
            model=self.settings.global_search_map_model,
            temperature=0.0,
            max_tokens=1024,
        )
        reduce_kwargs = dict(
            model=self.settings.global_search_reduce_model,
            temperature=0.0,
            max_tokens=2048,
        )
        if api_key:
            map_kwargs["api_key"] = api_key
            reduce_kwargs["api_key"] = api_key
        if base_url:
            map_kwargs["base_url"] = base_url
            reduce_kwargs["base_url"] = base_url
        self._map_llm = ChatAnthropic(**map_kwargs)
        self._reduce_llm = ChatAnthropic(**reduce_kwargs)
        self._parser = StrOutputParser()

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        max_communities: int | None = None,
        **kwargs,
    ) -> SearchResponse:
        """
        Perform global search using community summaries.

        Args:
            query: Search query (typically broad/thematic)
            k: Number of sources to return (not directly used in global search)
            filter: Optional metadata filters
            max_communities: Maximum communities to process
            **kwargs: Additional parameters

        Returns:
            SearchResponse with synthesized answer
        """
        start = time.perf_counter()

        max_comm = max_communities or self.settings.global_search_max_communities

        # Step 1: Get all community summaries from graph
        community_summaries = await self._get_community_summaries()

        if not community_summaries:
            logger.warning("[GLOBAL_SEARCH] No community summaries found")
            return self._empty_response(query, start)

        # Step 2: Rank communities by relevance (optional)
        if self.settings.global_search_rank_by_similarity:
            ranked_communities = await self._rank_communities(
                query, community_summaries, max_comm
            )
        else:
            ranked_communities = list(community_summaries.values())[:max_comm]

        logger.info(
            f"[GLOBAL_SEARCH] Processing {len(ranked_communities)} communities "
            f"out of {len(community_summaries)} total"
        )

        # Step 3: Map phase - partial answers from each community
        partial_answers = await self._map_phase(query, ranked_communities)

        # Filter empty answers
        valid_answers = [a for a in partial_answers if a.strip()]
        logger.info(f"[GLOBAL_SEARCH] Map phase: {len(valid_answers)} valid partial answers")

        if not valid_answers:
            return self._empty_response(query, start)

        # Step 4: Reduce phase - synthesize final answer
        final_answer = await self._reduce_phase(query, valid_answers)

        elapsed = (time.perf_counter() - start) * 1000

        # Create SearchResponse
        result = SearchResult(
            chunk=DocumentChunk(
                id="global_search",
                document_id="graphrag_global",
                content=final_answer,
                metadata={
                    "search_type": "global",
                    "communities_processed": len(ranked_communities),
                    "partial_answers_count": len(valid_answers),
                    "community_ids": [self._extract_community_id(s) for s in ranked_communities],
                },
            ),
            score=1.0,  # Global search doesn't have traditional scores
        )

        logger.info(f"[GLOBAL_SEARCH] Completed in {elapsed:.0f}ms")

        return SearchResponse(
            query=query,
            results=[result],
            total_found=1,
            search_type="graphrag_global",
            elapsed_ms=elapsed,
        )

    async def _get_community_summaries(self) -> dict[str, str]:
        """
        Get all community summaries from the graph.

        Returns:
            Dictionary mapping community_key -> summary
        """
        summaries = {}

        # Access graph store to get community nodes
        graph = self._graph_store._graph if hasattr(self._graph_store, "_graph") else None

        if not graph:
            return summaries

        for node_id, data in graph.nodes(data=True):
            if data.get("node_type") == "COMMUNITY":
                summary = data.get("summary", "")
                if summary:
                    comm_id = data.get("community_id", 0)
                    level = data.get("level", 0)
                    key = f"{comm_id}_L{level}"
                    summaries[key] = summary

        logger.info(f"[GLOBAL_SEARCH] Found {len(summaries)} community summaries")
        return summaries

    async def _rank_communities(
        self,
        query: str,
        summaries: dict[str, str],
        top_k: int,
    ) -> list[str]:
        """
        Rank communities by embedding similarity to query.

        Args:
            query: Search query
            summaries: Community summaries
            top_k: Number of top communities to return

        Returns:
            List of ranked summary texts
        """
        query_embedding = await self._embedding_engine.embed_text(query)

        # Compute embeddings for all summaries
        summary_embeddings = {}
        for key, summary in summaries.items():
            emb = await self._embedding_engine.embed_text(summary)
            summary_embeddings[key] = emb

        # Rank by cosine similarity
        from numpy import dot
        from numpy.linalg import norm

        similarities = {}
        for key, emb in summary_embeddings.items():
            similarity = dot(query_embedding, emb) / (norm(query_embedding) * norm(emb))
            similarities[key] = similarity

        # Sort and get top-k
        ranked_keys = sorted(similarities.keys(), key=lambda k: similarities[k], reverse=True)
        top_keys = ranked_keys[:top_k]

        ranked_summaries = [summaries[k] for k in top_keys]
        logger.info(f"[GLOBAL_SEARCH] Ranked communities: {top_keys}")

        return ranked_summaries

    async def _map_phase(
        self,
        query: str,
        community_summaries: list[str],
    ) -> list[str]:
        """
        Map phase: generate partial answers from each community summary.

        Args:
            query: Search query
            community_summaries: List of community summaries

        Returns:
            List of partial answers
        """
        prompt = self._get_map_prompt(query)
        partial_answers = []

        for i, summary in enumerate(community_summaries):
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content=f"Community Summary:\n{summary}\n\nQuery: {query}"),
            ]

            try:
                response = await self._map_llm.ainvoke(messages)
                answer = self._parser.invoke(response).strip()
                partial_answers.append(answer)
                logger.debug(f"[GLOBAL_SEARCH] Map phase: community {i + 1}/{len(community_summaries)}")
            except Exception as e:
                logger.error(f"[GLOBAL_SEARCH] Map phase error for community {i}: {e}")
                partial_answers.append("")  # Empty answer for failed communities

        return partial_answers

    async def _reduce_phase(
        self,
        query: str,
        partial_answers: list[str],
    ) -> str:
        """
        Reduce phase: synthesize partial answers into final response.

        Args:
            query: Original search query
            partial_answers: List of partial answers from map phase

        Returns:
            Synthesized final answer
        """
        prompt = self._get_reduce_prompt(query, partial_answers)

        messages = [
            SystemMessage(content="You are an expert synthesizer of information from multiple sources."),
            HumanMessage(content=prompt),
        ]

        try:
            response = await self._reduce_llm.ainvoke(messages)
            final_answer = self._parser.invoke(response).strip()
            logger.info("[GLOBAL_SEARCH] Reduce phase completed")
            return final_answer
        except Exception as e:
            logger.error(f"[GLOBAL_SEARCH] Reduce phase error: {e}")
            # Fallback: join partial answers
            return "\n\n".join(partial_answers)

    def _get_map_prompt(self, query: str) -> str:
        """Get the prompt for map phase."""
        return """You are analyzing a community summary from a knowledge graph.

Based on the community summary provided, extract information that is relevant to the user's query.

Guidelines:
- Provide ONLY information directly supported by the community summary
- Keep your response concise (2-3 sentences)
- If the summary is not relevant to the query, respond with "NOT_RELEVANT"
- Do NOT add information not present in the summary"""

    def _get_reduce_prompt(self, query: str, partial_answers: list[str]) -> str:
        """Get the prompt for reduce phase."""
        answers_text = "\n\n".join(
            f"Partial Answer {i + 1}:\n{ans}"
            for i, ans in enumerate(partial_answers)
        )

        return f"""Synthesize the following partial answers into a comprehensive response to the user's query.

Query: {query}

Partial Answers from different communities:
{answers_text}

Provide a well-structured, comprehensive answer that:
1. Directly addresses the query
2. Integrates information from multiple communities
3. Is clear and concise
4. Maintains factual accuracy"""

    def _extract_community_id(self, summary: str) -> str:
        """Extract community ID from summary string."""
        # Summary format: "[Community X (level Y)] ..."
        import re
        match = re.search(r'\[Community (\d+)', summary)
        return match.group(1) if match else "unknown"

    def _empty_response(self, query: str, start_time: float) -> SearchResponse:
        """Create an empty response when no communities are available."""
        elapsed = (time.perf_counter() - start_time) * 1000

        return SearchResponse(
            query=query,
            results=[],
            total_found=0,
            search_type="graphrag_global",
            elapsed_ms=elapsed,
        )
