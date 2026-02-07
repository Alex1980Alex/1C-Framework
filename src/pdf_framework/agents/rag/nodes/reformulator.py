"""History-Aware Query Reformulation node for Conversational RAG (Phase 9).

Reformulates user queries to be self-contained by resolving anaphoric
references ("this", "it", "how about") based on conversation history.

Author: Claude Code
Version: 1.0.0 - Phase 9.2: History-Aware Reformulation
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from src.pdf_framework.agents.memory.conversation import Message
from src.pdf_framework.agents.rag.state import RAGState

logger = logging.getLogger(__name__)


def _format_history(messages: list[Message]) -> str:
    """Format conversation history for LLM prompt."""
    if not messages:
        return "No previous conversation."

    lines = []
    for msg in messages:
        role = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{role}: {msg.content}")

    return "\n".join(lines)


def _get_reformulation_system_prompt() -> str:
    """Get system prompt for query reformulation."""
    return """You are an expert at reformulating questions to be self-contained.

Your task is to rewrite the latest user query so that it can be understood
WITHOUT relying on the conversation history.

Rules:
1. Resolve all pronouns and references (he, she, it, this, that, etc.)
2. Replace implicit references with the actual subject
3. Keep the original intent and meaning
4. Return ONLY the rewritten query, nothing else

Examples:
History: "What is PostgreSQL?" / "PostgreSQL is a relational database..."
Latest: "How do I install it?"
Rewritten: "How do I install PostgreSQL?"

History: "Tell me about registers in 1C" / "Registers store numeric data..."
Latest: "What about information registers?"
Rewritten: "What are information registers in 1C?"

History: (empty)
Latest: "What is 1C?"
Rewritten: "What is 1C?" (no change needed)

IMPORTANT: If there is no conversation history, return the query unchanged."""


def _get_reformulation_prompt(
    history: str,
    latest_query: str,
) -> str:
    """Build reformulation prompt."""
    return f"""Conversation history:
{history}

Latest user query: {latest_query}

Rewrite the latest query to be self-contained (resolve all references).
Return ONLY the rewritten query, nothing else."""


def _parse_reformulated_query(response: str) -> str:
    """Parse LLM response to extract reformulated query."""
    query = response.strip()

    # Remove common prefixes if present
    for prefix in ["Rewritten:", "Query:", "Answer:", "Reformulated:"]:
        if query.startswith(prefix):
            query = query[len(prefix):].strip()

    # Remove quotes if entire response is quoted
    if query.startswith('"') and query.endswith('"'):
        query = query[1:-1].strip()
    elif query.startswith("'") and query.endswith("'"):
        query = query[1:-1].strip()

    return query


async def reformulate_query(
    state: RAGState,
    llm: ChatAnthropic,
    enable_reformulation: bool = True,
) -> dict[str, Any]:
    """
    Reformulate query to be self-contained using conversation history.

    Args:
        state: RAGState with chat_history and question
        llm: LLM for reformulation
        enable_reformulation: Whether to perform reformulation

    Returns:
        Dict with potentially updated "question" field
    """
    question = state.get("question", "")
    history = state.get("chat_history", [])

    # Skip if no history or reformulation disabled
    if not history or not enable_reformulation:
        logger.debug("[REFORMULATOR] No reformulation needed")
        return {}

    if not question:
        return {}

    logger.info(f"[REFORMULATOR] Reformulating: {question[:50]}...")

    try:
        # Format history for prompt
        history_text = _format_history(history)
        prompt = _get_reformulation_prompt(history_text, question)

        messages = [
            SystemMessage(content=_get_reformulation_system_prompt()),
            HumanMessage(content=prompt),
        ]

        # Get reformulated query
        response = await llm.ainvoke(messages)
        parser = StrOutputParser()
        rewritten = _parse_reformulated_query(parser.invoke(response))

        # Log the reformulation
        if rewritten != question:
            logger.info(f"[REFORMULATOR] '{question[:40]}...' → '{rewritten[:40]}...'")
        else:
            logger.debug("[REFORMULATOR] No changes needed")

        return {"question": rewritten, "original_question": question}

    except Exception as e:
        logger.error(f"[REFORMULATOR] Error reformulating query: {e}")
        # Fallback: use original query
        return {"original_question": question}


def _should_reformulate(state: RAGState) -> bool:
    """
    Determine if query should be reformulated based on state.

    Args:
        state: RAGState

    Returns:
        True if reformulation should be performed
    """
    # Need history to reformulate
    history = state.get("chat_history", [])
    if not history:
        return False

    # Don't reformulate if explicitly disabled
    if state.get("disable_reformulation", False):
        return False

    return True


async def reformulate_query_node(
    state: RAGState,
    llm: ChatAnthropic,
    enable_reformulation: bool = True,
) -> dict[str, Any]:
    """
    LangGraph node wrapper for query reformulation.

    Args:
        state: RAGState
        llm: LLM for reformulation
        enable_reformulation: Whether to perform reformulation

    Returns:
        Dict with potentially updated question
    """
    if not _should_reformulate(state) or not enable_reformulation:
        return {}

    return await reformulate_query(state, llm, enable_reformulation)
