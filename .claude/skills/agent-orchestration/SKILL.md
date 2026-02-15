# Agent Orchestration

## Когда использовать
- "RAG agent", "multi-agent", "LangGraph nodes"
- "Self-RAG", "hallucination", "query rewriting"
- "analytical agent", "research agent", "orchestrator"

## Типы агентов

| Агент | Назначение | Фреймворк | Раундов |
|-------|-----------|-----------|---------|
| **RAG Agent** | Q&A с grading + rewriting | LangGraph (7 nodes) | 1-3 |
| **Multi-Agent** | 4 агента: retrieval→analysis→writing→verification | LangGraph | 2 |
| **Analytical** | Structured analysis с evidence collection | LangGraph | 3 |
| **Research v2** | Deep research с plan-tree DAG | LangGraph | 5 |

## RAG Agent Pipeline (Self-RAG)

```
analyze_query → execute_search → grade_documents →
  ├─ relevance < 0.5 → rewrite_query → retry (max 2)
  └─ relevance >= 0.5 → generate_answer → check_hallucination →
      ├─ hallucinated → regenerate (max 2)
      └─ grounded → END
```

**Strategy escalation**: vector → hybrid → two_stage (при retry)

## Multi-Agent (Phase 39)

4 специализированных агента с verify→rewrite loop:
1. **Retrieval**: parallel search (hybrid, bm25, section_first)
2. **Analysis**: comparison, contradictions, conclusions
3. **Writing**: structured report synthesis
4. **Verification**: fact-checking + validation

## Конфиг

```env
AGENT__MODEL=claude-opus-4-6
AGENT__TEMPERATURE=0.0
AGENT__SEARCH_K=5
AGENT__RERANKER_ENABLED=true
AGENT__RERANKER_TYPE=llm
AGENT__CHECKPOINTER=memory        # memory|sqlite|postgres
SELFRAG__ENABLED=true
SELFRAG__RELEVANCE_THRESHOLD=0.5
SELFRAG__SCORE_PREFILTER_THRESHOLD=0.1
SELFRAG__MAX_RETRIES=2
SELFRAG__HALLUCINATION_CHECK_ENABLED=true
SELFRAG__ENRICHMENT_ENABLED=true
```

## Диагностика

| Симптом | Причина | Решение |
|---------|---------|---------|
| Бесконечный rewrite loop | max_retries не ограничен | Проверить `retry_count < max_retries` |
| Grading всё отбрасывает | Score prefilter слишком строгий | Понизить `score_prefilter_threshold` (0.05) |
| Hallucination false positives | LLM путается на сложном контексте | Урезать `max_context_chars` (4000) |
| Multi-agent застрял | Max iterations не задан | `_MAX_ITERATIONS = 2` в orchestrator |
| Z.AI proxy 401 | Missing base_url | Передать `base_url=settings.base_url` в ChatAnthropic |

## Файлы
- RAG Agent: `src/pdf_framework/agents/rag/agent.py`
- RAG State: `src/pdf_framework/agents/rag/state.py`
- RAG Nodes: `src/pdf_framework/agents/rag/nodes/` (grader, rewriter, hallucination_checker)
- Multi-Agent: `src/pdf_framework/agents/multi/orchestrator.py`
- Analytical: `src/pdf_framework/agents/analytical/agent.py`
- Research v2: `src/pdf_framework/agents/research_v2/agent.py`
- Middleware: `src/pdf_framework/agents/rag/middleware.py` (token tracking)
