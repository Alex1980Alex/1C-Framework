"""Analytical RAG Agent (Phase 33).

Think -> Act -> Observe -> Re-Think cycle.

Pipeline:
  plan -> retrieve -> collect_evidence -> (compare | analyze) ->
  check_coverage -> (retrieve_more | synthesize) -> format_output

Supports: factual, comparative, analytical, and overview questions.
Produces structured output with summary, analysis, comparison tables, and sources.
"""

import asyncio
import json
import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import END, StateGraph

from src.pdf_framework.agents.analytical.schemas import (
    AnalysisPlan,
    AnalyticalState,
    ComparisonRow,
    ComparisonTable,
    Evidence,
    StructuredAnswer,
)
from src.pdf_framework.config import AgentSettings
from src.pdf_framework.search.manager import SearchManager

logger = logging.getLogger(__name__)

_MAX_ROUNDS = 3
_COVERAGE_THRESHOLD = 0.7  # 70% of aspects must be covered to skip extra rounds


def create_analytical_agent(
    search_manager: SearchManager,
    settings: AgentSettings | None = None,
    api_key: str = "",
    fast_model: str = "claude-sonnet-4-5-20250929",
):
    """Create a LangGraph Analytical RAG agent.

    Phase 33: Evidence-gathering, comparative analysis engine.

    Args:
        search_manager: Search manager for multi-strategy retrieval.
        settings: Agent configuration.
        api_key: Anthropic API key.
        fast_model: Model for planning and evidence extraction (default: Sonnet).

    Returns:
        Compiled LangGraph ready for invocation.
    """
    settings = settings or AgentSettings()

    llm_kwargs = dict(
        model=settings.model,
        temperature=0.1,
        max_tokens=settings.max_tokens,
        api_key=api_key or None,
    )
    if settings.base_url:
        llm_kwargs["base_url"] = settings.base_url
    llm = ChatAnthropic(**llm_kwargs)

    fast_llm_kwargs = dict(
        model=fast_model,
        temperature=0.0,
        max_tokens=2048,
        api_key=api_key or None,
    )
    if settings.base_url:
        fast_llm_kwargs["base_url"] = settings.base_url
    fast_llm = ChatAnthropic(**fast_llm_kwargs)

    parser = StrOutputParser()

    # ========== Node 1: Plan ==========
    async def plan_analysis(state: AnalyticalState) -> dict:
        """Analyze the question and create a retrieval plan."""
        question = state["question"]

        prompt = (
            "Ты — аналитический планировщик RAG-системы.\n"
            "Проанализируй вопрос пользователя и создай план поиска.\n\n"
            "Ответь строго в JSON:\n"
            "{\n"
            '  "question_type": "factual|comparative|analytical|overview",\n'
            '  "aspects": ["аспект1", "аспект2", ...],\n'
            '  "search_queries": ["запрос1", "запрос2", ...],\n'
            '  "entities_to_compare": ["сущность1", "сущность2"]  // только для comparative\n'
            "}\n\n"
            "Правила:\n"
            "- comparative: вопрос сравнивает 2+ объекта (отличия, сравнение)\n"
            "- analytical: вопрос требует анализа причин, механизмов, взаимосвязей\n"
            "- overview: обзорный вопрос о теме (основные объекты, общее описание)\n"
            "- factual: простой вопрос с одним ответом\n"
            "- aspects: конкретные аспекты, которые нужно раскрыть (3-6 штук)\n"
            "- search_queries: поисковые запросы для каждого аспекта (2-5 штук)\n"
            "- entities_to_compare: объекты для сравнения (только если comparative)\n"
        )

        try:
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content=question),
            ]
            response = await fast_llm.ainvoke(messages)
            text = parser.invoke(response).strip()

            # Extract JSON from possible markdown code block
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            plan_data = json.loads(text)
            plan = AnalysisPlan(**plan_data)
        except Exception as e:
            logger.warning("[PLAN] LLM planning failed: %s, using defaults", e)
            plan = AnalysisPlan(
                question_type="factual",
                aspects=["основной ответ"],
                search_queries=[question],
            )

        logger.info(
            "[PLAN] type=%s, aspects=%d, queries=%d, entities=%s",
            plan.question_type, len(plan.aspects),
            len(plan.search_queries), plan.entities_to_compare or "none",
        )

        return {
            "plan": plan.model_dump(),
            "round": 0,
            "max_rounds": _MAX_ROUNDS,
            "evidence": [],
            "search_responses": [],
            "uncovered_aspects": list(plan.aspects),
        }

    # ========== Node 2: Multi-Source Retrieve ==========
    async def retrieve(state: AnalyticalState) -> dict:
        """Execute search queries from the plan (parallel, multi-strategy)."""
        plan = AnalysisPlan(**state["plan"])
        current_round = state.get("round", 0)
        uncovered = state.get("uncovered_aspects", [])

        # Determine queries for this round
        if current_round == 0:
            queries = plan.search_queries[:5]  # First round: all planned queries
        else:
            # Subsequent rounds: generate queries for uncovered aspects
            queries = [f"{aspect}" for aspect in uncovered[:3]]

        if not queries:
            queries = [state["question"]]

        # Execute searches in parallel across multiple strategies
        strategies = ["hybrid", "bm25"]
        if plan.question_type in ("comparative", "overview"):
            strategies.append("section_first")

        all_results = []

        async def _search_one(query: str, strategy: str):
            try:
                return await search_manager.search(
                    query=query, strategy=strategy, k=5, rerank=True,
                )
            except Exception as e:
                logger.warning("[RETRIEVE] %s/%s failed: %s", strategy, query[:30], e)
                return None

        tasks = [
            _search_one(q, s)
            for q in queries
            for s in strategies
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if r is not None and not isinstance(r, Exception):
                all_results.append(r)

        # Deduplicate chunks by ID
        seen_ids: set[str] = set()
        # Also consider evidence from prior rounds
        for ev in state.get("evidence", []):
            if ev.get("chunk_id"):
                seen_ids.add(ev["chunk_id"])

        unique_chunks = []
        for resp in all_results:
            for sr in resp.results:
                if sr.chunk.id not in seen_ids:
                    seen_ids.add(sr.chunk.id)
                    unique_chunks.append(sr)

        logger.info(
            "[RETRIEVE] Round %d: %d queries x %d strategies = %d unique chunks",
            current_round + 1, len(queries), len(strategies), len(unique_chunks),
        )

        # Store responses for evidence collection
        stored = state.get("search_responses", [])
        for resp in all_results:
            stored.append({
                "query": resp.query,
                "search_type": resp.search_type,
                "result_count": len(resp.results),
            })

        return {
            "search_responses": stored,
            "_current_chunks": [
                {
                    "id": sr.chunk.id,
                    "content": sr.chunk.content,
                    "score": sr.score,
                    "source": sr.chunk.metadata.get("source", ""),
                    "page": sr.chunk.metadata.get("page_number", ""),
                    "section": sr.chunk.metadata.get("section_title", "")
                        or sr.chunk.metadata.get("breadcrumb", ""),
                }
                for sr in unique_chunks
            ],
        }

    # ========== Node 3: Collect Evidence ==========
    async def collect_evidence(state: AnalyticalState) -> dict:
        """Extract structured evidence from retrieved chunks using LLM."""
        plan = AnalysisPlan(**state["plan"])
        chunks = state.get("_current_chunks", [])

        if not chunks:
            return {"round": state.get("round", 0) + 1}

        # Build chunk context for LLM
        chunks_text = ""
        for i, c in enumerate(chunks[:15], 1):  # Limit to 15 chunks per round
            section_info = f" [{c['section']}]" if c.get("section") else ""
            chunks_text += f"[{i}] (p.{c.get('page', '?')}{section_info})\n{c['content'][:500]}\n\n"

        aspects_str = ", ".join(plan.aspects)
        prompt = (
            "Извлеки факты из контекста, относящиеся к вопросу.\n\n"
            f"Вопрос: {state['question']}\n"
            f"Аспекты для раскрытия: {aspects_str}\n\n"
            f"Контекст:\n{chunks_text}\n\n"
            "Ответь строго JSON-массивом фактов:\n"
            '[\n  {"fact": "...", "aspect": "какой аспект", "chunk_index": 1, "relevance": 0.9},\n  ...\n]\n\n'
            "Правила:\n"
            "- Каждый факт — одно конкретное утверждение из текста\n"
            "- aspect — из списка аспектов выше\n"
            "- chunk_index — номер чанка [N] из контекста\n"
            "- relevance — 0.0-1.0, насколько факт отвечает на вопрос\n"
            "- Максимум 15 фактов, только релевантные (relevance > 0.5)\n"
        )

        try:
            messages = [
                SystemMessage(content="Ты — аналитик-экстрактор фактов. Отвечай только JSON."),
                HumanMessage(content=prompt),
            ]
            response = await fast_llm.ainvoke(messages)
            text = parser.invoke(response).strip()

            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            facts_raw = json.loads(text)
        except Exception as e:
            logger.warning("[EVIDENCE] LLM extraction failed: %s", e)
            facts_raw = []

        # Build evidence objects
        existing_evidence = list(state.get("evidence", []))
        for f in facts_raw:
            chunk_idx = f.get("chunk_index", 1) - 1  # 1-based -> 0-based
            chunk = chunks[chunk_idx] if 0 <= chunk_idx < len(chunks) else {}

            ev = Evidence(
                fact=f.get("fact", ""),
                source=chunk.get("source", ""),
                section=chunk.get("section", ""),
                chunk_id=chunk.get("id", ""),
                relevance=float(f.get("relevance", 0.5)),
                aspect=f.get("aspect", ""),
            )
            existing_evidence.append(ev.model_dump())

        logger.info(
            "[EVIDENCE] Round %d: extracted %d new facts (total: %d)",
            state.get("round", 0) + 1, len(facts_raw), len(existing_evidence),
        )

        return {
            "evidence": existing_evidence,
            "round": state.get("round", 0) + 1,
        }

    # ========== Node 4: Compare (for comparative questions) ==========
    async def compare_entities(state: AnalyticalState) -> dict:
        """Build a comparison table from collected evidence."""
        plan = AnalysisPlan(**state["plan"])
        evidence = state.get("evidence", [])

        if plan.question_type != "comparative" or not plan.entities_to_compare:
            return {}

        entities = plan.entities_to_compare
        aspects = plan.aspects

        # Build evidence context for comparison
        evidence_text = ""
        for ev in evidence:
            evidence_text += f"- [{ev.get('aspect', '?')}] {ev.get('fact', '')}\n"

        prompt = (
            "Построй таблицу сравнения на основе фактов.\n\n"
            f"Объекты сравнения: {', '.join(entities)}\n"
            f"Критерии: {', '.join(aspects)}\n\n"
            f"Факты:\n{evidence_text}\n\n"
            "Ответь строго JSON:\n"
            "{\n"
            '  "rows": [\n'
            '    {"criterion": "...", "values": {"объект1": "описание", "объект2": "описание"}},\n'
            "    ...\n"
            "  ]\n"
            "}\n\n"
            "Правила:\n"
            "- Один row на каждый критерий сравнения\n"
            "- values — ключ = имя объекта, значение = краткое описание\n"
            "- Если данных нет — поставь '-'\n"
        )

        try:
            messages = [
                SystemMessage(content="Ты — аналитик-компаратор. Отвечай только JSON."),
                HumanMessage(content=prompt),
            ]
            response = await fast_llm.ainvoke(messages)
            text = parser.invoke(response).strip()

            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            table_data = json.loads(text)
            table = ComparisonTable(
                entities=entities,
                rows=[ComparisonRow(**r) for r in table_data.get("rows", [])],
            )
        except Exception as e:
            logger.warning("[COMPARE] Table generation failed: %s", e)
            table = ComparisonTable(entities=entities)

        logger.info(
            "[COMPARE] Generated table: %d entities x %d criteria",
            len(table.entities), len(table.rows),
        )

        return {"comparison_table": table.model_dump()}

    # ========== Node 5: Check Coverage ==========
    async def check_coverage(state: AnalyticalState) -> dict:
        """Check if all aspects of the question are covered by evidence."""
        plan = AnalysisPlan(**state["plan"])
        evidence = state.get("evidence", [])
        aspects = plan.aspects

        if not aspects:
            return {"coverage": 1.0, "uncovered_aspects": []}

        # Check which aspects have evidence
        covered_aspects = set()
        for ev in evidence:
            asp = ev.get("aspect", "")
            if asp:
                # Fuzzy match: check if any planned aspect is partially matched
                for planned in aspects:
                    if asp.lower() in planned.lower() or planned.lower() in asp.lower():
                        covered_aspects.add(planned)

        uncovered = [a for a in aspects if a not in covered_aspects]
        coverage = len(covered_aspects) / len(aspects) if aspects else 1.0

        logger.info(
            "[COVERAGE] %.0f%% covered (%d/%d aspects), uncovered: %s",
            coverage * 100, len(covered_aspects), len(aspects),
            uncovered[:3] if uncovered else "none",
        )

        return {
            "coverage": coverage,
            "uncovered_aspects": uncovered,
        }

    # ========== Node 6: Synthesize ==========
    async def synthesize(state: AnalyticalState) -> dict:
        """Generate the final structured answer from evidence."""
        question = state["question"]
        plan = AnalysisPlan(**state["plan"])
        evidence = state.get("evidence", [])
        comparison = state.get("comparison_table")
        rounds_used = state.get("round", 0)

        # Build evidence summary for LLM
        evidence_text = ""
        for i, ev in enumerate(evidence, 1):
            src = f" (p.{ev.get('source', '?')}, {ev.get('section', '')})" if ev.get("source") else ""
            evidence_text += f"[{i}] {ev.get('fact', '')}{src}\n"

        comp_table_md = ""
        if comparison:
            comp_table = ComparisonTable(**comparison)
            comp_table_md = comp_table.to_markdown()

        prompt = (
            "Синтезируй ответ на основе собранных фактов.\n\n"
            f"Вопрос: {question}\n"
            f"Тип вопроса: {plan.question_type}\n"
            f"Аспекты: {', '.join(plan.aspects)}\n\n"
            f"Собранные факты ({len(evidence)} шт.):\n{evidence_text}\n\n"
        )

        if comp_table_md:
            prompt += f"Таблица сравнения:\n{comp_table_md}\n\n"

        prompt += (
            "Требования к ответу:\n"
            "1. Начни с краткого резюме (2-3 предложения)\n"
            "2. Затем детальный анализ с разбивкой по аспектам\n"
            "3. Если есть таблица сравнения — включи её в ответ\n"
            "4. Указывай источники [N] из списка фактов\n"
            "5. В конце — краткий вывод\n"
            "6. Отвечай на русском языке\n"
        )

        try:
            messages = [
                SystemMessage(
                    content="Ты — аналитик документации 1С:Предприятие. "
                    "Даёшь структурированные, аргументированные ответы на русском языке."
                ),
                HumanMessage(content=prompt),
            ]
            response = await llm.ainvoke(messages)
            analysis_text = parser.invoke(response)
        except Exception as e:
            logger.error("[SYNTHESIZE] Generation failed: %s", e)
            analysis_text = "Ошибка генерации ответа."

        # Extract sources
        sources: list[str] = []
        for ev in evidence:
            src = ev.get("source", "")
            if src and src not in sources:
                sources.append(src)

        # Build summary (first 2-3 sentences)
        summary_lines = analysis_text.split("\n")
        summary = ""
        for line in summary_lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("|"):
                summary = line
                break

        structured = StructuredAnswer(
            summary=summary[:500] if summary else "",
            detailed_analysis=analysis_text,
            comparison_table=ComparisonTable(**comparison) if comparison else None,
            evidence=[Evidence(**ev) for ev in evidence],
            sources=sources,
            coverage=state.get("coverage", 0.0),
            rounds_used=rounds_used,
        )

        logger.info(
            "[SYNTHESIZE] Generated: %d chars, %d sources, %d evidence, %d rounds",
            len(analysis_text), len(sources), len(evidence), rounds_used,
        )

        return {
            "answer": analysis_text,
            "structured_answer": structured.model_dump(),
            "sources": sources,
        }

    # ========== Conditional Edges ==========

    def should_retrieve_more_or_synthesize(state: AnalyticalState) -> str:
        """Decide if more retrieval rounds are needed."""
        coverage = state.get("coverage", 0.0)
        current_round = state.get("round", 0)
        max_rounds = state.get("max_rounds", _MAX_ROUNDS)
        uncovered = state.get("uncovered_aspects", [])

        if coverage >= _COVERAGE_THRESHOLD:
            logger.info("[EDGE] Coverage %.0f%% >= %.0f%% -> synthesize", coverage * 100, _COVERAGE_THRESHOLD * 100)
            return "synthesize"

        if current_round >= max_rounds:
            logger.info("[EDGE] Max rounds %d reached -> synthesize", max_rounds)
            return "synthesize"

        if not uncovered:
            return "synthesize"

        logger.info("[EDGE] Coverage %.0f%%, round %d/%d -> retrieve_more", coverage * 100, current_round, max_rounds)
        return "retrieve_more"

    def should_compare_or_synthesize(state: AnalyticalState) -> str:
        """Route to comparison or directly to coverage check."""
        plan_data = state.get("plan", {})
        q_type = plan_data.get("question_type", "factual")
        entities = plan_data.get("entities_to_compare", [])

        if q_type == "comparative" and len(entities) >= 2:
            return "compare"
        return "check_coverage"

    # ========== Build Graph ==========
    graph = StateGraph(AnalyticalState)

    graph.add_node("plan", plan_analysis)
    graph.add_node("retrieve", retrieve)
    graph.add_node("collect_evidence", collect_evidence)
    graph.add_node("compare", compare_entities)
    graph.add_node("check_coverage", check_coverage)
    graph.add_node("synthesize", synthesize)

    # Entry point
    graph.set_entry_point("plan")

    # Edges
    graph.add_edge("plan", "retrieve")
    graph.add_edge("retrieve", "collect_evidence")

    # After evidence collection: compare (if comparative) or check coverage
    graph.add_conditional_edges(
        "collect_evidence",
        should_compare_or_synthesize,
        {"compare": "compare", "check_coverage": "check_coverage"},
    )

    graph.add_edge("compare", "check_coverage")

    # After coverage check: retrieve more or synthesize
    graph.add_conditional_edges(
        "check_coverage",
        should_retrieve_more_or_synthesize,
        {"retrieve_more": "retrieve", "synthesize": "synthesize"},
    )

    graph.add_edge("synthesize", END)

    logger.info("[GRAPH] Compiled Analytical RAG agent (Phase 33)")

    return graph.compile()
