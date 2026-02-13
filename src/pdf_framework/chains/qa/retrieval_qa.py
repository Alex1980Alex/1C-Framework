"""Retrieval QA chain: answer questions using retrieved document context."""

import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from src.pdf_framework.config import AgentSettings
from src.pdf_framework.schemas.documents import SearchResponse

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "Всегда отвечай на русском языке.\n\n"
    "Ты — справочная система по документации 1С:Предприятие 8. "
    "К тебе обращается разработчик, который столкнулся с технологией платформы "
    "и хочет свериться с документацией прежде чем внедрять. "
    "Твоя задача — дать ему точную выписку из стандартов: что это, "
    "как работает по документации, и как правильно применить.\n\n"
    "ФОРМАТ ОТВЕТА:\n"
    "1. **Что это и зачем** — определение механизма и задача, которую он решает.\n"
    "2. **Как работает по документации** — точный механизм: шаги, логика, "
    "правила платформы. Со ссылками на конкретные пункты §X.Y.Z.\n"
    "3. **Возможности и ограничения** — что позволяет, что запрещено, "
    "граничные условия (с примерами имен, значений, параметров).\n"
    "4. **Связанные механизмы** — с какими другими технологиями платформы "
    "работает в связке, на что влияет.\n"
    "5. **Как применить** — пошаговая инструкция для разработчика: "
    "что создать в конфигураторе, какой код написать на встроенном языке. "
    "Если в документации есть примеры кода — ОБЯЗАТЕЛЬНО приведи их (в блоке ```). "
    "Разработчик должен уйти с готовым рецептом.\n"
    "6. **Ссылки** — разделы документации (§X.Y.Z) для самостоятельного изучения.\n\n"
    "ПРИНЦИПЫ:\n"
    "- Ты даешь ФАКТЫ ИЗ ДОКУМЕНТАЦИИ, а не свое мнение.\n"
    "- Каждое утверждение подкрепляй ссылкой [1], [2] и §номером раздела.\n"
    "- Код из документации ценнее любых описаний — всегда включай его.\n"
    "- Пиши плотно, без воды. Не пиши «давайте разберемся» и т.п.\n"
    "- Если в документации чего-то нет — скажи прямо.\n"
    "- Используй ТОЛЬКО информацию из контекста ниже.\n\n"
    "Контекст:\n{context}"
)


class RetrievalQAChain:
    """Generate LLM answers grounded in retrieved document chunks."""

    def __init__(self, settings: AgentSettings | None = None, api_key: str = ""):
        self._settings = settings or AgentSettings()

        # Configure ChatAnthropic with optional base_url for proxies like Z.AI
        llm_kwargs = {
            "model": self._settings.model,
            "temperature": self._settings.temperature,
            "max_tokens": self._settings.max_tokens,
            "api_key": api_key or None,
        }

        # Add base_url if configured (for Z.AI or other proxies)
        if self._settings.base_url:
            llm_kwargs["base_url"] = self._settings.base_url

        self._llm = ChatAnthropic(**llm_kwargs)
        self._parser = StrOutputParser()

    async def answer(
        self,
        question: str,
        search_response: SearchResponse,
        *,
        search_manager: Any = None,
        fast_llm: ChatAnthropic | None = None,
    ) -> str:
        """Generate an answer using retrieved context.

        If search_manager and fast_llm are provided, runs the Phase 42
        Answer Enrichment Loop: checks completeness → generates sub-queries
        → enriches context → regenerates answer.
        """
        context = self._build_context(search_response)

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT.format(context=context)),
            HumanMessage(content=question),
        ]

        response = await self._llm.ainvoke(messages)
        answer_text = self._parser.invoke(response)

        # Phase 42: Answer Enrichment Loop
        if search_manager and fast_llm:
            try:
                from src.pdf_framework.chains.qa.enrichment import (
                    check_completeness,
                    enrich_search_results,
                    generate_sub_queries,
                )

                check = await check_completeness(question, answer_text, fast_llm)
                if not check["is_complete"]:
                    sub_queries = await generate_sub_queries(
                        question, check["gaps"], fast_llm,
                    )
                    enriched = await enrich_search_results(
                        search_response.results, sub_queries, search_manager,
                    )
                    # Regenerate with enriched context
                    enriched_context = self._build_context(enriched)
                    enriched_messages = [
                        SystemMessage(content=_SYSTEM_PROMPT.format(context=enriched_context)),
                        HumanMessage(content=question),
                    ]
                    enriched_response = await self._llm.ainvoke(enriched_messages)
                    answer_text = self._parser.invoke(enriched_response)
                    search_response = enriched  # for section refs below
                    logger.info(
                        "[ENRICHMENT] Regenerated with %d chunks (was %d)",
                        enriched.total_found, len(search_response.results),
                    )
            except Exception:
                logger.exception("[ENRICHMENT] Enrichment loop failed, using initial answer")

        # Phase 41: Guaranteed section reference block
        from src.pdf_framework.utils.section_refs import append_section_refs
        return append_section_refs(answer_text, search_response.results)

    async def stream_answer(
        self, question: str, search_response: SearchResponse
    ) -> AsyncIterator[str]:
        """Stream answer tokens via ChatAnthropic.astream()."""
        context = self._build_context(search_response)

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT.format(context=context)),
            HumanMessage(content=question),
        ]

        async for chunk in self._llm.astream(messages):
            content = chunk.content
            # Handle both str and list[ContentBlock]
            if isinstance(content, list):
                content = "".join(
                    getattr(block, "text", "") for block in content
                )
            if content:
                yield content

    @staticmethod
    def _build_context(search_response: SearchResponse) -> str:
        """Build a context string from search results.

        Phase 41: Each chunk starts with §section_number for LLM to reference.
        """
        import re

        parts: list[str] = []
        for i, result in enumerate(search_response.results, 1):
            source = result.chunk.metadata.get("source", "unknown")
            page = result.chunk.metadata.get("page", "")
            page_str = f", стр. {page}" if page else ""

            # Phase 41: extract section number
            section_title = result.chunk.metadata.get("section_title", "")
            breadcrumb = result.chunk.metadata.get("breadcrumb", "")
            sec_raw = section_title or breadcrumb
            sec_clean = sec_raw.replace("*", "").strip()
            sec_match = re.match(r"(\d+(?:\.\d+)*)", sec_clean)
            sec_num = sec_match.group(1) if sec_match else ""

            if sec_num:
                header = f"[{i}] (§{sec_num} «{sec_clean}»{page_str}, score: {result.score:.3f})"
            else:
                header = f"[{i}] (source: {source}{page_str}, score: {result.score:.3f})"

            bc_line = f"\nРаздел: {breadcrumb}" if breadcrumb else ""
            parts.append(f"{header}{bc_line}\n{result.chunk.content}")
        return "\n\n---\n\n".join(parts) if parts else "No relevant context found."
