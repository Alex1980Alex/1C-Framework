"""Multi-Step Retriever for Deep Research (Phase 19.2).

Performs sequential retrieval with context accumulation.
Uses results from previous searches to inform subsequent searches.

Based on R2R's iterative retrieval pattern.

Author: Claude Code
Version: 1.0.0 - Phase 19: Deep Research Agent
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from src.pdf_framework.config import Settings, get_settings
from src.pdf_framework.schemas.documents import SearchResult, SearchResponse
from src.pdf_framework.search.manager import SearchManager

logger = logging.getLogger(__name__)


class RetrievalStep(BaseModel):
    """A single step in multi-step retrieval."""

    step_number: int
    query: str
    results: list[SearchResult]
    context_used: str = ""  # Context from previous steps
    new_findings: str = ""  # Summary of what was found
    sources_count: int = 0


class MultiStepResult(BaseModel):
    """Result of multi-step retrieval."""

    steps: list[RetrievalStep]
    all_results: list[SearchResult]
    accumulated_context: str
    total_sources: int
    final_summary: str = ""


class MultiStepRetriever:
    """Performs multi-step retrieval with context accumulation.

    Each step builds on the context from previous steps,
    enabling deep research across multiple documents.
    """

    def __init__(
        self,
        search_manager: SearchManager,
        max_steps: int = 5,
        results_per_step: int = 5,
        max_context_tokens: int = 4000,
        settings: Settings | None = None,
    ):
        """Initialize the multi-step retriever.

        Args:
            search_manager: Search manager for retrieval
            max_steps: Maximum retrieval steps
            results_per_step: Results to retrieve per step
            max_context_tokens: Maximum context to accumulate
            settings: Application settings
        """
        self._search_manager = search_manager
        self._max_steps = max_steps
        self._results_per_step = results_per_step
        self._max_context_tokens = max_context_tokens
        self._settings = settings or get_settings()

    async def retrieve(
        self,
        queries: list[str],
        execution_order: list[int] | None = None,
    ) -> MultiStepResult:
        """Perform multi-step retrieval.

        Args:
            queries: List of queries (possibly from decomposition)
            execution_order: Order to execute queries (default: sequential)

        Returns:
            MultiStepResult with all steps and accumulated context
        """
        if execution_order is None:
            execution_order = list(range(len(queries)))

        steps: list[RetrievalStep] = []
        all_results: list[SearchResult] = []
        accumulated_context = ""

        for step_idx, query_idx in enumerate(execution_order):
            if step_idx >= self._max_steps:
                break

            query = queries[query_idx]

            # Augment query with accumulated context
            augmented_query = self._augment_query(query, accumulated_context)

            # Perform search
            logger.info(f"[MULTI_STEP] Step {step_idx + 1}: {query[:60]}...")

            search_response = await self._search_manager.search(
                query=augmented_query,
                strategy="hybrid",  # Use best strategy
                k=self._results_per_step,
            )

            # Extract results
            results = search_response.results
            all_results.extend(results)

            # Summarize new findings
            new_findings = self._summarize_findings(results)

            # Update accumulated context
            accumulated_context = self._update_context(
                accumulated_context,
                new_findings,
            )

            # Record step
            step = RetrievalStep(
                step_number=step_idx + 1,
                query=query,
                results=results,
                context_used=accumulated_context[:200] + "..." if len(accumulated_context) > 200 else accumulated_context,
                new_findings=new_findings,
                sources_count=len(results),
            )
            steps.append(step)

        # Deduplicate results by chunk ID
        seen_ids = set()
        unique_results = []
        for result in all_results:
            if result.chunk.id not in seen_ids:
                seen_ids.add(result.chunk.id)
                unique_results.append(result)

        return MultiStepResult(
            steps=steps,
            all_results=unique_results,
            accumulated_context=accumulated_context,
            total_sources=len(unique_results),
        )

    def _augment_query(self, query: str, context: str) -> str:
        """Augment query with accumulated context.

        Args:
            query: Current query
            context: Accumulated context from previous steps

        Returns:
            Augmented query string
        """
        if not context:
            return query

        # For now, just use the original query
        # In production, could use LLM to rewrite query based on context
        return query

    def _summarize_findings(self, results: list[SearchResult]) -> str:
        """Summarize key findings from search results.

        Args:
            results: Search results from current step

        Returns:
            Summary of findings
        """
        if not results:
            return "No relevant information found."

        # Extract key information from top results
        findings = []

        for i, result in enumerate(results[:3]):  # Top 3 results
            content = result.chunk.content
            source = result.chunk.metadata.get("source", "Unknown")

            finding = f"[Source {i + 1}: {source}]\n{content[:300]}"
            if len(content) > 300:
                finding += "..."

            findings.append(finding)

        return "\n\n".join(findings)

    def _update_context(self, current_context: str, new_findings: str) -> str:
        """Update accumulated context with new findings.

        Args:
            current_context: Current accumulated context
            new_findings: New findings from latest step

        Returns:
            Updated context (truncated to max tokens)
        """
        updated = current_context

        if new_findings:
            if updated:
                updated += "\n\n---\n\n" + new_findings
            else:
                updated = new_findings

        # Truncate to max tokens (rough estimate: 1 token ≈ 4 chars)
        max_chars = self._max_context_tokens * 4
        if len(updated) > max_chars:
            updated = updated[:max_chars] + "\n\n[Context truncated due to length...]"

        return updated


async def retrieve_multi_step(
    queries: list[str],
    search_manager: SearchManager,
    max_steps: int = 5,
) -> MultiStepResult:
    """Convenience function for multi-step retrieval.

    Args:
        queries: List of queries to retrieve
        search_manager: Search manager instance
        max_steps: Maximum steps to execute

    Returns:
        MultiStepResult with all retrieval steps
    """
    retriever = MultiStepRetriever(
        search_manager=search_manager,
        max_steps=max_steps,
    )
    return await retriever.retrieve(queries)
