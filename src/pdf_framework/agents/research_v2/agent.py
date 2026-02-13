"""Research Agent v2 — Plan-Execute-Verify (Phase 36).

Autonomous LangGraph agent with:
- Dependency-tree planning
- Adaptive execution (agent decides depth)
- Evidence graph with contradiction detection
- Quality gates (coverage >=80%, groundedness >=90%)
- Structured report generation
- Session memory for multi-step research
"""

import asyncio
import json
import logging
import uuid

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import END, StateGraph

from src.pdf_framework.agents.research_v2.schemas import (
    EvidenceFact,
    EvidenceGraph,
    EvidenceRelation,
    QualityGateResult,
    ReportSection,
    ResearchPlanTree,
    ResearchReport,
    ResearchTask,
    ResearchV2State,
)
from src.pdf_framework.config import AgentSettings
from src.pdf_framework.search.manager import SearchManager

logger = logging.getLogger(__name__)

_MAX_ROUNDS = 5
_COVERAGE_GATE = 0.80
_GROUNDEDNESS_GATE = 0.90


def create_research_agent_v2(
    search_manager: SearchManager,
    settings: AgentSettings | None = None,
    api_key: str = "",
    fast_model: str = "claude-sonnet-4-5-20250929",
):
    """Create a LangGraph Research Agent v2.

    Phase 36: Plan-Execute-Verify with evidence graph and quality gates.

    Args:
        search_manager: Search manager for multi-strategy retrieval.
        settings: Agent configuration.
        api_key: Anthropic API key.
        fast_model: Model for planning and extraction (Sonnet).

    Returns:
        Compiled LangGraph ready for invocation.
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

    # ========== Node 1: Plan Research ==========
    async def plan_research(state: ResearchV2State) -> dict:
        """Generate a dependency-tree research plan."""
        question = state["question"]

        prompt = (
            "Ты — планировщик исследований. Построй план-дерево для вопроса.\n\n"
            "Ответь строго JSON:\n"
            "{\n"
            '  "complexity": "simple|moderate|complex",\n'
            '  "tasks": [\n'
            '    {"id": "1", "question": "...", "strategy": "hybrid", '
            '"parent_id": null, "priority": 1},\n'
            '    {"id": "1.1", "question": "...", "strategy": "bm25", '
            '"parent_id": "1", "priority": 2},\n'
            "    ...\n"
            "  ]\n"
            "}\n\n"
            "Правила:\n"
            "- 3-8 задач, организованных в дерево зависимостей\n"
            "- parent_id=null для корневых задач (можно начать параллельно)\n"
            "- parent_id='1' означает: начать после задачи '1'\n"
            "- strategy: hybrid, bm25, section_first, graphrag_local, vector\n"
            "- Для сравнительных вопросов: отдельные задачи для каждого объекта\n"
            "- Для обзорных: иерархия аспектов с зависимостями\n"
            "- Последняя задача — интеграция/проверка (зависит от всех предыдущих)\n"
        )

        try:
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content=question),
            ]
            response = await fast_llm.ainvoke(messages)
            text = parser.invoke(response).strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)
            tasks = [ResearchTask(**t) for t in data.get("tasks", [])]
            plan = ResearchPlanTree(
                original_question=question,
                complexity=data.get("complexity", "moderate"),
                tasks=tasks,
            )
        except Exception as e:
            logger.warning("[PLAN_V2] LLM planning failed: %s, using defaults", e)
            plan = ResearchPlanTree(
                original_question=question,
                complexity="moderate",
                tasks=[
                    ResearchTask(id="1", question=question, strategy="hybrid"),
                    ResearchTask(
                        id="2",
                        question=f"Связанные аспекты: {question}",
                        strategy="bm25",
                    ),
                    ResearchTask(
                        id="3",
                        question=f"Детали и примеры: {question}",
                        strategy="section_first",
                        parent_id="1",
                    ),
                ],
            )

        logger.info(
            "[PLAN_V2] complexity=%s, tasks=%d",
            plan.complexity,
            len(plan.tasks),
        )

        return {
            "plan": plan.model_dump(),
            "evidence_graph": EvidenceGraph().model_dump(),
            "round": 0,
            "max_rounds": min(state.get("max_rounds", _MAX_ROUNDS), _MAX_ROUNDS),
            "total_queries": 0,
            "session_id": state.get("session_id", str(uuid.uuid4())[:8]),
        }

    # ========== Node 2: Execute Tasks ==========
    async def execute_tasks(state: ResearchV2State) -> dict:
        """Execute ready tasks from the plan (parallel where possible)."""
        plan = ResearchPlanTree(**state["plan"])
        ready = plan.get_ready_tasks()

        if not ready:
            # All tasks done or blocked — force remaining to done
            for t in plan.tasks:
                if t.status == "pending":
                    t.status = "skipped"
            return {
                "plan": plan.model_dump(),
                "current_chunks": [],
            }

        # Execute ready tasks in parallel
        async def _search_task(task: ResearchTask):
            try:
                strategy = task.strategy
                if strategy == "section_first":
                    return task, await search_manager.search_section_first(
                        query=task.question, k=5,
                    )
                return task, await search_manager.search(
                    query=task.question, strategy=strategy, k=5, rerank=True,
                )
            except Exception as e:
                logger.warning("[EXEC] Task %s failed: %s", task.id, e)
                return task, None

        results = await asyncio.gather(
            *[_search_task(t) for t in ready[:4]],  # max 4 parallel
        )

        all_chunks: list[dict] = []
        seen_ids: set[str] = set()

        # Collect existing evidence chunk_ids
        eg = EvidenceGraph(**state.get("evidence_graph", {}))
        for f in eg.facts:
            if f.chunk_id:
                seen_ids.add(f.chunk_id)

        query_count = state.get("total_queries", 0)

        for task, response in results:
            plan.mark_done(task.id)
            query_count += 1
            if response is None:
                continue
            for sr in response.results:
                if sr.chunk.id not in seen_ids:
                    seen_ids.add(sr.chunk.id)
                    all_chunks.append({
                        "id": sr.chunk.id,
                        "content": sr.chunk.content,
                        "score": sr.score,
                        "source": sr.chunk.metadata.get("source", ""),
                        "page": sr.chunk.metadata.get("page_number", ""),
                        "section": sr.chunk.metadata.get("section_title", "")
                            or sr.chunk.metadata.get("breadcrumb", ""),
                        "task_id": task.id,
                    })

        logger.info(
            "[EXEC] Executed %d tasks, got %d new chunks (progress: %.0f%%)",
            len(results),
            len(all_chunks),
            plan.progress * 100,
        )

        return {
            "plan": plan.model_dump(),
            "current_chunks": all_chunks,
            "total_queries": query_count,
        }

    # ========== Node 3: Build Evidence ==========
    async def build_evidence(state: ResearchV2State) -> dict:
        """Extract facts from chunks and build the evidence graph."""
        chunks = state.get("current_chunks", [])
        if not chunks:
            return {"round": state.get("round", 0) + 1}

        eg = EvidenceGraph(**state.get("evidence_graph", {}))
        plan = ResearchPlanTree(**state["plan"])

        # Group aspects from plan tasks
        aspects = [t.question for t in plan.tasks if t.status == "done"]
        aspects_str = "; ".join(aspects[:5])

        # Build context
        chunks_text = ""
        for i, c in enumerate(chunks[:20], 1):
            sec = f" [{c['section']}]" if c.get("section") else ""
            chunks_text += (
                f"[{i}] (p.{c.get('page', '?')}{sec}, task={c.get('task_id', '?')})\n"
                f"{c['content'][:400]}\n\n"
            )

        prompt = (
            "Извлеки факты из контекста для исследования.\n\n"
            f"Вопрос: {state['question']}\n"
            f"Исследуемые аспекты: {aspects_str}\n\n"
            f"Контекст:\n{chunks_text}\n\n"
            "Ответь JSON:\n"
            "{\n"
            '  "facts": [\n'
            '    {"fact": "...", "aspect": "...", "chunk_index": 1, '
            '"confidence": 0.9}\n'
            "  ],\n"
            '  "relations": [\n'
            '    {"source_idx": 0, "target_idx": 1, '
            '"type": "supports|contradicts|refines"}\n'
            "  ]\n"
            "}\n\n"
            "Правила:\n"
            "- Максимум 15 фактов, только с confidence > 0.5\n"
            "- Связи: supports (подтверждает), contradicts (противоречит), "
            "refines (уточняет)\n"
            "- chunk_index — номер [N] из контекста\n"
        )

        try:
            messages = [
                SystemMessage(
                    content="Ты — аналитик-экстрактор фактов. Отвечай только JSON."
                ),
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
        except Exception as e:
            logger.warning("[EVIDENCE_V2] LLM extraction failed: %s", e)
            data = {"facts": [], "relations": []}

        # Build evidence facts
        new_fact_ids: list[str] = []
        existing_count = len(eg.facts)
        for f in data.get("facts", []):
            chunk_idx = f.get("chunk_index", 1) - 1
            chunk = chunks[chunk_idx] if 0 <= chunk_idx < len(chunks) else {}

            fact_id = f"f{existing_count + len(new_fact_ids) + 1}"
            ef = EvidenceFact(
                id=fact_id,
                fact=f.get("fact", ""),
                source=chunk.get("source", ""),
                section=chunk.get("section", ""),
                chunk_id=chunk.get("id", ""),
                confidence=float(f.get("confidence", 0.7)),
                aspect=f.get("aspect", ""),
                task_id=chunk.get("task_id", ""),
            )
            eg.add_fact(ef)
            new_fact_ids.append(fact_id)

        # Build relations
        for rel in data.get("relations", []):
            src_idx = rel.get("source_idx", 0)
            tgt_idx = rel.get("target_idx", 0)
            if 0 <= src_idx < len(new_fact_ids) and 0 <= tgt_idx < len(new_fact_ids):
                eg.add_relation(
                    EvidenceRelation(
                        source_id=new_fact_ids[src_idx],
                        target_id=new_fact_ids[tgt_idx],
                        relation_type=rel.get("type", "supports"),
                    )
                )

        logger.info(
            "[EVIDENCE_V2] Round %d: +%d facts (total: %d), +%d relations, "
            "%d contradictions",
            state.get("round", 0) + 1,
            len(new_fact_ids),
            len(eg.facts),
            len(data.get("relations", [])),
            len(eg.find_contradictions()),
        )

        return {
            "evidence_graph": eg.model_dump(),
            "round": state.get("round", 0) + 1,
        }

    # ========== Node 4: Quality Gate ==========
    async def quality_gate(state: ResearchV2State) -> dict:
        """Evaluate quality gates: coverage, groundedness, confidence."""
        plan = ResearchPlanTree(**state["plan"])
        eg = EvidenceGraph(**state.get("evidence_graph", {}))

        # Coverage: how many plan tasks have evidence
        tasks_with_evidence: set[str] = set()
        all_aspects: set[str] = set()
        for t in plan.tasks:
            all_aspects.add(t.question[:50])  # truncate for matching
        for f in eg.facts:
            if f.task_id:
                tasks_with_evidence.add(f.task_id)
            if f.aspect:
                for a in all_aspects:
                    if f.aspect.lower() in a.lower() or a.lower() in f.aspect.lower():
                        tasks_with_evidence.add(a)

        coverage = (
            len(tasks_with_evidence) / len(plan.tasks) if plan.tasks else 1.0
        )

        # Groundedness: facts with high confidence
        if eg.facts:
            avg_confidence = sum(f.confidence for f in eg.facts) / len(eg.facts)
            high_confidence_ratio = (
                sum(1 for f in eg.facts if f.confidence >= 0.7) / len(eg.facts)
            )
            groundedness = high_confidence_ratio
        else:
            avg_confidence = 0.0
            groundedness = 0.0

        contradictions = len(eg.find_contradictions())

        # Determine uncovered
        covered_task_ids = {f.task_id for f in eg.facts if f.task_id}
        uncovered = [
            t.question for t in plan.tasks
            if t.id not in covered_task_ids and t.status == "done"
        ]

        # Determine recommendation
        current_round = state.get("round", 0)
        max_rounds = state.get("max_rounds", _MAX_ROUNDS)

        passed = coverage >= _COVERAGE_GATE and groundedness >= _GROUNDEDNESS_GATE
        if passed or current_round >= max_rounds:
            recommendation = "finalize"
        elif plan.get_ready_tasks():
            recommendation = "continue"
        else:
            recommendation = "finalize"  # no more tasks to execute

        gate = QualityGateResult(
            coverage=round(coverage, 2),
            groundedness=round(groundedness, 2),
            confidence=round(avg_confidence, 2),
            passed=passed,
            uncovered_aspects=uncovered[:5],
            contradictions=contradictions,
            recommendation=recommendation,
        )

        logger.info(
            "[QUALITY_V2] coverage=%.0f%%, groundedness=%.0f%%, confidence=%.2f, "
            "contradictions=%d, recommendation=%s",
            gate.coverage * 100,
            gate.groundedness * 100,
            gate.confidence,
            gate.contradictions,
            gate.recommendation,
        )

        return {"quality": gate.model_dump()}

    # ========== Node 5: Generate Report ==========
    async def generate_report(state: ResearchV2State) -> dict:
        """Generate a comprehensive structured report."""
        question = state["question"]
        eg = EvidenceGraph(**state.get("evidence_graph", {}))
        plan = ResearchPlanTree(**state["plan"])
        quality = QualityGateResult(**state.get("quality", {}))

        # Build evidence context for report generation
        top_facts = eg.strongest_facts(top_k=20)
        facts_text = ""
        for i, f in enumerate(top_facts, 1):
            src = f" ({f.source}, {f.section})" if f.source else ""
            facts_text += f"[{i}] {f.fact}{src}\n"

        contradictions = eg.find_contradictions()
        contra_text = ""
        if contradictions:
            fact_map = {f.id: f for f in eg.facts}
            for c in contradictions:
                src = fact_map.get(c.source_id)
                tgt = fact_map.get(c.target_id)
                if src and tgt:
                    contra_text += (
                        f"- ПРОТИВОРЕЧИЕ: \"{src.fact}\" vs \"{tgt.fact}\"\n"
                    )

        # Group facts by plan task
        task_sections = ""
        for task in plan.tasks:
            task_facts = [f for f in eg.facts if f.task_id == task.id]
            if task_facts:
                task_sections += (
                    f"\n### Задача: {task.question}\n"
                    + "".join(f"- {f.fact}\n" for f in task_facts[:5])
                )

        prompt = (
            "Составь структурированный исследовательский отчёт.\n\n"
            f"Вопрос: {question}\n"
            f"Сложность: {plan.complexity}\n"
            f"Раундов поиска: {state.get('round', 0)}\n"
            f"Собрано фактов: {len(eg.facts)}\n"
            f"Покрытие: {quality.coverage:.0%}\n\n"
            f"Ключевые факты:\n{facts_text}\n\n"
        )

        if contra_text:
            prompt += f"Обнаруженные противоречия:\n{contra_text}\n\n"

        if task_sections:
            prompt += f"Факты по задачам:\n{task_sections}\n\n"

        prompt += (
            "Формат отчёта:\n"
            "1. **Резюме** (3-5 предложений)\n"
            "2. **Основные выводы** (по каждому аспекту)\n"
            "3. **Сравнительная таблица** (если применимо, в markdown)\n"
            "4. **Противоречия** (если есть)\n"
            "5. **Заключение** (2-3 предложения)\n\n"
            "Указывай источники [N] из списка фактов.\n"
            "Отвечай на русском языке.\n"
        )

        try:
            messages = [
                SystemMessage(
                    content="Ты — аналитик документации 1С:Предприятие. "
                    "Составляешь подробные структурированные отчёты."
                ),
                HumanMessage(content=prompt),
            ]
            response = await llm.ainvoke(messages)
            report_text = parser.invoke(response)
        except Exception as e:
            logger.error("[REPORT_V2] Generation failed: %s", e)
            report_text = "Ошибка генерации отчёта."

        # Extract sources
        sources: list[str] = []
        for f in eg.facts:
            if f.source and f.source not in sources:
                sources.append(f.source)

        # Build sections from report text
        sections: list[ReportSection] = []
        current_title = ""
        current_content = ""
        for line in report_text.split("\n"):
            if line.startswith("## ") or line.startswith("**") and line.endswith("**"):
                if current_title:
                    sections.append(
                        ReportSection(title=current_title, content=current_content.strip())
                    )
                current_title = line.strip("#* ")
                current_content = ""
            else:
                current_content += line + "\n"
        if current_title:
            sections.append(
                ReportSection(title=current_title, content=current_content.strip())
            )

        # Extract summary (first section or first paragraph)
        summary = ""
        for sec in sections:
            if "резюме" in sec.title.lower() or "summary" in sec.title.lower():
                summary = sec.content[:500]
                break
        if not summary and sections:
            summary = sections[0].content[:500]

        report = ResearchReport(
            question=question,
            executive_summary=summary,
            sections=sections,
            contradictions=contra_text,
            sources=sources,
            evidence_count=len(eg.facts),
            rounds_used=state.get("round", 0),
            coverage=quality.coverage,
            total_search_queries=state.get("total_queries", 0),
        )

        logger.info(
            "[REPORT_V2] Generated: %d chars, %d sections, %d sources, "
            "%d evidence, %d rounds",
            len(report_text),
            len(sections),
            len(sources),
            len(eg.facts),
            state.get("round", 0),
        )

        return {
            "report": report.model_dump(),
            "answer": report_text,
        }

    # ========== Conditional Edges ==========

    def should_continue_or_finalize(state: ResearchV2State) -> str:
        """Decide: continue executing tasks or finalize report."""
        quality = state.get("quality", {})
        recommendation = quality.get("recommendation", "finalize")

        if recommendation == "continue":
            return "execute"
        return "report"

    # ========== Build Graph ==========
    graph = StateGraph(ResearchV2State)

    graph.add_node("plan", plan_research)
    graph.add_node("execute", execute_tasks)
    graph.add_node("evidence", build_evidence)
    graph.add_node("quality", quality_gate)
    graph.add_node("report", generate_report)

    graph.set_entry_point("plan")

    # Plan -> Execute -> Evidence -> Quality -> (Execute | Report)
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "evidence")
    graph.add_edge("evidence", "quality")

    graph.add_conditional_edges(
        "quality",
        should_continue_or_finalize,
        {"execute": "execute", "report": "report"},
    )

    graph.add_edge("report", END)

    logger.info("[GRAPH] Compiled Research Agent v2 (Phase 36)")

    return graph.compile()
