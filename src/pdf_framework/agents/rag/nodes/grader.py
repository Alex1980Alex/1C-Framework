"""Document Grader node for Self-RAG.

Evaluates each retrieved document for relevance to the query using LLM.
Optimized: parallel grading + score-based pre-filter.

Author: Claude Code
Version: 0.6.1 - Parallel grading & score pre-filter
"""

import asyncio
import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from src.pdf_framework.agents.rag.state import RAGState
from src.pdf_framework.config import SelfRAGSettings

logger = logging.getLogger(__name__)

_parser = StrOutputParser()


async def grade_documents(
    state: RAGState,
    llm: ChatAnthropic,
    settings: SelfRAGSettings,
) -> dict[str, Any]:
    """Grade retrieved documents for relevance — parallel + pre-filter.

    Optimizations:
    1. Score pre-filter: docs with search score < threshold skip LLM grading.
    2. Parallel grading: remaining docs graded concurrently via asyncio.gather.

    Args:
        state: Current RAG state with search_response
        llm: LLM instance for grading
        settings: SelfRAGSettings configuration

    Returns:
        Updated state with graded_documents and relevance_ratio
    """
    search_response = state.get("search_response")
    question = state.get("original_question") or state.get("question", "")

    if not search_response or not search_response.results:
        logger.warning("[GRADE] No search results to grade")
        return {"graded_documents": [], "relevance_ratio": 0.0}

    score_threshold = settings.score_prefilter_threshold
    results = search_response.results

    # Split: candidates for LLM grading vs auto-rejected by score
    to_grade = []
    auto_rejected = []
    for result in results:
        if result.score >= score_threshold:
            to_grade.append(result)
        else:
            auto_rejected.append(result)

    if auto_rejected:
        logger.info(
            f"[GRADE] Pre-filter: {len(auto_rejected)} docs skipped "
            f"(score < {score_threshold}), {len(to_grade)} sent to LLM"
        )

    # Grade one document via LLM (Ralph Wiggum: 1 retry for structured yes/no)
    async def _grade_one(result) -> dict:
        content = result.chunk.content
        content_preview = content[:500] + "..." if len(content) > 500 else content
        prompt = _get_grading_prompt(question, content_preview)
        base_messages = [
            SystemMessage(content=prompt["system"]),
            HumanMessage(content=prompt["user"]),
        ]

        feedback = ""
        for attempt in range(1, 3):  # max 2 attempts
            try:
                messages = list(base_messages)
                if feedback:
                    messages.append(HumanMessage(content=f"\u26a0\ufe0f {feedback}"))

                response = await llm.ainvoke(messages)
                result_text = _parser.invoke(response).strip().lower()

                # Validate: starts with yes/no/да/нет?
                valid = any(result_text.startswith(w) for w in ["yes", "no", "да", "нет", "relevant", "not"])
                if not valid and attempt < 2:
                    feedback = f"Reply ONLY 'yes' or 'no'. Previous: '{result_text[:60]}'"
                    logger.warning(f"[GRADE] Attempt {attempt}: unclear '{result_text[:40]}' for {result.chunk.id[:12]}")
                    continue

                is_relevant = _parse_relevance(result_text)
                return {
                    "chunk_id": result.chunk.id,
                    "is_relevant": is_relevant,
                    "reason": result_text[:200],
                    "score": result.score,
                    "content_preview": content_preview[:100],
                }
            except Exception as e:
                logger.error(f"[GRADE] Attempt {attempt} error for {result.chunk.id[:12]}: {e}")
                feedback = f"Previous call failed: {e}."

        # All attempts failed — conservative fallback
        return {
            "chunk_id": result.chunk.id,
            "is_relevant": True,
            "reason": "All grading attempts failed",
            "score": result.score,
            "content_preview": content_preview[:100],
        }

    # Run all LLM grading calls concurrently
    if to_grade:
        graded = list(await asyncio.gather(*[_grade_one(r) for r in to_grade]))
    else:
        graded = []

    # Append auto-rejected docs (no LLM call needed)
    for result in auto_rejected:
        graded.append({
            "chunk_id": result.chunk.id,
            "is_relevant": False,
            "reason": f"auto-rejected: score {result.score:.3f} < {score_threshold}",
            "score": result.score,
            "content_preview": result.chunk.content[:100],
        })

    relevant_count = sum(1 for g in graded if g["is_relevant"])
    ratio = relevant_count / len(graded) if graded else 0.0

    logger.info(
        f"[GRADE] {relevant_count}/{len(graded)} relevant "
        f"(LLM-graded: {len(to_grade)}, pre-filtered: {len(auto_rejected)})"
    )

    return {"graded_documents": graded, "relevance_ratio": ratio}


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
    positive_words = ["yes", "relevant", "да"]
    negative_words = ["no", "not relevant", "unrelated", "нет"]

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
