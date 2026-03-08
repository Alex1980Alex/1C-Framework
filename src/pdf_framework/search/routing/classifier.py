"""Query Complexity Classifier for Adaptive RAG.

Classifies user queries by complexity to determine optimal search strategy.

Author: Claude Code
Version: 0.9.0 - Phase 8.1: Query Complexity Classifier
"""

import logging
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel

from src.shared.llm_rotation.adapter import cheap_llm_call, is_cheap_llm_enabled

logger = logging.getLogger(__name__)


class QueryClassification(BaseModel):
    """Result of query complexity classification."""

    # Complexity level
    complexity: Literal["simple", "moderate", "complex", "thematic"]

    # Query type
    query_type: str  # factual, analytical, comparative, thematic

    # Confidence in classification (0.0-1.0)
    confidence: float

    # Reasoning (for debugging)
    reasoning: str = ""


class QueryClassifier:
    """
    LLM-based query complexity classifier.

    Determines the optimal search strategy by analyzing query complexity:
    - simple: Factual, single entity lookup (fast path)
    - moderate: Conceptual, how/what/why questions
    - complex: Comparison, multi-step analysis, listing
    - thematic: Broad overview, main themes
    """

    def __init__(
        self,
        llm: ChatAnthropic | None = None,
        model: str = "claude-haiku-4-5-20251001",
        cache_enabled: bool = True,
        api_key: str = "",
        base_url: str = "",
    ):
        """
        Initialize query classifier.

        Args:
            llm: LLM for classification (default: Haiku for speed)
            model: Model name to use
            cache_enabled: Enable LRU cache for classifications
            api_key: Anthropic API key
            base_url: Custom API endpoint (for Z.AI or other proxies)
        """
        if llm is None:
            llm_kwargs = dict(model=model, temperature=0.0, max_tokens=512)
            if api_key:
                llm_kwargs["api_key"] = api_key
            if base_url:
                llm_kwargs["base_url"] = base_url
            llm = ChatAnthropic(**llm_kwargs)
        self._llm = llm
        self._parser = StrOutputParser()
        self._cache_enabled = cache_enabled

        # Simple LRU cache (dict-based)
        self._cache: dict[str, QueryClassification] = {}

    def classify_fast(self, query: str) -> QueryClassification | None:
        """Rule-based fast classification (~0ms). Returns None if uncertain.

        Covers ~80% of queries without LLM call. Patterns are tuned for
        Russian-language 1C documentation queries.
        """
        q = query.strip().lower()
        words = q.split()
        word_count = len(words)

        if not q:
            return None

        # Thematic patterns — broad overview queries
        _THEMATIC = (
            "обзор", "основные темы", "общая картина", "резюме", "итог",
            "о чём", "о чем", "ключевые", "главные мысли", "краткое содержание",
        )
        if any(p in q for p in _THEMATIC):
            return QueryClassification(
                complexity="thematic", query_type="thematic",
                confidence=0.85, reasoning="rule:thematic_keywords",
            )

        # Complex patterns — comparison, enumeration, multi-step
        _COMPLEX = (
            "сравни", "сравнение", "отличия", "различия", "плюсы и минусы",
            "перечисли все", "перечисли основные", "пошаговый", "пошагово",
            "compare", "difference", "list all",
        )
        if any(p in q for p in _COMPLEX):
            return QueryClassification(
                complexity="complex", query_type="comparative",
                confidence=0.85, reasoning="rule:complex_keywords",
            )

        # Simple patterns — short factual queries
        _SIMPLE_START = (
            "что такое", "кто такой", "где находится", "какой тип",
            "what is", "who is", "where is", "define",
        )
        if any(q.startswith(p) for p in _SIMPLE_START) and word_count <= 8:
            return QueryClassification(
                complexity="simple", query_type="factual",
                confidence=0.80, reasoning="rule:simple_start",
            )

        # Very short queries → simple
        if word_count <= 3:
            return QueryClassification(
                complexity="simple", query_type="factual",
                confidence=0.75, reasoning="rule:short_query",
            )

        # Moderate patterns — how/why questions
        _MODERATE_START = (
            "как ", "почему ", "зачем ", "каким образом ",
            "how ", "why ", "explain ",
        )
        if any(q.startswith(p) for p in _MODERATE_START):
            return QueryClassification(
                complexity="moderate", query_type="analytical",
                confidence=0.80, reasoning="rule:moderate_start",
            )

        return None  # Uncertain → fall through to LLM

    async def classify(self, query: str) -> QueryClassification:
        """
        Classify query by complexity and type.

        Uses fast rule-based classification first (~0ms for ~80% of queries),
        falls back to LLM for ambiguous cases.

        Args:
            query: User search query

        Returns:
            QueryClassification with complexity, type, and confidence
        """
        # Check cache first
        if self._cache_enabled and query in self._cache:
            logger.debug(f"[CLASSIFIER] Cache hit for query: {query[:30]}...")
            return self._cache[query]

        # Try fast rule-based classification (~0ms)
        fast_result = self.classify_fast(query)
        if fast_result is not None:
            if self._cache_enabled:
                self._cache[query] = fast_result
            logger.info(
                "[CLASSIFIER] Fast: '%s' -> %s (%s, confidence=%.2f)",
                query[:40], fast_result.complexity,
                fast_result.query_type, fast_result.confidence,
            )
            return fast_result

        # Normalize query for LLM classification
        normalized_query = query.strip()
        if not normalized_query:
            return QueryClassification(
                complexity="moderate",
                query_type="unknown",
                confidence=0.0,
                reasoning="Empty query",
            )

        try:
            classification = await self._classify_with_llm(normalized_query)

            # Cache the result
            if self._cache_enabled:
                self._cache[query] = classification

            logger.info(
                "[CLASSIFIER] LLM: '%s' -> %s (%s, confidence=%.2f)",
                query[:40], classification.complexity,
                classification.query_type, classification.confidence,
            )

            return classification

        except Exception as e:
            logger.error(f"[CLASSIFIER] Error classifying query: {e}")
            # Fallback to moderate (safe default)
            return QueryClassification(
                complexity="moderate",
                query_type="unknown",
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
            )

    async def _classify_with_llm(self, query: str) -> QueryClassification:
        """Classify query using LLM."""
        prompt = self._get_classification_prompt(query)

        messages = [
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=prompt),
        ]

        response = await self._llm.ainvoke(messages)
        result_text = self._parser.invoke(response).strip().lower()

        return self._parse_classification(result_text)

    def _get_system_prompt(self) -> str:
        """Get system prompt for query classification."""
        return """You are a query classification expert for a RAG (Retrieval Augmented Generation) system.

Your task is to classify user queries by complexity and type.

Complexity levels:
- simple: Factual, single entity lookup (e.g., "What version?", "Who is the author?")
- moderate: Conceptual question, how/what/why (e.g., "How does X work?", "What is Y?")
- complex: Comparison, multi-step analysis, listing (e.g., "Compare X and Y", "List all Z")
- thematic: Broad overview, main themes (e.g., "What are the main topics?", "Overview of this document")

Query types:
- factual: Asking for specific facts
- analytical: Asking for analysis or explanation
- comparative: Asking to compare things
- thematic: Asking about themes or overviews

Reply in this exact format:
complexity query_type confidence

Examples:
- What is the version? simple factual 0.95
- How does the authentication work? moderate analytical 0.88
- Compare PostgreSQL and MySQL complex comparative 0.82
- What are the main topics in this document? thematic thematic 0.90"""

    def _get_classification_prompt(self, query: str) -> str:
        """Build classification prompt for a query."""
        return f"""Classify this search query by complexity and type.

Query: {query}

Reply with: complexity query_type confidence

Where:
- complexity is one of: simple, moderate, complex, thematic
- query_type is one of: factual, analytical, comparative, thematic
- confidence is a float from 0.0 to 1.0

Keep your response concise - just the three values on one line."""

    def _parse_classification(self, text: str) -> QueryClassification:
        """
        Parse LLM response into QueryClassification.

        Args:
            text: LLM response text

        Returns:
            Parsed QueryClassification
        """
        parts = text.strip().split()

        if len(parts) < 2:
            return QueryClassification(
                complexity="moderate",
                query_type="unknown",
                confidence=0.0,
                reasoning=f"Could not parse: {text}",
            )

        # Parse complexity
        complexity = parts[0]
        if complexity not in ("simple", "moderate", "complex", "thematic"):
            complexity = "moderate"  # Safe default

        # Parse query type
        query_type = parts[1] if len(parts) > 1 else "unknown"
        if query_type not in ("factual", "analytical", "comparative", "thematic"):
            query_type = "analytical"  # Safe default

        # Parse confidence
        try:
            confidence_text = parts[2] if len(parts) > 2 else "0.5"
            confidence = float(confidence_text)
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, IndexError):
            confidence = 0.5

        return QueryClassification(
            complexity=complexity,
            query_type=query_type,
            confidence=confidence,
            reasoning=f"LLM classification: {text}",
        )

    def clear_cache(self) -> None:
        """Clear the classification cache."""
        self._cache.clear()
        logger.info("[CLASSIFIER] Cache cleared")

    def get_cached_classification(self, query: str) -> QueryClassification | None:
        """Get cached classification if available."""
        return self._cache.get(query)
