"""Answer Enrichment Loop: detect thin answers and enrich context via sub-queries.

Phase 42: FAIR-RAG inspired iterative refinement with Ralph Wiggum self-correction.
Flow: generate answer → check completeness → generate sub-queries → enrich → regenerate.
"""

import asyncio
import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.pdf_framework.schemas.documents import SearchResponse, SearchResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Completeness checker
# ---------------------------------------------------------------------------

_COMPLETENESS_SYSTEM = (
    "Ты — оценщик полноты ответа. "
    "Тебе дают вопрос пользователя и сгенерированный ответ.\n\n"
    "Оцени, достаточно ли подробно ответ раскрывает тему.\n"
    "Ответ считается НЕПОЛНЫМ, если:\n"
    "- Упоминаются подразделы/подглавы, но их содержимое не раскрыто\n"
    "- Даны только общие фразы без конкретики (имена, значения, шаги)\n"
    "- Отсутствуют примеры кода, хотя тема подразумевает их\n"
    "- Описаны менее 3 аспектов механизма\n\n"
    "Формат ответа — СТРОГО одна строка:\n"
    "COMPLETE — если ответ достаточно полный\n"
    "INCOMPLETE: аспект1; аспект2; аспект3 — если есть пробелы\n\n"
    "Примеры:\n"
    "COMPLETE\n"
    "INCOMPLETE: не раскрыта структура пакета; нет примера кода; "
    "не описаны ограничения\n"
)


async def check_completeness(
    question: str,
    answer: str,
    fast_llm: ChatAnthropic,
) -> dict[str, Any]:
    """Check if the answer is complete or thin.

    Returns {"is_complete": bool, "gaps": list[str]}.
    Uses Ralph Wiggum pattern: 2 attempts with feedback.
    """
    feedback = ""

    for attempt in range(1, 3):
        prompt = (
            f"Вопрос пользователя: {question}\n\n"
            f"Сгенерированный ответ:\n{answer}"
        )
        if feedback:
            prompt += f"\n\n⚠️ КОРРЕКЦИЯ: {feedback}"

        messages = [
            SystemMessage(content=_COMPLETENESS_SYSTEM),
            HumanMessage(content=prompt),
        ]

        try:
            response = await fast_llm.ainvoke(messages)
            text = response.content
            if isinstance(text, list):
                text = "".join(getattr(b, "text", "") for b in text)
            text = text.strip()

            # Parse response
            if text.upper().startswith("COMPLETE"):
                logger.info("[ENRICHMENT] Answer is COMPLETE")
                return {"is_complete": True, "gaps": []}

            if "INCOMPLETE" in text.upper():
                # Extract gaps after "INCOMPLETE:"
                parts = text.split(":", 1)
                gaps_raw = parts[1].strip() if len(parts) > 1 else ""
                gaps = [g.strip() for g in gaps_raw.split(";") if g.strip()]

                if gaps:
                    logger.info(
                        "[ENRICHMENT] Answer INCOMPLETE, %d gaps: %s",
                        len(gaps), "; ".join(gaps),
                    )
                    return {"is_complete": False, "gaps": gaps}

                feedback = (
                    "Ответ в формате INCOMPLETE, но не указаны конкретные пробелы. "
                    "Укажи пробелы через точку с запятой после INCOMPLETE:"
                )
                continue

            # Invalid format
            feedback = (
                "Ответь СТРОГО в формате: COMPLETE или "
                "INCOMPLETE: пробел1; пробел2; пробел3"
            )

        except Exception:
            logger.exception("[ENRICHMENT] Completeness check failed (attempt %d)", attempt)
            feedback = "Произошла ошибка. Попробуй снова в правильном формате."

    # Fallback: assume complete (don't waste resources on retry)
    logger.warning("[ENRICHMENT] Completeness check fallback → COMPLETE")
    return {"is_complete": True, "gaps": []}


# ---------------------------------------------------------------------------
# 2. Sub-query generator
# ---------------------------------------------------------------------------

_SUBQUERY_SYSTEM = (
    "Ты — генератор поисковых запросов для базы знаний по документации 1С.\n"
    "Тебе дают исходный вопрос и список пробелов в ответе.\n\n"
    "Сгенерируй 2-3 КОРОТКИХ поисковых запроса, чтобы найти недостающую информацию.\n"
    "Каждый запрос на отдельной строке, без нумерации и маркеров.\n"
    "Запросы должны быть конкретными и отличаться друг от друга.\n\n"
    "Пример:\n"
    "добавление WS-ссылки URL WSDL\n"
    "иерархическая структура WS-ссылки модель данных\n"
    "операции точки подключения Web-сервис\n"
)


async def generate_sub_queries(
    question: str,
    gaps: list[str],
    fast_llm: ChatAnthropic,
    max_queries: int = 3,
) -> list[str]:
    """Generate targeted sub-queries to fill gaps in the answer.

    Returns list of 2-3 search queries.
    Uses Ralph Wiggum pattern: 2 attempts with feedback.
    """
    gaps_text = "; ".join(gaps)
    feedback = ""

    for attempt in range(1, 3):
        prompt = (
            f"Исходный вопрос: {question}\n"
            f"Пробелы в ответе: {gaps_text}"
        )
        if feedback:
            prompt += f"\n\n⚠️ КОРРЕКЦИЯ: {feedback}"

        messages = [
            SystemMessage(content=_SUBQUERY_SYSTEM),
            HumanMessage(content=prompt),
        ]

        try:
            response = await fast_llm.ainvoke(messages)
            text = response.content
            if isinstance(text, list):
                text = "".join(getattr(b, "text", "") for b in text)

            # Parse: one query per line
            queries = []
            for line in text.strip().split("\n"):
                q = line.strip().lstrip("0123456789.-) ").strip()
                if q and len(q) >= 5 and q.lower() != question.lower():
                    queries.append(q)

            if queries:
                queries = queries[:max_queries]
                logger.info(
                    "[ENRICHMENT] Generated %d sub-queries: %s",
                    len(queries), queries,
                )
                return queries

            feedback = (
                "Верни 2-3 поисковых запроса, каждый на отдельной строке. "
                "Без нумерации, без маркеров, просто текст запроса."
            )

        except Exception:
            logger.exception("[ENRICHMENT] Sub-query generation failed (attempt %d)", attempt)
            feedback = "Произошла ошибка. Попробуй снова."

    # Fallback: use question + gap keywords
    fallback = [f"{question} {gap}" for gap in gaps[:max_queries]]
    logger.warning("[ENRICHMENT] Sub-query fallback: %s", fallback)
    return fallback


# ---------------------------------------------------------------------------
# 3. Enrichment search
# ---------------------------------------------------------------------------


async def enrich_search_results(
    original_results: list[SearchResult],
    sub_queries: list[str],
    search_manager: Any,
    k_per_query: int = 5,
) -> SearchResponse:
    """Run additional searches and merge with original results.

    Deduplicates by chunk.id. Original results keep their position priority.
    Returns a combined SearchResponse.
    """
    # Collect existing chunk IDs
    seen_ids: set[str] = set()
    merged: list[SearchResult] = []

    for r in original_results:
        seen_ids.add(r.chunk.id)
        merged.append(r)

    # Run sub-queries in parallel
    async def _search_one(query: str) -> list[SearchResult]:
        try:
            resp = await search_manager.search(
                query=query,
                strategy="hybrid",
                k=k_per_query,
                rerank=False,
            )
            return resp.results
        except Exception:
            logger.exception("[ENRICHMENT] Sub-query search failed: %s", query)
            return []

    all_new = await asyncio.gather(*[_search_one(q) for q in sub_queries])

    new_count = 0
    for results in all_new:
        for r in results:
            if r.chunk.id not in seen_ids:
                seen_ids.add(r.chunk.id)
                merged.append(r)
                new_count += 1

    logger.info(
        "[ENRICHMENT] Merged: %d original + %d new = %d total",
        len(original_results), new_count, len(merged),
    )

    return SearchResponse(
        query=original_results[0].chunk.metadata.get("query", "") if original_results else "",
        results=merged,
        total_found=len(merged),
        search_type="enriched",
    )
