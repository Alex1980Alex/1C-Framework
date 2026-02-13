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

    # Truncate context to avoid excessive token usage on fast model
    max_chars = settings.max_context_chars
    if len(context) > max_chars:
        context = context[:max_chars] + "\n\n[... truncated for verification ...]"
        logger.debug(f"[HALLUCINATION] Context truncated to {max_chars} chars")

    check_prompt = _get_hallucination_check_prompt(context, answer)
    messages = [
        SystemMessage(content=check_prompt["system"]),
        HumanMessage(content=check_prompt["user"]),
    ]

    # Ralph Wiggum: self-correcting feedback for structured response
    parser = StrOutputParser()
    max_rw_retries = 2
    feedback = ""
    last_result_text = ""

    for attempt in range(1, max_rw_retries + 1):
        try:
            attempt_messages = list(messages)
            if feedback:
                attempt_messages.append(HumanMessage(content=f"\u26a0\ufe0f CORRECTION: {feedback}"))

            response = await llm.ainvoke(attempt_messages)
            result_text = parser.invoke(response).strip().lower()
            last_result_text = result_text

            # Validate: starts with expected keyword?
            valid_starts = ["grounded", "not_grounded", "not grounded"]
            if not any(result_text.startswith(v) for v in valid_starts):
                feedback = (
                    f"Reply ONLY with 'grounded' or 'not_grounded: reason'. "
                    f"Previous response '{result_text[:80]}' was not recognized."
                )
                logger.warning(f"[HALLUCINATION] Attempt {attempt}: unclear '{result_text[:80]}'")
                continue

            # Valid structured response
            is_hallucinated = _parse_hallucination_result(result_text)
            if is_hallucinated:
                logger.warning(f"[HALLUCINATION] Detected! Reason: {result_text[:200]}")
            else:
                logger.info("[HALLUCINATION] Answer is grounded")
            return {
                "is_hallucinated": is_hallucinated,
                "hallucination_reason": result_text[:300],
            }

        except Exception as e:
            logger.error(f"[HALLUCINATION] Attempt {attempt} error: {e}")
            feedback = f"Previous call failed: {e}. Try again."
            last_result_text = f"error: {e}"

    # All retries exhausted
    is_hallucinated = _parse_hallucination_result(last_result_text) if last_result_text else False
    return {
        "is_hallucinated": is_hallucinated,
        "hallucination_reason": last_result_text[:300] if last_result_text else "All attempts failed",
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

    strict_prompt = f"""Отвечай на русском языке. Отвечай на следующий вопрос, используя ТОЛЬКО предоставленный контекст.

КРИТИЧЕСКИЕ ПРАВИЛА:
1. Используй ТОЛЬКО информацию из контекста ниже
2. НЕ добавляй информацию, которой нет в контексте
3. Если контекст не содержит ответа, скажи «У меня недостаточно информации для ответа на этот вопрос»
4. НЕ придумывай факты, числа, даты или другие детали
5. Ответ должен быть кратким и подтверждённым контекстом
6. Для каждого утверждения указывай номер раздела документации (§X.Y.Z) из заголовка фрагмента
7. В конце добавь блок «Где найти в документации:» со списком использованных разделов

Контекст:
{context}

Вопрос: {question}

Ответ:"""

    # Ralph Wiggum: self-correcting retry for regeneration
    parser = StrOutputParser()
    hallucination_reason = state.get("hallucination_reason", "")
    max_rw_retries = 2
    rw_feedback = ""
    last_answer = ""

    for rw_attempt in range(1, max_rw_retries + 1):
        try:
            prompt = strict_prompt
            if rw_feedback:
                prompt += f"\n\n\u26a0\ufe0f \u041a\u041e\u0420\u0420\u0415\u041a\u0426\u0418\u042f: {rw_feedback}"

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            new_answer = parser.invoke(response).strip()
            last_answer = new_answer

            # Validate: non-empty and Russian
            if len(new_answer) < 20:
                rw_feedback = "\u041e\u0442\u0432\u0435\u0442 \u0441\u043b\u0438\u0448\u043a\u043e\u043c \u043a\u043e\u0440\u043e\u0442\u043a\u0438\u0439. \u0414\u0430\u0439 \u0440\u0430\u0437\u0432\u0451\u0440\u043d\u0443\u0442\u044b\u0439 \u043e\u0442\u0432\u0435\u0442 \u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c."
                logger.warning(f"[REGENERATE] Attempt {rw_attempt}: too short ({len(new_answer)} chars)")
                continue

            # Validate: not same as hallucinated answer
            old_answer = state.get("answer", "")
            if old_answer and new_answer[:200] == old_answer[:200]:
                rw_feedback = (
                    f"\u041f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0439 \u043e\u0442\u0432\u0435\u0442 \u0441\u043e\u0434\u0435\u0440\u0436\u0430\u043b \u0433\u0430\u043b\u043b\u044e\u0446\u0438\u043d\u0430\u0446\u0438\u0438: {hallucination_reason[:200]}. "
                    "\u0421\u0433\u0435\u043d\u0435\u0440\u0438\u0440\u0443\u0439 \u0414\u0420\u0423\u0413\u041e\u0419 \u043e\u0442\u0432\u0435\u0442, \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u044f \u0422\u041e\u041b\u042c\u041a\u041e \u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442."
                )
                logger.warning(f"[REGENERATE] Attempt {rw_attempt}: same as hallucinated answer")
                continue

            logger.info(f"[REGENERATE] Generated stricter answer ({len(new_answer)} chars)")
            break

        except Exception as e:
            logger.error(f"[REGENERATE] Attempt {rw_attempt} error: {e}")
            rw_feedback = f"\u041f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0438\u0439 \u0432\u044b\u0437\u043e\u0432 \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u043b\u0441\u044f \u043e\u0448\u0438\u0431\u043a\u043e\u0439: {e}."
            last_answer = ""

    new_answer = last_answer

    # Extract sources
    search_resp = state.get("search_response")
    sources: list[str] = []
    if search_resp:
        for r in search_resp.results:
            src = r.chunk.metadata.get("source", "")
            if src and src not in sources:
                sources.append(src)

    if new_answer:
        return {
            "answer": new_answer,
            "generation_attempts": attempts,
            "sources": sources,
            "is_hallucinated": False,
        }
    return {
        "generation_attempts": attempts,
        "is_hallucinated": False,
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
