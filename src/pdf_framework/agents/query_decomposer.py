"""Query Decomposer for Deep Research (Phase 19.1).

Decomposes complex queries into sub-questions for multi-step retrieval.
Enables deep research across multiple documents.

Based on R2R's Deep Research API pattern.

Author: Claude Code
Version: 1.0.0 - Phase 19: Deep Research Agent
"""

import logging
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field

from src.pdf_framework.config import Settings, get_settings

logger = logging.getLogger(__name__)


class SubQuestion(BaseModel):
    """A sub-question from query decomposition."""

    question: str
    dependencies: list[int] = Field(default_factory=list)  # Indices of dependent questions
    rationale: str = ""  # Why this sub-question is needed
    search_terms: list[str] = Field(default_factory=list)  # Alternative search queries


class QueryDecomposition(BaseModel):
    """Result of query decomposition."""

    sub_questions: list[SubQuestion]
    execution_order: list[int]  # Order to execute sub-questions
    original_query: str
    reasoning: str = ""  # Overall decomposition strategy


class QueryDecomposer:
    """Decomposes complex queries into sub-questions.

    Uses LLM to analyze query structure and break it into
    answerable components that can be resolved sequentially.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-5-20250929",
        max_sub_questions: int = 5,
        settings: Settings | None = None,
    ):
        """Initialize the query decomposer.

        Args:
            api_key: Anthropic API key (empty = use env)
            model: Claude model for decomposition
            max_sub_questions: Maximum sub-questions to generate
            settings: Application settings
        """
        self._client = Anthropic(api_key=api_key or None)
        self._model = model
        self._max_sub_questions = max_sub_questions
        self._settings = settings or get_settings()

    def decompose(self, query: str, context: str = "") -> QueryDecomposition:
        """Decompose a complex query into sub-questions.

        Args:
            query: User's query to decompose
            context: Optional context from previous turns

        Returns:
            QueryDecomposition with sub-questions
        """
        prompt = self._build_decomposition_prompt(query, context)

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            result = response.content[0].text
            decomposition = self._parse_decomposition(result, query)

            logger.info(
                f"[QUERY_DECOMPOSER] Split query into {len(decomposition.sub_questions)} sub-questions"
            )

            return decomposition

        except Exception as e:
            logger.error(f"[QUERY_DECOMPOSER] Failed to decompose query: {e}")
            # Fallback: single question
            return QueryDecomposition(
                sub_questions=[
                    SubQuestion(
                        question=query,
                        dependencies=[],
                        rationale="Fallback: direct query",
                    )
                ],
                execution_order=[0],
                original_query=query,
                reasoning="Decomposition failed, using direct query",
            )

    def _build_decomposition_prompt(self, query: str, context: str) -> str:
        """Build prompt for query decomposition.

        Args:
            query: User query
            context: Optional context

        Returns:
            Prompt string
        """
        prompt = f"""You are a research assistant specializing in breaking down complex questions into manageable sub-questions.

**User Query:**
{query}

**Your Task:**
Break this query into 2-5 sub-questions that, when answered together, will provide a comprehensive answer to the original query.

**Guidelines:**
1. Each sub-question should be specific and answerable from documentation
2. Identify dependencies between sub-questions (e.g., Q2 depends on Q1's answer)
3. Include search terms/phrases that would help find relevant information
4. Explain WHY each sub-question is needed

**Output Format:**
Return a JSON object with this structure:
{{
    "reasoning": "Overall strategy for decomposition",
    "sub_questions": [
        {{
            "question": "Specific sub-question",
            "dependencies": [],  // List of indices this depends on
            "rationale": "Why this sub-question matters",
            "search_terms": ["term1", "term2", "phrase with spaces"]
        }}
    ],
    "execution_order": [0, 1, 2]  // Order to execute (respecting dependencies)
}}

**Example:**
Query: "How does 1C:Enterprise handle multi-user concurrency and what are the best practices?"

{{
    "reasoning": "This query requires understanding both the technical mechanism and practical recommendations",
    "sub_questions": [
        {{
            "question": "What is the mechanism for handling concurrent user access in 1C:Enterprise?",
            "dependencies": [],
            "rationale": "Need to understand the technical foundation first",
            "search_terms": ["concurrency", "locking", "transactions", "optimistic lock"]
        }},
        {{
            "question": "What are the recommended practices for developing multi-user applications?",
            "dependencies": [0],
            "rationale": "Best practices depend on understanding the concurrency model",
            "search_terms": ["best practices", "multi-user", "development guidelines", "recommendations"]
        }},
        {{
            "question": "What common issues arise in multi-user scenarios and how to resolve them?",
            "dependencies": [0],
            "rationale": "Practical problems and solutions based on the concurrency mechanism",
            "search_terms": ["deadlocks", "conflicts", "contention", "performance"]
        }}
    ],
    "execution_order": [0, 1, 2]
}}
"""

        if context:
            prompt = f"**Context from conversation:**\n{context}\n\n" + prompt

        return prompt

    def _parse_decomposition(self, result: str, original_query: str) -> QueryDecomposition:
        """Parse LLM response into QueryDecomposition.

        Args:
            result: LLM response text
            original_query: Original user query

        Returns:
            Parsed QueryDecomposition
        """
        import json

        try:
            # Extract JSON from response
            start = result.find("{")
            end = result.rfind("}") + 1

            if start == -1 or end == 0:
                raise ValueError("No JSON found in response")

            json_str = result[start:end]
            data = json.loads(json_str)

            # Parse sub-questions
            sub_questions = []
            for sq in data.get("sub_questions", []):
                sub_questions.append(SubQuestion(
                    question=sq["question"],
                    dependencies=sq.get("dependencies", []),
                    rationale=sq.get("rationale", ""),
                    search_terms=sq.get("search_terms", []),
                ))

            return QueryDecomposition(
                sub_questions=sub_questions,
                execution_order=data.get("execution_order", list(range(len(sub_questions)))),
                original_query=original_query,
                reasoning=data.get("reasoning", ""),
            )

        except Exception as e:
            logger.warning(f"[QUERY_DECOMPOSER] Failed to parse decomposition: {e}")
            # Fallback: single question
            return QueryDecomposition(
                sub_questions=[
                    SubQuestion(
                        question=original_query,
                        dependencies=[],
                        rationale="Fallback: direct query",
                    )
                ],
                execution_order=[0],
                original_query=original_query,
                reasoning="Parse error, using direct query",
            )


def decompose_query(
    query: str,
    api_key: str = "",
    model: str = "claude-sonnet-4-5-20250929",
    context: str = "",
) -> QueryDecomposition:
    """Convenience function for query decomposition.

    Args:
        query: User query to decompose
        api_key: Anthropic API key
        model: Claude model to use
        context: Optional conversation context

    Returns:
        QueryDecomposition with sub-questions
    """
    decomposer = QueryDecomposer(api_key=api_key, model=model)
    return decomposer.decompose(query, context)
