"""LangGraph RAG agent with Self-RAG (Phase 5).

Enhanced agent pipeline:
  analyze → search → grade → (rewrite | generate) → hallucination_check → (regenerate | end)

Phase 11.5: Anthropic prompt caching for token savings.
Phase 43: LangGraph checkpointing + middleware integration.

Author: Claude Code
Version: 1.3.0 - Phase 43: Framework integration (checkpointing, ONNX, middleware)
"""

import logging
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import END, StateGraph

from src.pdf_framework.agents.rag.nodes import (
    check_hallucination,
    grade_documents,
    regenerate_answer,
    rewrite_query,
)
from src.pdf_framework.agents.rag.state import RAGState
from src.pdf_framework.config import PROJECT_ROOT, AgentSettings, SelfRAGSettings
from src.pdf_framework.search.manager import SearchManager

logger = logging.getLogger(__name__)


def _create_cached_system_message(content: str) -> SystemMessage:
    """
    Create a SystemMessage with prompt caching enabled.

    Anthropic caches prompts with cache_control blocks.
    Effective for prompts > 1024 tokens.

    Args:
        content: System prompt content

    Returns:
        SystemMessage with cache_control
    """
    # Only use caching for longer prompts (cost-effective threshold)
    if len(content) > 1024:
        return SystemMessage(
            content=[
                {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}
            ]
        )
    return SystemMessage(content=content)


def create_rag_agent(
    search_manager: SearchManager,
    settings: AgentSettings | None = None,
    self_rag_settings: SelfRAGSettings | None = None,
    api_key: str = "",
):
    """Create a LangGraph RAG agent with Self-RAG support.

    Phase 5 (v0.6.0) Pipeline:
      1. analyze_query — classify question and choose strategy
      2. execute_search — run search via SearchManager
      3. grade_documents — LLM-based relevance assessment
      4. rewrite_query — if relevance < threshold, rewrite and retry
      5. generate_answer — produce final answer from context
      6. check_hallucination — verify answer is grounded
      7. regenerate_answer — if hallucinated, regenerate with strict prompt

    Args:
        search_manager: Search manager for vector/graph/hybrid search
        settings: Agent configuration (model, temperature, etc.)
        self_rag_settings: Self-RAG configuration
        api_key: Anthropic API key

    Returns:
        Compiled LangGraph ready for invocation
    """
    settings = settings or AgentSettings()
    self_rag_settings = self_rag_settings or SelfRAGSettings()

    # Phase 43: Token tracking middleware
    from src.pdf_framework.agents.rag.middleware import TokenTracker, ContentGuard, with_middleware

    token_tracker = TokenTracker(node_name="init")

    # LLM instances — pass base_url for Z.AI or other proxies
    main_llm_kwargs = dict(
        model=settings.model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        api_key=api_key or None,
    )
    if settings.base_url:
        main_llm_kwargs["base_url"] = settings.base_url
    main_llm = ChatAnthropic(**main_llm_kwargs)
    with_middleware(main_llm, token_tracker, ContentGuard())

    # Single fast LLM for all Self-RAG tasks (grading, rewriting, hallucination)
    # All three use the same model (Haiku by default), so one instance suffices.
    fast_llm_kwargs = dict(
        model=self_rag_settings.grading_model,
        temperature=0.0,
        max_tokens=1024,
        api_key=api_key or None,
    )
    if settings.base_url:
        fast_llm_kwargs["base_url"] = settings.base_url
    fast_llm = ChatAnthropic(**fast_llm_kwargs)
    with_middleware(fast_llm, token_tracker)

    parser = StrOutputParser()

    # ========== Node 1: Analyze Query ==========
    async def analyze_query(state: RAGState) -> dict:
        """Classify the question and choose the best search strategy."""
        token_tracker.set_node("analyze")
        question = state["question"]

        # Respect user-selected strategy if it's valid
        user_strategy = state.get("search_strategy")
        available = search_manager.available_strategies
        if user_strategy and user_strategy in available:
            logger.info(f"[ANALYZE] Using user-selected strategy: {user_strategy}")
            return {
                "query_type": "factual",
                "search_strategy": user_strategy,
                "original_question": question,
            }

        # Auto-classify with LLM when no valid strategy specified
        try:
            messages = [
                SystemMessage(
                    content=(
                        "Classify the user question into one of these types: factual, analytical, comparative. "
                        "Also choose the best search strategy: vector (semantic similarity), "
                        "graph (entity relations), or hybrid (both). "
                        "Reply with exactly two words: <query_type> <strategy>. "
                        "Example: factual vector"
                    )
                ),
                HumanMessage(content=question),
            ]
            response = await main_llm.ainvoke(messages)
            text = parser.invoke(response).strip().lower()
            parts = text.split()

            query_type = parts[0] if parts else "factual"
            strategy = parts[1] if len(parts) > 1 else "vector"
        except Exception as e:
            logger.error(f"[ANALYZE] LLM error: {e}, using defaults")
            query_type = "factual"
            strategy = "hybrid"

        # Fallback to available strategies
        if strategy not in available:
            strategy = available[0] if available else "vector"

        logger.info(f"[ANALYZE] query_type={query_type}, strategy={strategy}")

        return {
            "query_type": query_type,
            "search_strategy": strategy,
            "original_question": question,
        }

    # ========== Node 2: Execute Search ==========
    async def execute_search(state: RAGState) -> dict:
        """Run the chosen search strategy."""
        strategy = state.get("search_strategy", "vector")
        question = state["question"]
        k = settings.search_k

        logger.info(f"[SEARCH] strategy={strategy}, k={k}, query='{question[:50]}...'")

        try:
            response = await search_manager.search(
                query=question, strategy=strategy, k=k
            )
            context = _build_context(response)
            logger.info(f"[SEARCH] Found {len(response.results)} results")
            return {"search_response": response, "context": context}
        except Exception as e:
            logger.error(f"[SEARCH] Error: {e}")
            return {"error": str(e), "context": ""}

    # ========== Node 3: Grade Documents (Phase 5) ==========
    async def grade_documents_node(state: RAGState) -> dict:
        """Grade retrieved documents for relevance, then filter context."""
        token_tracker.set_node("grade")
        if not self_rag_settings.enabled:
            # Self-RAG disabled: use legacy evaluation
            return _legacy_evaluate_results(state)

        result = await grade_documents(state, fast_llm, self_rag_settings)

        # Filter context to keep only relevant documents
        graded = result.get("graded_documents", [])
        search_response = state.get("search_response")
        if search_response and graded:
            relevant_ids = {g["chunk_id"] for g in graded if g["is_relevant"]}
            if relevant_ids:
                from src.pdf_framework.schemas.documents import SearchResponse
                filtered_results = [
                    r for r in search_response.results
                    if r.chunk.id in relevant_ids
                ]
                if filtered_results:
                    filtered_response = SearchResponse(
                        query=search_response.query,
                        results=filtered_results,
                        total_found=len(filtered_results),
                        search_type=search_response.search_type,
                    )
                    result["context"] = _build_context(filtered_response)
                    result["search_response"] = filtered_response
                    logger.info(
                        f"[GRADE] Filtered context: {len(filtered_results)}/{len(search_response.results)} docs kept"
                    )

        return result

    def _legacy_evaluate_results(state: RAGState) -> dict:
        """Legacy evaluation for backward compatibility."""
        response = state.get("search_response")
        if not response or not response.results:
            return {"relevance_score": 0.0, "needs_more_context": True}

        avg_score = sum(r.score for r in response.results) / len(response.results)
        needs_more = avg_score < 0.3 or len(response.results) < 2
        return {"relevance_score": avg_score, "needs_more_context": needs_more}

    # ========== Node 4: Rewrite Query (Phase 5) ==========
    async def rewrite_query_node(state: RAGState) -> dict:
        """Rewrite query when relevance is low."""
        token_tracker.set_node("rewrite")
        return await rewrite_query(state, fast_llm, self_rag_settings)

    # ========== Node 5: Generate Answer (Ralph Wiggum) ==========
    async def generate_answer(state: RAGState) -> dict:
        """Generate the final answer from context with self-correcting retry."""
        token_tracker.set_node("generate")
        question = state["question"]
        context = state.get("context", "")

        if not context:
            logger.warning("[GENERATE] No context available")
            return {
                "answer": "Не удалось найти релевантную информацию для ответа на ваш вопрос.",
                "sources": [],
            }

        system_prompt = (
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
            f"Контекст:\n{context}"
        )

        # Ralph Wiggum: self-correcting feedback loop
        max_retries = 2
        feedback = ""
        last_answer = ""

        for attempt in range(1, max_retries + 1):
            try:
                prompt_text = question
                if feedback:
                    prompt_text += f"\n\n⚠️ КОРРЕКЦИЯ: {feedback}"

                messages = [
                    _create_cached_system_message(system_prompt),
                    HumanMessage(content=prompt_text),
                ]

                response = await main_llm.ainvoke(messages)
                answer = parser.invoke(response)
                last_answer = answer

                # Validate: non-empty?
                if len(answer.strip()) < 20:
                    feedback = "Ответ слишком короткий. Дай развёрнутый ответ на русском языке."
                    logger.warning(f"[GENERATE] Attempt {attempt}: too short ({len(answer)} chars)")
                    continue

                # Validate: Russian language?
                cyrillic = sum(1 for ch in answer[:300] if '\u0400' <= ch <= '\u04ff')
                latin = sum(1 for ch in answer[:300] if 'a' <= ch.lower() <= 'z')
                if latin > cyrillic * 2 and len(answer) > 50:
                    feedback = "Ответ должен быть на РУССКОМ языке. Переведи и ответь заново."
                    logger.warning(f"[GENERATE] Attempt {attempt}: not Russian (lat={latin}, cyr={cyrillic})")
                    continue

                # Valid answer — log cache savings and return
                usage = getattr(response, "usage", None)
                if usage:
                    cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0)
                    if cache_read_tokens > 0:
                        total_input_tokens = getattr(usage, "prompt_tokens", 0)
                        savings_pct = (cache_read_tokens / total_input_tokens * 100) if total_input_tokens > 0 else 0
                        logger.info(f"[GENERATE] Prompt cache saved {cache_read_tokens} tokens "
                                   f"({savings_pct:.1f}% reduction from {total_input_tokens} total)")

                logger.info(f"[GENERATE] Generated answer ({len(answer)} chars)")
                break

            except Exception as e:
                logger.error(f"[GENERATE] Attempt {attempt} error: {e}")
                feedback = f"Предыдущий вызов завершился ошибкой: {e}. Попробуй ещё раз."
                last_answer = f"Ошибка генерации ответа: {e}"

        answer = last_answer

        # Phase 41: Guaranteed section reference block
        search_resp = state.get("search_response")
        if search_resp and search_resp.results:
            from src.pdf_framework.utils.section_refs import append_section_refs
            answer = append_section_refs(answer, search_resp.results)

        sources: list[str] = []
        if search_resp:
            for r in search_resp.results:
                src = r.chunk.metadata.get("source", "")
                if src and src not in sources:
                    sources.append(src)

        # Phase 43: Attach token usage to metadata
        metadata = state.get("metadata", {}) or {}
        metadata["token_usage"] = token_tracker.usage.to_dict()

        return {"answer": answer, "sources": sources, "metadata": metadata}

    # ========== Node 6: Check Hallucination (Phase 5) ==========
    async def check_hallucination_node(state: RAGState) -> dict:
        """Check if answer is grounded in context."""
        token_tracker.set_node("hallucinate_check")
        if not self_rag_settings.enabled or not self_rag_settings.hallucination_check_enabled:
            logger.debug("[HALLUCINATION] Disabled, skipping")
            return {"is_hallucinated": False}

        return await check_hallucination(state, fast_llm, self_rag_settings)

    # ========== Node 7: Regenerate Answer (Phase 5) ==========
    async def regenerate_answer_node(state: RAGState) -> dict:
        """Regenerate answer with stricter prompt."""
        token_tracker.set_node("regenerate")
        return await regenerate_answer(state, main_llm, self_rag_settings)

    # ========== Conditional Edges ==========

    def should_rewrite_or_generate(state: RAGState) -> str:
        """Decide whether to rewrite query or proceed to generation."""
        if not self_rag_settings.enabled:
            # Legacy behavior
            if state.get("needs_more_context") and state.get("search_strategy") != "hybrid":
                return "retry"
            return "generate"

        # Self-RAG behavior
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", self_rag_settings.max_retries)
        relevance_ratio = state.get("relevance_ratio", 0.0)
        graded = state.get("graded_documents", [])

        # If at least 1 relevant doc exists (context was already filtered), generate
        has_relevant = any(g.get("is_relevant") for g in graded)
        if has_relevant:
            logger.info(f"[EDGE] relevance={relevance_ratio:.2%}, has_relevant=True → generate")
            return "generate"

        # No relevant docs at all — try rewriting
        if retry_count < max_retries:
            logger.info(f"[EDGE] relevance=0%, retry {retry_count+1}/{max_retries} → rewrite")
            return "rewrite"

        logger.info(f"[EDGE] No relevant docs after {retry_count} retries → generate (best effort)")
        return "generate"

    def should_regenerate_or_end(state: RAGState) -> str:
        """Decide whether to regenerate answer or finish."""
        if not self_rag_settings.enabled or not self_rag_settings.hallucination_check_enabled:
            return "end"

        is_hallucinated = state.get("is_hallucinated", False)
        attempts = state.get("generation_attempts", 0)
        max_attempts = self_rag_settings.max_generation_attempts

        if is_hallucinated and attempts < max_attempts:
            logger.info(f"[EDGE] hallucinated={is_hallucinated}, attempts={attempts} < {max_attempts} → regenerate")
            return "regenerate"

        return "end"

    # ========== Build the Graph ==========
    graph = StateGraph(RAGState)

    # Add nodes
    graph.add_node("analyze", analyze_query)
    graph.add_node("search", execute_search)
    graph.add_node("grade", grade_documents_node)
    graph.add_node("rewrite", rewrite_query_node)
    graph.add_node("generate", generate_answer)
    graph.add_node("hallucinate_check", check_hallucination_node)
    graph.add_node("regenerate", regenerate_answer_node)

    # Set entry point
    graph.set_entry_point("analyze")

    # Define edges
    graph.add_edge("analyze", "search")
    graph.add_edge("search", "grade")

    # Conditional: grade → rewrite or generate
    graph.add_conditional_edges(
        "grade",
        should_rewrite_or_generate,
        {"rewrite": "rewrite", "generate": "generate", "retry": "rewrite"},
    )

    graph.add_edge("rewrite", "search")
    graph.add_edge("generate", "hallucinate_check")

    # Conditional: hallucinate_check → regenerate or end
    graph.add_conditional_edges(
        "hallucinate_check",
        should_regenerate_or_end,
        {"regenerate": "regenerate", "end": END},
    )

    graph.add_edge("regenerate", END)

    # Phase 43: LangGraph checkpointing for state persistence
    compile_kwargs: dict = {}
    if settings.checkpointer == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            import sqlite3

            _ckpt_path = str(PROJECT_ROOT / "data" / "agent_checkpoints.db")
            conn = sqlite3.connect(_ckpt_path, check_same_thread=False)
            compile_kwargs["checkpointer"] = SqliteSaver(conn)
            logger.info("[GRAPH] SQLite checkpointer → %s", _ckpt_path)
        except ImportError:
            logger.warning("[GRAPH] langgraph.checkpoint.sqlite not available, no checkpointer")
    elif settings.checkpointer == "memory":
        try:
            from langgraph.checkpoint.memory import MemorySaver

            compile_kwargs["checkpointer"] = MemorySaver()
            logger.info("[GRAPH] In-memory checkpointer enabled")
        except ImportError:
            pass

    logger.info("[GRAPH] Compiled Self-RAG agent (v0.7.0 — Phase 43)")

    compiled = graph.compile(**compile_kwargs)
    # Expose token tracker for callers to inspect usage after invocation
    compiled.token_tracker = token_tracker  # type: ignore[attr-defined]
    return compiled


def _extract_section_number(title: str) -> str:
    """Extract section number like '5.9.4.3' from section_title or breadcrumb.

    Handles bold markdown: '**5.9.Документы**' → '5.9'
    """
    import re
    clean = title.replace("*", "").strip()
    m = re.match(r"(\d+(?:\.\d+)*)", clean)
    return m.group(1) if m else ""


def _build_context(response) -> str:
    """Build context string from search results.

    Phase 41: Each chunk starts with §section_number for LLM to reference.

    Args:
        response: SearchResponse with results

    Returns:
        Formatted context string
    """
    parts: list[str] = []
    for i, result in enumerate(response.results, 1):
        source = result.chunk.metadata.get("source", "unknown")
        page = result.chunk.metadata.get("page", "")
        page_str = f", стр. {page}" if page else ""

        # Phase 41: extract section number for §-references
        section_title = result.chunk.metadata.get("section_title", "")
        breadcrumb = result.chunk.metadata.get("breadcrumb", "")
        sec_num = _extract_section_number(section_title) or _extract_section_number(breadcrumb)
        sec_name = section_title.replace("*", "").strip()

        if sec_num:
            header = f"[{i}] (§{sec_num} «{sec_name}»{page_str}, score: {result.score:.3f})"
        else:
            header = f"[{i}] (source: {source}{page_str}, score: {result.score:.3f})"

        bc_line = f"\nРаздел: {breadcrumb}" if breadcrumb else ""
        parts.append(f"{header}{bc_line}\n{result.chunk.content}")
    return "\n\n---\n\n".join(parts)
