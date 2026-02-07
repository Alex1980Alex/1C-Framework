"""Hallucination Checker node for Self-RAG.

Verifies that the generated answer is grounded in the retrieved context.

Author: Claude Code
Version: 0.6.0 - Phase 5.4: Hallucination Checking
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from src.pdf_framework.agents.rag.state import RAGState
from src.pdf_framework.config import SelfRAGSettings

logger = logging.getLogger(__name__)


async def check_hallucination(
    state: RAGState,
    llm: ChatAnthropic,
    settings: SelfRAGSettings,
) -> dict[str, Any]:
    """Check if the answer is grounded in the retrieved context.

    Verifies that every claim in the answer is supported by the provided context.

    Args:
        state: Current RAG state with answer and context
        llm: LLM instance for hallucination checking
        settings: SelfRAGSettings configuration

    Returns:
        Updated state with:
        - is_hallucinated: Boolean result
        - hallucination_reason: Explanation
    """
    if not settings.hallucination_check_enabled:
        logger.debug("[HALLUCINATION] Disabled, skipping check")
        return {"is_hallucinated": False, "hallucination_reason": "Check disabled"}

    answer = state.get("answer", "")
    context = state.get("context", "")

    if not answer:
        logger.warning("[HALLUCINATION] No answer to check")
        return {"is_hallucinated": False, "hallucination_reason": "No answer generated"}

    if not context:
        logger.warning("[HALLUCINATION] No context for verification")
        # Without context, we can't verify - assume potentially hallucinated
        return {
            "is_hallucinated": True,
            "hallucination_reason": "No context provided for verification",
        }

    check_prompt = _get_hallucination_check_prompt(context, answer)
    messages = [
        SystemMessage(content=check_prompt["system"]),
        HumanMessage(content=check_prompt["user"]),
    ]

    try:
        parser = StrOutputParser()
        response = await llm.ainvoke(messages)
        result_text = parser.invoke(response).strip().lower()

        is_hallucinated = _parse_hallucination_result(result_text)

        if is_hallucinated:
            logger.warning(
                f"[HALLUCINATION] Detected! Reason: {result_text[:200]}"
            )
        else:
            logger.info("[HALLUCINATION] Answer is grounded ✓")

        return {
            "is_hallucinated": is_hallucinated,
            "hallucination_reason": result_text[:300],
        }

    except Exception as e:
        logger.error(f"[HALLUCINATION] Check error: {e}, assuming grounded")
        # On error, assume grounded to avoid false positives
        return {
            "is_hallucinated": False,
            "hallucination_reason": f"Check error: {str(e)}",
        }


async def regenerate_answer(
    state: RAGState,
    llm: ChatAnthropic,
    settings: SelfRAGSettings,
) -> dict[str, Any]:
    """Regenerate answer with stricter prompt after hallucination detected.

    Args:
        state: Current RAG state
        llm: LLM instance for regeneration
        settings: SelfRAGSettings configuration

    Returns:
        Updated state with:
        - answer: Regenerated answer
        - generation_attempts: Incremented
    """
    question = state.get("question", "")
    context = state.get("context", "")
    attempts = state.get("generation_attempts", 0) + 1

    logger.info(f"[REGENERATE] Attempt {attempts}/{settings.max_generation_attempts}")

    strict_prompt = f"""Answer the following question using ONLY the context provided below.

CRITICAL RULES:
1. You MUST use ONLY information from the context below
2. Do NOT add any information not present in the context
3. If the context doesn't contain the answer, say "I don't have enough information to answer this question"
4. Do NOT make up facts, numbers, dates, or any details
5. Keep your answer concise and directly supported by the context

Context:
{context}

Question: {question}

Answer:"""

    messages = [HumanMessage(content=strict_prompt)]

    try:
        parser = StrOutputParser()
        response = await llm.ainvoke(messages)
        new_answer = parser.invoke(response).strip()

        logger.info("[REGENERATE] Generated stricter answer")

        # Extract sources from search response
        search_resp = state.get("search_response")
        sources: list[str] = []
        if search_resp:
            for r in search_resp.results:
                src = r.chunk.metadata.get("source", "")
                if src and src not in sources:
                    sources.append(src)

        return {
            "answer": new_answer,
            "generation_attempts": attempts,
            "sources": sources,
            "is_hallucinated": False,  # Assume regenerated answer is better
        }

    except Exception as e:
        logger.error(f"[REGENERATE] Error: {e}")
        # Return original answer on error
        return {
            "generation_attempts": attempts,
            "is_hallucinated": False,  # Don't block on error
        }


def _get_hallucination_check_prompt(context: str, answer: str) -> dict[str, str]:
    """Build hallucination check prompt for LLM.

    Args:
        context: Retrieved context
        answer: Generated answer

    Returns:
        Dict with system and user prompts
    """
    return {
        "system": (
            "You are a factual accuracy verifier. "
            "Your task is to determine if an answer is fully grounded in the provided context.\n\n"
            "An answer is grounded (not hallucinated) if:\n"
            "- All factual claims are supported by the context\n"
            "- No new information is introduced from outside the context\n"
            "- Numbers, dates, names, and specific details match the context\n\n"
            "Reply with:\n"
            "- 'grounded' if the answer is fully supported\n"
            "- 'not_grounded: <brief explanation>' if hallucinations are detected\n\n"
            "Examples:\n"
            "- 'grounded'\n"
            "- 'not_grounded: answer mentions 2024 but context only discusses 2023'\n"
        ),
        "user": (
            f"Context:\n{context}\n\n"
            f"Answer:\n{answer}\n\n"
            f"Is this answer fully grounded in the context? (grounded/not_grounded)"
        ),
    }


def _parse_hallucination_result(response: str) -> bool:
    """Parse hallucination check response from LLM.

    Args:
        response: LLM response text

    Returns:
        True if hallucinated, False if grounded
    """
    response_clean = response.strip().lower()

    # Check for negative indicators (hallucinated)
    hallucinated_words = [
        "not_grounded",
        "not grounded",
        "hallucinated",
        "not supported",
        "unsupported",
    ]
    grounded_words = ["grounded", "supported", "yes", "верно", "подтверждено"]

    for word in hallucinated_words:
        if word in response_clean:
            return True

    for word in grounded_words:
        if response_clean.startswith(word) or f" {word}" in response_clean:
            return False

    # Fallback: assume grounded if unclear
    logger.warning(f"[HALLUCINATION] Unclear response: '{response}', assuming grounded")
    return False
