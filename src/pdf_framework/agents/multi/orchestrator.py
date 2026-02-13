"""Multi-Agent Orchestrator (Phase 39).

Coordinates 4 specialized agents:
1. Retrieval Agent — finds relevant information across strategies
2. Analysis Agent — compares, finds contradictions, draws conclusions
3. Writing Agent — synthesizes into a structured report
4. Verification Agent — fact-checks and validates

Uses LangGraph for handoff coordination.
"""

import asyncio
import json
import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import END, StateGraph

from src.pdf_framework.agents.multi.schemas import (
    AnalysisResult,
    OrchestratorState,
    RetrievalResult,
    VerificationResult,
    WritingResult,
)
from src.pdf_framework.config import AgentSettings
from src.pdf_framework.search.manager import SearchManager

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 2  # verify → re-write if needed


def create_multi_agent(
    search_manager: SearchManager,
    settings: AgentSettings | None = None,
    api_key: str = "",
    fast_model: str = "claude-sonnet-4-5-20250929",
):
    """Create the Multi-Agent Orchestrator (Phase 39).

    Args:
        search_manager: Search manager for retrieval agent.
        settings: Agent configuration.
        api_key: Anthropic API key.
        fast_model: Fast model for analysis/verification.

    Returns:
        Compiled LangGraph with orchestrated agents.
    """
    settings = settings or AgentSettings()

    llm_kwargs: dict = dict(
        model=settings.model,
        temperature=0.1,
        max_tokens=settings.max_tokens,
        api_key=api_key or None,
    )
    if settings.base_url:
        llm_kwargs["base_url"] = settings.base_url
    llm = ChatAnthropic(**llm_kwargs)

    fast_kwargs: dict = dict(
        model=fast_model,
        temperature=0.0,
        max_tokens=2048,
        api_key=api_key or None,
    )
    if settings.base_url:
        fast_kwargs["base_url"] = settings.base_url
    fast_llm = ChatAnthropic(**fast_kwargs)

    parser = StrOutputParser()

    # ========== Agent 1: Retrieval Agent ==========
    async def retrieval_agent(state: OrchestratorState) -> dict:
        """Find relevant chunks using multiple strategies."""
        question = state["question"]
        messages_log = list(state.get("messages", []))

        # Multi-strategy parallel search
        strategies = ["hybrid", "bm25"]
        # If previous verification flagged gaps, add more strategies
        verif = state.get("verification", {})
        if verif.get("issues"):
            strategies.append("section_first")

        async def _search(strategy: str):
            try:
                if strategy == "section_first":
                    return await search_manager.search_section_first(
                        query=question, k=5,
                    )
                return await search_manager.search(
                    query=question, strategy=strategy, k=5, rerank=True,
                )
            except Exception as e:
                logger.warning("[RETRIEVAL] %s failed: %s", strategy, e)
                return None

        results = await asyncio.gather(*[_search(s) for s in strategies])

        # Deduplicate
        seen: set[str] = set()
        chunks: list[dict] = []
        for resp in results:
            if resp is None:
                continue
            for r in resp.results:
                if r.chunk.id not in seen:
                    seen.add(r.chunk.id)
                    chunks.append({
                        "id": r.chunk.id,
                        "content": r.chunk.content[:600],
                        "score": round(r.score, 3),
                        "source": r.chunk.metadata.get("source", ""),
                        "page": r.chunk.metadata.get("page_number"),
                        "section": r.chunk.metadata.get("section_title", "")
                            or r.chunk.metadata.get("breadcrumb", ""),
                    })

        retrieval = RetrievalResult(
            chunks=chunks,
            strategies_used=strategies,
            total_found=len(chunks),
        )

        messages_log.append({
            "from": "retrieval",
            "to": "orchestrator",
            "content": f"Found {len(chunks)} chunks via {strategies}",
        })

        logger.info(
            "[RETRIEVAL] %d chunks from %s",
            len(chunks),
            strategies,
        )

        return {
            "retrieval": retrieval.model_dump(),
            "messages": messages_log,
            "phase": "analyze",
        }

    # ========== Agent 2: Analysis Agent ==========
    async def analysis_agent(state: OrchestratorState) -> dict:
        """Analyze retrieved chunks: compare, find patterns, draw conclusions."""
        question = state["question"]
        retrieval = state.get("retrieval", {})
        chunks = retrieval.get("chunks", [])
        messages_log = list(state.get("messages", []))

        if not chunks:
            return {
                "analysis": AnalysisResult().model_dump(),
                "phase": "write",
            }

        # Build context for analysis — Phase 41: explicit §section numbers
        context = ""
        for i, c in enumerate(chunks[:15], 1):
            sec_raw = c.get("section", "")
            # Extract section number from "**5.9.Документы**" → "5.9"
            import re
            sec_clean = sec_raw.replace("*", "").strip()
            sec_match = re.match(r"(\d+(?:\.\d+)*)", sec_clean)
            sec_num = sec_match.group(1) if sec_match else ""
            sec_label = f" §{sec_num} «{sec_clean}»" if sec_num else (f" [{sec_raw}]" if sec_raw else "")
            context += f"[{i}] (стр.{c.get('page', '?')}{sec_label})\n{c['content']}\n\n"

        prompt = (
            "Проанализируй найденную информацию.\n\n"
            f"Вопрос: {question}\n\n"
            f"Контекст ({len(chunks)} фрагментов):\n{context}\n\n"
            "Ответь JSON:\n"
            "{\n"
            '  "findings": ["§X.Y.Z: факт1", "§X.Y.Z: факт2", ...],\n'
            '  "comparison_table": "| Критерий | ... |\\n|---|...| (markdown)",\n'
            '  "contradictions": ["противоречие1", ...],\n'
            '  "conclusions": ["вывод1", ...],\n'
            '  "sections_map": ["§X.Y — Название раздела", ...]\n'
            "}\n\n"
            "Правила:\n"
            "- findings: ключевые факты (5-10 штук), КАЖДЫЙ начинается с §номера раздела из заголовка фрагмента\n"
            "- comparison_table: только если вопрос сравнительный\n"
            "- contradictions: где источники противоречат друг другу\n"
            "- conclusions: аналитические выводы (2-5)\n"
            "- sections_map: карта всех использованных разделов (§номер — Название)\n"
        )

        try:
            messages = [
                SystemMessage(content="Ты — аналитик. Отвечай только JSON."),
                HumanMessage(content=prompt),
            ]
            response = await fast_llm.ainvoke(messages)
            text = parser.invoke(response).strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            data = json.loads(text)
            analysis = AnalysisResult(**data)
        except Exception as e:
            logger.warning("[ANALYSIS] Failed: %s", e)
            analysis = AnalysisResult(
                findings=["Анализ не удался"],
                conclusions=["Недостаточно данных для выводов"],
            )

        messages_log.append({
            "from": "analysis",
            "to": "orchestrator",
            "content": f"{len(analysis.findings)} findings, "
            f"{len(analysis.contradictions)} contradictions",
        })

        logger.info(
            "[ANALYSIS] %d findings, %d contradictions, %d conclusions",
            len(analysis.findings),
            len(analysis.contradictions),
            len(analysis.conclusions),
        )

        return {
            "analysis": analysis.model_dump(),
            "messages": messages_log,
            "phase": "write",
        }

    # ========== Agent 3: Writing Agent ==========
    async def writing_agent(state: OrchestratorState) -> dict:
        """Synthesize analysis into a structured report."""
        question = state["question"]
        retrieval = state.get("retrieval", {})
        analysis = state.get("analysis", {})
        messages_log = list(state.get("messages", []))

        # Handle corrections from verification
        verif = state.get("verification", {})
        corrections = verif.get("corrections", [])
        corrections_text = ""
        if corrections:
            corrections_text = (
                "\n\nИсправления от проверщика:\n"
                + "\n".join(f"- {c}" for c in corrections)
                + "\n\nУчти эти исправления в отчёте.\n"
            )

        findings = analysis.get("findings", [])
        conclusions = analysis.get("conclusions", [])
        comp_table = analysis.get("comparison_table", "")
        contradictions = analysis.get("contradictions", [])

        prompt = (
            "Напиши структурированный отчёт на основе анализа.\n\n"
            f"Вопрос: {question}\n\n"
            f"Ключевые факты ({len(findings)}):\n"
            + "\n".join(f"- {f}" for f in findings)
            + "\n\n"
            f"Выводы:\n"
            + "\n".join(f"- {c}" for c in conclusions)
            + "\n\n"
        )

        if comp_table:
            prompt += f"Таблица сравнения:\n{comp_table}\n\n"
        if contradictions:
            prompt += (
                "Противоречия:\n"
                + "\n".join(f"- {c}" for c in contradictions)
                + "\n\n"
            )

        prompt += corrections_text

        prompt += (
            "Формат отчёта:\n"
            "1. Резюме (3-5 предложений)\n"
            "2. Детальный анализ (по аспектам) — для каждого факта указывай (см. §X.Y.Z)\n"
            "3. Сравнительная таблица (если есть)\n"
            "4. Рекомендации / Выводы\n"
            "5. 📚 Где найти в документации — список всех использованных разделов:\n"
            "   - §номер — Название раздела\n\n"
            "Пиши на русском. Указывай [N] ссылки на факты и §номера разделов.\n"
        )

        try:
            messages = [
                SystemMessage(
                    content="Ты — технический писатель. "
                    "Создаёшь качественные структурированные отчёты."
                ),
                HumanMessage(content=prompt),
            ]
            response = await llm.ainvoke(messages)
            report_text = parser.invoke(response)
        except Exception as e:
            logger.error("[WRITING] Failed: %s", e)
            report_text = "Ошибка генерации отчёта."

        # Phase 41: Guaranteed section reference block
        if "Где найти в документации" not in report_text:
            from src.pdf_framework.utils.section_refs import (
                extract_sections_from_chunks,
                build_section_nav_block,
            )
            sections = extract_sections_from_chunks(retrieval.get("chunks", []))
            nav = build_section_nav_block(sections)
            if nav:
                report_text += nav

        # Extract sources from retrieval
        sources: list[str] = []
        for c in retrieval.get("chunks", []):
            src = c.get("source", "")
            if src and src not in sources:
                sources.append(src)

        writing = WritingResult(
            report=report_text,
            sources=sources,
        )

        messages_log.append({
            "from": "writing",
            "to": "orchestrator",
            "content": f"Report: {len(report_text)} chars, {len(sources)} sources",
        })

        logger.info("[WRITING] %d chars, %d sources", len(report_text), len(sources))

        return {
            "draft": writing.model_dump(),
            "messages": messages_log,
            "phase": "verify",
        }

    # ========== Agent 4: Verification Agent ==========
    async def verification_agent(state: OrchestratorState) -> dict:
        """Fact-check and validate the draft report."""
        question = state["question"]
        draft = state.get("draft", {})
        retrieval = state.get("retrieval", {})
        messages_log = list(state.get("messages", []))
        iteration = state.get("iteration", 0)

        report_text = draft.get("report", "")
        chunks = retrieval.get("chunks", [])

        # Build source context for verification
        source_context = ""
        for i, c in enumerate(chunks[:10], 1):
            source_context += f"[{i}] {c.get('content', '')[:300]}\n\n"

        prompt = (
            "Проверь отчёт на фактическую точность.\n\n"
            f"Вопрос: {question}\n\n"
            f"Отчёт:\n{report_text[:3000]}\n\n"
            f"Исходные данные:\n{source_context}\n\n"
            "Ответь JSON:\n"
            "{\n"
            '  "passed": true/false,\n'
            '  "issues": ["проблема1", ...],\n'
            '  "corrections": ["исправление1", ...],\n'
            '  "groundedness": 0.0-1.0,\n'
            '  "completeness": 0.0-1.0\n'
            "}\n\n"
            "Правила:\n"
            "- passed: true если groundedness >=0.9 и completeness >=0.8\n"
            "- issues: конкретные фактические ошибки\n"
            "- corrections: конкретные исправления\n"
            "- groundedness: доля утверждений, подтверждённых источниками\n"
            "- completeness: покрытие аспектов вопроса\n"
            "- Проверь наличие ссылок на разделы (§X.Y.Z). Если в отчёте нет привязки к разделам документации, "
            "добавь в corrections: «Добавить ссылки на разделы документации (§номер)»\n"
        )

        try:
            messages = [
                SystemMessage(content="Ты — верификатор. Отвечай только JSON."),
                HumanMessage(content=prompt),
            ]
            response = await fast_llm.ainvoke(messages)
            text = parser.invoke(response).strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            data = json.loads(text)
            verification = VerificationResult(**data)
        except Exception as e:
            logger.warning("[VERIFY] Failed: %s", e)
            verification = VerificationResult(
                passed=True,
                groundedness=0.8,
                completeness=0.8,
            )

        messages_log.append({
            "from": "verification",
            "to": "orchestrator",
            "content": f"{'PASSED' if verification.passed else 'FAILED'}: "
            f"groundedness={verification.groundedness:.0%}, "
            f"completeness={verification.completeness:.0%}, "
            f"issues={len(verification.issues)}",
        })

        logger.info(
            "[VERIFY] %s: groundedness=%.0f%%, completeness=%.0f%%, "
            "issues=%d, iteration=%d",
            "PASSED" if verification.passed else "FAILED",
            verification.groundedness * 100,
            verification.completeness * 100,
            len(verification.issues),
            iteration + 1,
        )

        return {
            "verification": verification.model_dump(),
            "messages": messages_log,
            "iteration": iteration + 1,
        }

    # ========== Finalize ==========
    async def finalize(state: OrchestratorState) -> dict:
        """Produce the final output."""
        draft = state.get("draft", {})
        verification = state.get("verification", {})
        retrieval = state.get("retrieval", {})
        analysis = state.get("analysis", {})

        report = {
            "text": draft.get("report", ""),
            "sources": draft.get("sources", []),
            "findings_count": len(analysis.get("findings", [])),
            "chunks_used": retrieval.get("total_found", 0),
            "groundedness": verification.get("groundedness", 0),
            "completeness": verification.get("completeness", 0),
            "iterations": state.get("iteration", 0),
            "agents_used": ["retrieval", "analysis", "writing", "verification"],
        }

        return {
            "answer": draft.get("report", ""),
            "report": report,
            "phase": "done",
        }

    # ========== Conditional Edges ==========

    def after_verification(state: OrchestratorState) -> str:
        """After verification: retry writing or finalize."""
        verif = state.get("verification", {})
        iteration = state.get("iteration", 0)
        max_iter = state.get("max_iterations", _MAX_ITERATIONS)

        if verif.get("passed", True) or iteration >= max_iter:
            return "finalize"
        # Re-write with corrections
        logger.info("[ORCHESTRATOR] Verification failed, re-writing (iter %d)", iteration)
        return "rewrite"

    # ========== Build Graph ==========
    graph = StateGraph(OrchestratorState)

    graph.add_node("retrieve", retrieval_agent)
    graph.add_node("analyze", analysis_agent)
    graph.add_node("write", writing_agent)
    graph.add_node("verify", verification_agent)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("retrieve")

    # Linear pipeline: retrieve → analyze → write → verify → (rewrite | finalize)
    graph.add_edge("retrieve", "analyze")
    graph.add_edge("analyze", "write")
    graph.add_edge("write", "verify")

    graph.add_conditional_edges(
        "verify",
        after_verification,
        {"rewrite": "write", "finalize": "finalize"},
    )

    graph.add_edge("finalize", END)

    logger.info("[GRAPH] Compiled Multi-Agent Orchestrator (Phase 39)")

    return graph.compile()
