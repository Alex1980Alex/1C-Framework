"""Document Grader node for Self-RAG.

Evaluates each retrieved document for relevance to the query using LLM.

Author: Claude Code
Version: 0.6.0 - Phase 5.2: Document Grading
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from src.pdf_framework.agents.rag.state import RAGState
from src.pdf_framework.config import SelfRAGSettings

logger = logging.getLogger(__name__)


async def grade_documents(
    state: RAGState,
    llm: ChatAnthropic,
    settings: SelfRAGSettings,
) -> dict[str, Any]:
    """Grade each retrieved document for relevance to the query.

    Uses binary grading (yes/no) via fast LLM (Claude Haiku) to assess
    whether each document is relevant to the original question.

    Args:
        state: Current RAG state with search_response
        llm: LLM instance (should use Haiku for speed)
        settings: SelfRAGSettings configuration

    Returns:
        Updated state with:
        - graded_documents: List of grading results
        - relevance_ratio: Float (0.0-1.0) proportion of relevant docs
    """
    search_response = state.get("search_response")
    question = state.get("original_question") or state.get("question", "")

    if not search_response or not search_response.results:
        logger.warning("[GRADE] No search results to grade")
        return {
            "graded_documents": [],
            "relevance_ratio": 0.0,
        }

    graded = []
    parser = StrOutputParser()

    for i, result in enumerate(search_response.results, 1):
        content = result.chunk.content
        # Truncate very long content for grading
        content_preview = content[:500] + "..." if len(content) > 500 else content

        grade_prompt = _get_grading_prompt(question, content_preview)
        messages = [
            SystemMessage(content=grade_prompt["system"]),
            HumanMessage(content=grade_prompt["user"]),
        ]

        try:
            response = await llm.ainvoke(messages)
            result_text = parser.invoke(response).strip().lower()

            # Parse binary response
            is_relevant = _parse_relevance(result_text)

            logger.debug(
                f"[GRADE] Document {i}/{len(search_response.results)}: "
                f"{'relevant ✓' if is_relevant else 'not relevant ✗'} "
                f"(raw: {result_text[:50]})"
            )

            graded.append({
                "chunk_id": result.chunk.id,
                "is_relevant": is_relevant,
                "reason": result_text[:200],  # Store explanation
                "score": result.score,  # Original search score
                "content_preview": content_preview[:100],
            })

        except Exception as e:
            logger.error(f"[GRADE] Error grading document {i}: {e}")
            # On error, assume relevant to avoid false negatives
            graded.append({
                "chunk_id": result.chunk.id,
                "is_relevant": True,  # Fallback: assume relevant
                "reason": f"Error during grading: {str(e)}",
                "score": result.score,
                "content_preview": content_preview[:100],
            })

    # Calculate relevance ratio
    relevant_count = sum(1 for g in graded if g["is_relevant"])
    ratio = relevant_count / len(graded) if graded else 0.0

    logger.info(
        f"[GRADE] Relevance ratio: {ratio:.2%} "
        f"({relevant_count}/{len(graded)} relevant, threshold: {settings.relevance_threshold:.0%})"
    )

    return {
        "graded_documents": graded,
        "relevance_ratio": ratio,
    }


def _get_grading_prompt(question: str, content: str) -> dict[str, str]:
    """Build grading prompt for LLM.

    Args:
        question: User's original question
        content: Document content to evaluate

    Returns:
        Dict with system and user prompts
    """
    return {
        "system": (
            "You are a document relevance evaluator. "
            "Your task is to determine if a document contains information "
            "that could help answer a user's question.\n\n"
            "Reply with 'yes' if the document is relevant, 'no' if not relevant. "
            "You may include a brief explanation after your yes/no answer.\n\n"
            "Examples:\n"
            "- 'yes' or 'yes - contains definition'\n"
            "- 'no' or 'no - unrelated topic'\n"
        ),
        "user": (
            f"Question: {question}\n\n"
            f"Document content:\n{content}\n\n"
            f"Is this document relevant to the question? (yes/no)"
        ),
    }


def _parse_relevance(response: str) -> bool:
    """Parse binary relevance response from LLM.

    Args:
        response: LLM response text

    Returns:
        True if relevant, False otherwise
    """
    response_clean = response.strip().lower()

    # Check for positive indicators
    positive_words = ["yes", "relevant", "yes", "да"]
    negative_words = ["no", "not relevant", "unrelated", "no", "нет"]

    # Check starts with
    for word in positive_words:
        if response_clean.startswith(word):
            return True

    for word in negative_words:
        if response_clean.startswith(word):
            return False

    # Fallback: assume relevant if unclear
    logger.warning(f"[GRADE] Unclear grading response: '{response}', assuming relevant")
    return True
