"""LangGraph RAG agent with Self-RAG (Phase 5).

Enhanced agent pipeline:
  analyze → search → grade → (rewrite | generate) → hallucination_check → (regenerate | end)

Author: Claude Code
Version: 0.6.0 - Phase 5: Self-RAG & Corrective RAG
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import END, StateGraph

from src.pdf_framework.agents.rag.nodes import (
    check_hallucination,
    grade_documents,
    regenerate_answer,
    rewrite_query,
)
from src.pdf_framework.agents.rag.state import RAGState
from src.pdf_framework.config import AgentSettings, SelfRAGSettings
from src.pdf_framework.search.manager import SearchManager

logger = logging.getLogger(__name__)


def create_rag_agent(
    search_manager: SearchManager,
    settings: AgentSettings | None = None,
    self_rag_settings: SelfRAGSettings | None = None,
    api_key: str = "",
):
    """Create a LangGraph RAG agent with Self-RAG support.

    Phase 5 (v0.6.0) Pipeline:
      1. analyze_query — classify question and choose strategy
      2. execute_search — run search via SearchManager
      3. grade_documents — LLM-based relevance assessment
      4. rewrite_query — if relevance < threshold, rewrite and retry
      5. generate_answer — produce final answer from context
      6. check_hallucination — verify answer is grounded
      7. regenerate_answer — if hallucinated, regenerate with strict prompt

    Args:
        search_manager: Search manager for vector/graph/hybrid search
        settings: Agent configuration (model, temperature, etc.)
        self_rag_settings: Self-RAG configuration
        api_key: Anthropic API key

    Returns:
        Compiled LangGraph ready for invocation
    """
    settings = settings or AgentSettings()
    self_rag_settings = self_rag_settings or SelfRAGSettings()

    # LLM instances
    main_llm = ChatAnthropic(
        model=settings.model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        api_key=api_key or None,
    )

    grading_llm = ChatAnthropic(
        model=self_rag_settings.grading_model,
        temperature=0.0,
        max_tokens=1024,
        api_key=api_key or None,
    )

    rewrite_llm = ChatAnthropic(
        model=self_rag_settings.rewrite_model,
        temperature=0.3,
        max_tokens=1024,
        api_key=api_key or None,
    )

    hallucination_llm = ChatAnthropic(
        model=self_rag_settings.hallucination_model,
        temperature=0.0,
        max_tokens=1024,
        api_key=api_key or None,
    )

    parser = StrOutputParser()

    # ========== Node 1: Analyze Query ==========
    async def analyze_query(state: RAGState) -> dict:
        """Classify the question and choose the best search strategy."""
        question = state["question"]
        messages = [
            SystemMessage(
                content=(
                    "Classify the user question into one of these types: factual, analytical, comparative. "
                    "Also choose the best search strategy: vector (semantic similarity), "
                    "graph (entity relations), or hybrid (both). "
                    "Reply with exactly two words: <query_type> <strategy>. "
                    "Example: factual vector"
                )
            ),
            HumanMessage(content=question),
        ]
        response = await main_llm.ainvoke(messages)
        text = parser.invoke(response).strip().lower()
        parts = text.split()

        query_type = parts[0] if parts else "factual"
        strategy = parts[1] if len(parts) > 1 else "vector"

        # Fallback to available strategies
        available = search_manager.available_strategies
        if strategy not in available:
            strategy = available[0] if available else "vector"

        logger.info(f"[ANALYZE] query_type={query_type}, strategy={strategy}")

        return {
            "query_type": query_type,
            "search_strategy": strategy,
            "original_question": question,
        }

    # ========== Node 2: Execute Search ==========
    async def execute_search(state: RAGState) -> dict:
        """Run the chosen search strategy."""
        strategy = state.get("search_strategy", "vector")
        question = state["question"]
        k = settings.search_k

        logger.info(f"[SEARCH] strategy={strategy}, k={k}, query='{question[:50]}...'")

        try:
            response = await search_manager.search(
                query=question, strategy=strategy, k=k
            )
            context = _build_context(response)
            logger.info(f"[SEARCH] Found {len(response.results)} results")
            return {"search_response": response, "context": context}
        except Exception as e:
            logger.error(f"[SEARCH] Error: {e}")
            return {"error": str(e), "context": ""}

    # ========== Node 3: Grade Documents (Phase 5) ==========
    async def grade_documents_node(state: RAGState) -> dict:
        """Grade retrieved documents for relevance."""
        if not self_rag_settings.enabled:
            # Self-RAG disabled: use legacy evaluation
            return _legacy_evaluate_results(state)

        return await grade_documents(state, grading_llm, self_rag_settings)

    def _legacy_evaluate_results(state: RAGState) -> dict:
        """Legacy evaluation for backward compatibility."""
        response = state.get("search_response")
        if not response or not response.results:
            return {"relevance_score": 0.0, "needs_more_context": True}

        avg_score = sum(r.score for r in response.results) / len(response.results)
        needs_more = avg_score < 0.3 or len(response.results) < 2
        return {"relevance_score": avg_score, "needs_more_context": needs_more}

    # ========== Node 4: Rewrite Query (Phase 5) ==========
    async def rewrite_query_node(state: RAGState) -> dict:
        """Rewrite query when relevance is low."""
        return await rewrite_query(state, rewrite_llm, self_rag_settings)

    # ========== Node 5: Generate Answer ==========
    async def generate_answer(state: RAGState) -> dict:
        """Generate the final answer from context."""
        question = state["question"]
        context = state.get("context", "")

        if not context:
            logger.warning("[GENERATE] No context available")
            return {
                "answer": "I couldn't find relevant information to answer your question.",
                "sources": [],
            }

        messages = [
            SystemMessage(
                content=(
                    "Answer the question using ONLY the context provided. "
                    "If the context is insufficient, say so. "
                    "Cite sources by their number [1], [2], etc.\n\n"
                    f"Context:\n{context}"
                )
            ),
            HumanMessage(content=question),
        ]

        response = await main_llm.ainvoke(messages)
        answer = parser.invoke(response)

        logger.info(f"[GENERATE] Generated answer ({len(answer)} chars)")

        search_resp = state.get("search_response")
        sources: list[str] = []
        if search_resp:
            for r in search_resp.results:
                src = r.chunk.metadata.get("source", "")
                if src and src not in sources:
                    sources.append(src)

        return {"answer": answer, "sources": sources}

    # ========== Node 6: Check Hallucination (Phase 5) ==========
    async def check_hallucination_node(state: RAGState) -> dict:
        """Check if answer is grounded in context."""
        if not self_rag_settings.enabled or not self_rag_settings.hallucination_check_enabled:
            logger.debug("[HALLUCINATION] Disabled, skipping")
            return {"is_hallucinated": False}

        return await check_hallucination(state, hallucination_llm, self_rag_settings)

    # ========== Node 7: Regenerate Answer (Phase 5) ==========
    async def regenerate_answer_node(state: RAGState) -> dict:
        """Regenerate answer with stricter prompt."""
        return await regenerate_answer(state, main_llm, self_rag_settings)

    # ========== Conditional Edges ==========

    def should_rewrite_or_generate(state: RAGState) -> str:
        """Decide whether to rewrite query or proceed to generation."""
        if not self_rag_settings.enabled:
            # Legacy behavior
            if state.get("needs_more_context") and state.get("search_strategy") != "hybrid":
                return "retry"
            return "generate"

        # Self-RAG behavior
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", self_rag_settings.max_retries)
        relevance_ratio = state.get("relevance_ratio", 0.0)

        if relevance_ratio < self_rag_settings.relevance_threshold and retry_count < max_retries:
            logger.info(f"[EDGE] relevance={relevance_ratio:.2%} < {self_rag_settings.relevance_threshold:.0%} → rewrite")
            return "rewrite"

        logger.info(f"[EDGE] relevance={relevance_ratio:.2%} ≥ threshold → generate")
        return "generate"

    def should_regenerate_or_end(state: RAGState) -> str:
        """Decide whether to regenerate answer or finish."""
        if not self_rag_settings.enabled or not self_rag_settings.hallucination_check_enabled:
            return "end"

        is_hallucinated = state.get("is_hallucinated", False)
        attempts = state.get("generation_attempts", 0)
        max_attempts = self_rag_settings.max_generation_attempts

        if is_hallucinated and attempts < max_attempts:
            logger.info(f"[EDGE] hallucinated={is_hallucinated}, attempts={attempts} < {max_attempts} → regenerate")
            return "regenerate"

        return "end"

    # ========== Build the Graph ==========
    graph = StateGraph(RAGState)

    # Add nodes
    graph.add_node("analyze", analyze_query)
    graph.add_node("search", execute_search)
    graph.add_node("grade", grade_documents_node)
    graph.add_node("rewrite", rewrite_query_node)
    graph.add_node("generate", generate_answer)
    graph.add_node("hallucinate_check", check_hallucination_node)
    graph.add_node("regenerate", regenerate_answer_node)

    # Set entry point
    graph.set_entry_point("analyze")

    # Define edges
    graph.add_edge("analyze", "search")
    graph.add_edge("search", "grade")

    # Conditional: grade → rewrite or generate
    graph.add_conditional_edges(
        "grade",
        should_rewrite_or_generate,
        {"rewrite": "rewrite", "generate": "generate", "retry": "rewrite"},
    )

    graph.add_edge("rewrite", "search")
    graph.add_edge("generate", "hallucinate_check")

    # Conditional: hallucinate_check → regenerate or end
    graph.add_conditional_edges(
        "hallucinate_check",
        should_regenerate_or_end,
        {"regenerate": "regenerate", "end": END},
    )

    graph.add_edge("regenerate", END)

    logger.info("[GRAPH] Compiled Self-RAG agent (v0.6.0)")

    return graph.compile()


def _build_context(response) -> str:
    """Build context string from search results.

    Args:
        response: SearchResponse with results

    Returns:
        Formatted context string
    """
    parts: list[str] = []
    for i, result in enumerate(response.results, 1):
        source = result.chunk.metadata.get("source", "unknown")
        page = result.chunk.metadata.get("page", "")
        page_str = f", p. {page}" if page else ""
        parts.append(
            f"[{i}] (source: {source}{page_str}, score: {result.score:.3f})\n"
            f"{result.chunk.content}"
        )
    return "\n\n---\n\n".join(parts)
