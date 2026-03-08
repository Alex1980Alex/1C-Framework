"""Query Rewriter node for Self-RAG.

Rewrites the query when document relevance is low, with strategy escalation.

Author: Claude Code
Version: 0.6.0 - Phase 5.3: Query Rewriting
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from src.pdf_framework.agents.rag.state import RAGState
from src.pdf_framework.config import SelfRAGSettings
from src.shared.llm_rotation.adapter import cheap_llm_call, is_cheap_llm_enabled

logger = logging.getLogger(__name__)

# Strategy escalation order: vector → hybrid → mmr (always registered)
STRATEGY_ESCALATION: dict[str, str] = {
    "vector": "hybrid",
    "hybrid": "mmr",
    "mmr": "mmr",  # Max level
    "graph": "hybrid",
    "two_stage": "two_stage",  # Already at advanced level
}


async def rewrite_query(
    state: RAGState,
    llm: ChatAnthropic,
    settings: SelfRAGSettings,
) -> dict[str, Any]:
    """Rewrite the query and optionally escalate search strategy.

    When document relevance is low, the query is rewritten to improve results.
    On second retry, the search strategy is escalated (vector → hybrid → two_stage).

    Args:
        state: Current RAG state
        llm: LLM instance for query rewriting
        settings: SelfRAGSettings configuration

    Returns:
        Updated state with:
        - question: Rewritten query
        - search_strategy: Potentially escalated strategy
        - retry_count: Incremented retry count
    """
    retry_count = state.get("retry_count", 0)
    original_question = state.get("original_question") or state.get("question", "")
    current_strategy = state.get("search_strategy", "vector")

    # First call: store original question
    if "original_question" not in state:
        logger.info("[REWRITE] First rewrite attempt, storing original question")

    new_retry_count = retry_count + 1

    # Determine new strategy (escalation on second retry)
    new_strategy = current_strategy
    if settings.strategy_escalation_enabled and new_retry_count >= 2:
        new_strategy = STRATEGY_ESCALATION.get(current_strategy, "hybrid")
        logger.info(
            f"[REWRITE] Strategy escalated: {current_strategy} → {new_strategy}"
        )
    else:
        logger.debug(f"[REWRITE] Keeping strategy: {current_strategy}")

    # Rewrite query via LLM
    rewritten = await _rewrite_via_llm(
        original_question=original_question,
        llm=llm,
        attempt=new_retry_count,
        graded_docs=state.get("graded_documents", []),
    )

    logger.info(
        f"[REWRITE] Retry {new_retry_count}/{settings.max_retries}: "
        f'"{original_question[:50]}..." → "{rewritten[:50]}..." '
        f"(strategy: {new_strategy})"
    )

    return {
        "question": rewritten,
        "search_strategy": new_strategy,
        "retry_count": new_retry_count,
    }


async def _rewrite_via_llm(
    original_question: str,
    llm: ChatAnthropic,
    attempt: int,
    graded_docs: list[dict],
) -> str:
    """Rewrite query using LLM.

    Args:
        original_question: Original user question
        llm: LLM instance
        attempt: Current retry attempt (1-based)
        graded_docs: Previously graded documents for context

    Returns:
        Rewritten query string
    """
    parser = StrOutputParser()

    # Build context from irrelevant docs
    irrelevant_context = ""
    if graded_docs:
        irrelevant = [d for d in graded_docs if not d["is_relevant"]]
        if irrelevant:
            irrelevant_context = (
                "\n\nPrevious search found these irrelevant topics:\n"
                + "\n".join(
                    f"- {d.get('content_preview', 'N/A')[:80]}..."
                    for d in irrelevant[:3]
                )
            )

    system_prompt = (
        "You are a query optimization expert. "
        "Your task is to rewrite a user's question to improve search results.\n\n"
        "Guidelines:\n"
        "- Keep the core intent and meaning\n"
        "- Use more specific or technical terms if appropriate\n"
        "- Break complex questions into simpler components\n"
        "- Add relevant domain-specific terminology\n"
        "- Return ONLY the rewritten question, no explanations\n"
    )

    user_prompt = (
        f"Original question: {original_question}{irrelevant_context}\n\n"
        f"Rewrite this question to get better search results. "
        f"Return ONLY the rewritten question."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    # Ralph Wiggum: self-correcting retry with prefix cleanup
    max_rw_retries = 2
    rw_feedback = ""
    bad_prefixes = [
        "Rewritten:", "Rewritten question:", "Revised:",
        "Here is the rewritten question:", "The rewritten question is:",
        "Переформулированный вопрос:", "Переписанный вопрос:",
    ]

    for rw_attempt in range(1, max_rw_retries + 1):
        try:
            attempt_messages = list(messages)
            if rw_feedback:
                attempt_messages.append(HumanMessage(content=f"\u26a0\ufe0f {rw_feedback}"))

            response = await llm.ainvoke(attempt_messages)
            rewritten = parser.invoke(response).strip()

            # Clean prefixes
            for prefix in bad_prefixes:
                if rewritten.lower().startswith(prefix.lower()):
                    rewritten = rewritten[len(prefix):].strip()

            # Validate: non-empty, not identical, not too long
            if not rewritten or len(rewritten) < 5:
                rw_feedback = "Return ONLY the rewritten question, nothing else. It must not be empty."
                logger.warning(f"[REWRITE] Attempt {rw_attempt}: empty result")
                continue

            if rewritten.strip() == original_question.strip():
                rw_feedback = "The rewritten question must be DIFFERENT from the original. Use different words."
                logger.warning(f"[REWRITE] Attempt {rw_attempt}: identical to original")
                continue

            return rewritten

        except Exception as e:
            logger.error(f"[REWRITE] Attempt {rw_attempt} error: {e}")
            rw_feedback = f"Previous call failed: {e}. Try again."

    logger.warning("[REWRITE] All attempts failed, using original question")
    return original_question
