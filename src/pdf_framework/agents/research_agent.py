"""Deep Research Agent (Phase 19).

Combines query decomposition, multi-step retrieval, and cross-document synthesis
for comprehensive research across multiple documents.

Based on R2R's Deep Research API pattern.

Author: Claude Code
Version: 1.0.0 - Phase 19: Deep Research Agent
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from src.pdf_framework.agents.cross_document_synthesizer import (
    CrossDocumentSynthesizer,
    SynthesizedAnswer,
)
from src.pdf_framework.agents.multi_step_retriever import (
    MultiStepRetriever,
    MultiStepResult,
)
from src.pdf_framework.agents.query_decomposer import (
    QueryDecomposer,
    QueryDecomposition,
)
from src.pdf_framework.config import Settings, get_settings
from src.pdf_framework.search.manager import SearchManager

logger = logging.getLogger(__name__)


class ResearchStep(BaseModel):
    """A single step in the research process."""

    step_type: str  # "decompose", "retrieve", "synthesize"
    description: str
    duration_ms: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)


class ResearchReport(BaseModel):
    """Complete research report with full citation chain."""

    original_query: str
    final_answer: str
    decomposition: QueryDecomposition | None = None
    retrieval_result: MultiStepResult | None = None
    synthesis: SynthesizedAnswer | None = None
    steps: list[ResearchStep] = Field(default_factory=list)
    total_duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeepResearchAgent:
    """Performs deep research across multiple documents.

    Workflow:
        1. Decompose complex query into sub-questions
        2. Perform multi-step retrieval with context accumulation
        3. Synthesize answer from multiple sources with citations
    """

    def __init__(
        self,
        search_manager: SearchManager,
        api_key: str = "",
        decomposer_model: str = "claude-sonnet-4-5-20250929",
        synthesizer_model: str = "claude-opus-4-6",
        max_retrieval_steps: int = 5,
        settings: Settings | None = None,
    ):
        """Initialize the deep research agent.

        Args:
            search_manager: Search manager for retrieval
            api_key: Anthropic API key (empty = use env)
            decomposer_model: Model for query decomposition
            synthesizer_model: Model for answer synthesis
            max_retrieval_steps: Maximum retrieval steps
            settings: Application settings
        """
        self._search_manager = search_manager
        self._settings = settings or get_settings()

        # Initialize components
        self._decomposer = QueryDecomposer(
            api_key=api_key,
            model=decomposer_model,
            settings=self._settings,
        )

        self._retriever = MultiStepRetriever(
            search_manager=search_manager,
            max_steps=max_retrieval_steps,
            settings=self._settings,
        )

        self._synthesizer = CrossDocumentSynthesizer(
            api_key=api_key,
            model=synthesizer_model,
            settings=self._settings,
        )

    async def research(
        self,
        query: str,
        context: str = "",
        enable_decomposition: bool = True,
        enable_synthesis: bool = True,
    ) -> ResearchReport:
        """Perform deep research on a query.

        Args:
            query: Research question
            context: Optional context from previous turns
            enable_decomposition: Use query decomposition
            enable_synthesis: Use cross-document synthesis

        Returns:
            Complete ResearchReport with all steps
        """
        import time

        t0 = time.time()
        steps: list[ResearchStep] = []

        report = ResearchReport(
            original_query=query,
            final_answer="",
        )

        # Step 1: Decompose query (if enabled)
        decomposition = None
        if enable_decomposition:
            step_t0 = time.time()
            decomposition = self._decomposer.decompose(query, context)
            steps.append(ResearchStep(
                step_type="decompose",
                description=f"Decomposed into {len(decomposition.sub_questions)} sub-questions",
                duration_ms=(time.time() - step_t0) * 1000,
                details={
                    "sub_questions": [sq.question for sq in decomposition.sub_questions],
                    "execution_order": decomposition.execution_order,
                },
            ))
            report.decomposition = decomposition

        # Step 2: Multi-step retrieval
        queries = (
            [sq.question for sq in decomposition.sub_questions]
            if decomposition
            else [query]
        )
        execution_order = (
            decomposition.execution_order
            if decomposition
            else None
        )

        step_t0 = time.time()
        retrieval_result = await self._retriever.retrieve(queries, execution_order)
        steps.append(ResearchStep(
            step_type="retrieve",
            description=f"Retrieved {retrieval_result.total_sources} sources in {len(retrieval_result.steps)} steps",
            duration_ms=(time.time() - step_t0) * 1000,
            details={
                "steps_count": len(retrieval_result.steps),
                "sources_count": retrieval_result.total_sources,
                "context_length": len(retrieval_result.accumulated_context),
            },
        ))
        report.retrieval_result = retrieval_result

        # Step 3: Cross-document synthesis (if enabled)
        if enable_synthesis and retrieval_result.all_results:
            step_t0 = time.time()
            synthesis = self._synthesizer.synthesize(
                query=query,
                results=retrieval_result.all_results,
                context=retrieval_result.accumulated_context,
            )
            steps.append(ResearchStep(
                step_type="synthesize",
                description=f"Synthesized answer with {len(synthesis.citations)} citations",
                duration_ms=(time.time() - step_t0) * 1000,
                details={
                    "citations_count": len(synthesis.citations),
                    "confidence": synthesis.confidence,
                    "conflicts": synthesis.conflicting_info,
                },
            ))
            report.synthesis = synthesis
            report.final_answer = synthesis.answer

        # If no synthesis, use accumulated context
        elif not enable_synthesis:
            report.final_answer = retrieval_result.accumulated_context or "No information found."

        # Finalize report
        report.total_duration_ms = (time.time() - t0) * 1000
        report.steps = steps

        logger.info(
            f"[DEEP_RESEARCH] Completed in {report.total_duration_ms:.0f}ms: "
            f"{len(steps)} steps, {retrieval_result.total_sources} sources"
        )

        return report

    async def simple_research(self, query: str) -> str:
        """Quick research without decomposition or synthesis.

        Args:
            query: Research question

        Returns:
            Research findings as text
        """
        report = await self.research(
            query=query,
            enable_decomposition=False,
            enable_synthesis=False,
        )
        return report.final_answer


async def deep_research(
    query: str,
    search_manager: SearchManager,
    api_key: str = "",
    context: str = "",
) -> ResearchReport:
    """Convenience function for deep research.

    Args:
        query: Research question
        search_manager: Search manager instance
        api_key: Anthropic API key
        context: Optional conversation context

    Returns:
        Complete ResearchReport
    """
    agent = DeepResearchAgent(search_manager=search_manager, api_key=api_key)
    return await agent.research(query, context)
