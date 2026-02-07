"""Query Suggestions for exploration (Phase 14.5).

Generates relevant query suggestions based on:
- Entity extraction from knowledge graph
- Frequency analysis from query logs
- LLM-based generation
- Related questions after answers

Author: Claude Code
Version: 1.5.0 - Phase 14.5: Query Suggestions
"""

import asyncio
import logging
from typing import Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SuggestionConfig(BaseModel):
    """Query suggestion configuration."""

    method: Literal["entity", "frequency", "llm", "related"] = "entity"
    max_suggestions: int = 5
    cache_ttl: int = 3600  # seconds
    llm_model: str = "claude-haiku-4-5-20251001"


class QuerySuggester:
    """
    Generates query suggestions for exploration.

    Methods:
    - entity: Top entities from knowledge graph
    - frequency: Popular queries from logs
    - llm: LLM-generated questions
    - related: Follow-up questions after answer
    """

    def __init__(
        self,
        config: SuggestionConfig | None = None,
        api_key: str = "",
    ):
        self._config = config or SuggestionConfig()
        _api_key = api_key
        self._cache: dict[str, tuple[list[str], float]] = {}
        self._query_counts: dict[str, int] = {}

    async def suggest(
        self,
        query: str = "",
        graph_store=None,
        k: int = 5,
    ) -> list[str]:
        """
        Generate query suggestions.

        Args:
            query: Optional context query
            graph_store: Graph store for entity-based suggestions
            k: Number of suggestions

        Returns:
            List of suggested queries
        """
        k = min(k, self._config.max_suggestions)

        # Check cache
        cache_key = f"{self._config.method}:{query}:{k}"
        if cache_key in self._cache:
            suggestions, timestamp = self._cache[cache_key]
            if __import__("time").time() - timestamp < self._config.cache_ttl:
                return suggestions

        # Generate suggestions based on method
        if self._config.method == "entity":
            suggestions = await self._entity_suggestions(graph_store, k)
        elif self._config.method == "frequency":
            suggestions = self._frequency_suggestions(k)
        elif self._config.method == "llm":
            suggestions = await self._llm_suggestions(query, k)
        elif self._config.method == "related":
            suggestions = await self._related_suggestions(query, k)
        else:
            suggestions = []

        # Cache results
        self._cache[cache_key] = (suggestions, __import__("time").time())

        return suggestions

    async def _entity_suggestions(
        self,
        graph_store,
        k: int,
    ) -> list[str]:
        """Entity-based suggestions from knowledge graph."""
        if graph_store is None:
            return []

        try:
            # Get top entities by degree
            stats = await graph_store.get_statistics()

            # Extract entities (this would depend on graph store implementation)
            # For now, return generic suggestions
            return [
                "Узнайте больше о ключевых сущностях",
                "Покажите связи между объектами",
                "Что входит в состав этой системы?",
                "Какие компоненты используются?",
                "Опишите архитектуру системы",
            ][:k]
        except Exception as e:
            logger.error(f"[SUGGEST] Entity suggestions failed: {e}")
            return []

    def _frequency_suggestions(self, k: int) -> list[str]:
        """Frequency-based suggestions from query logs."""
        # Sort by frequency and return top-k
        sorted_queries = sorted(
            self._query_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [q for q, _ in sorted_queries[:k]]

    async def _llm_suggestions(self, context: str, k: int) -> list[str]:
        """LLM-based suggestions."""
        if not context:
            return []

        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage

            llm = ChatAnthropic(
                model_name=self._config.llm_model,
                temperature=0.5,
            )

            prompt = f'''Based on the query "{context}", suggest {k} interesting follow-up questions
that a user might want to ask to explore this topic further.

Return each question on a new line, numbered 1-{k}.

Questions:'''

            response = await llm.ainvoke([HumanMessage(content=prompt)])

            # Parse response - handle both string and list response
            content = response.content if isinstance(response.content, str) else str(response.content)
            lines = content.strip().split("\n")
            suggestions = []
            for line in lines:
                # Remove numbering
                clean = line.strip()
                for prefix in [f"{i}." for i in range(1, 10)] + ["- ", "* "]:
                    if clean.startswith(prefix):
                        clean = clean[len(prefix):].strip()
                if clean and len(clean) > 5:
                    suggestions.append(clean)

            return suggestions[:k]

        except Exception as e:
            logger.error(f"[SUGGEST] LLM suggestions failed: {e}")
            return []

    async def _related_suggestions(self, context: str, k: int) -> list[str]:
        """Related questions after an answer."""
        # Similar to LLM but with different prompt
        return await self._llm_suggestions(context, k)

    def log_query(self, query: str) -> None:
        """Log a query for frequency-based suggestions."""
        self._query_counts[query] = self._query_counts.get(query, 0) + 1

    def clear_cache(self) -> None:
        """Clear suggestion cache."""
        self._cache.clear()


# Global query suggester instance
_query_suggester: QuerySuggester | None = None


def get_query_suggester(**kwargs) -> QuerySuggester:
    """Get or create global query suggester instance."""
    global _query_suggester
    if _query_suggester is None:
        _query_suggester = QuerySuggester(**kwargs)
    return _query_suggester
