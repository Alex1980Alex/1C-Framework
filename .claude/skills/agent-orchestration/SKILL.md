# Agent Orchestration

## Когда использовать
- "RAG agent", "multi-agent", "LangGraph nodes"
- "Self-RAG", "hallucination", "query rewriting"
- "analytical agent", "research agent", "orchestrator"
- "какой агент выбрать", "adaptive", "deep research", "чат"

---

## Для пользователя — выбор агента

### Decision Tree

```
Что нужно?
├─ Простой вопрос                → ask (Self-RAG)
├─ Автоматический выбор          → ask --strategy adaptive
├─ Сравнение / анализ            → ask --strategy adaptive (decomposition)
├─ Глубокое исследование         → research
├─ Многошаговый диалог           → chat
└─ Структурированный отчёт       → research --max-rounds 5
```

### 6 типов агентов + Chat mode

| Агент | Назначение | Скорость | CLI |
|-------|-----------|----------|-----|
| **Self-RAG** | Q&A с grading + rewriting | 3-5 с | `ask "?"` |
| **Adaptive** | Автоклассификация → стратегия | Зависит | `ask "?" --strategy adaptive` |
| **Deep Research** | Планирование → multi-step | 10-30 с | `research "?"` |
| **Analytical** | Evidence collection + tables | 5-10 с | MCP: `analyze` |
| **Multi-Agent** | 4 агента: retrieval→analysis→writing→verify | 10-20 с | MCP: `plan_execute` |
| **Plan-Execute** | DAG план → пошаговое выполнение | 10-30 с | MCP: `plan_execute` |

> **Chat mode** (`chat`) — это не отдельный агент, а CLI-режим с ConversationMemory (SQLite/Memory backend). Использует RAG Agent + history rewriting.

### CLI примеры

```bash
# Простой вопрос с Self-RAG
python -m src.cli.main ask "Что такое конфигуратор?" --stream

# Adaptive — автоклассификация типа запроса
python -m src.cli.main ask "Сравните регистры" --strategy adaptive --verbose

# Deep Research — многошаговое исследование
python -m src.cli.main research "Сравните все типы модулей"

# Интерактивный чат с историей
python -m src.cli.main chat --strategy hybrid --thread session-1
```

### Adaptive RAG — автоклассификация

```
Запрос → Rule-based (90%, 0 мс) / LLM (10%)
  → factual + simple   → vector
  → factual + moderate → hybrid + reranking
  → conceptual         → graphrag_local
  → overview           → graphrag_global
  → complex            → decomposition → multi-step
```

### Deep Research — многошаговый

```
Step 1: Декомпозиция на 3-5 подвопросов
Step 2: Для каждого → поиск → проверка полноты → уточнение
Step 3: Quality check (coverage + groundedness)
Step 4: Синтез с citations
```

### Chat Mode — multi-turn с историей (не отдельный агент)

Реализация: CLI `chat` команда + `ConversationMemory` (SQLite backend).

- Команды: `/history`, `/clear`, `/strategy vector`, `/quit`
- Query Reformulation: автоматическая перезапись с учётом истории
- Backend: `MemoryBackend` (dev) или `SQLiteBackend` (production, `data/conversations.db`)
- Cleanup: `auto_cleanup_days=30` — автоудаление старых тредов

```env
CONVERSATION__MAX_HISTORY=10
CONVERSATION__STORAGE=sqlite
CONVERSATION__DB_PATH=data/conversations.db
```

### API

```bash
# RAG вопрос-ответ
curl -X POST http://localhost:8000/search/ask \
    -d '{"query": "Что такое конфигуратор?", "strategy": "hybrid"}'

# Streaming (SSE)
curl -X POST http://localhost:8000/search/ask/stream \
    -d '{"query": "Опишите архитектуру"}'

# Chat
curl -X POST http://localhost:8000/chat/message \
    -d '{"message": "Расскажите о регистрах", "thread_id": "session-1"}'
```

---

## Internals — pipeline и отладка

## Типы агентов (классы)

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

4 агента с verify→rewrite loop:
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
SELFRAG__MAX_RETRIES=2
ADAPTIVE__ROUTING_ENABLED=true
CONVERSATION__MAX_HISTORY=10
```

## Диагностика

| Симптом | Причина | Решение |
|---------|---------|---------|
| Бесконечный rewrite loop | max_retries не ограничен | Проверить `retry_count < max_retries` |
| Grading всё отбрасывает | Score prefilter строгий | Понизить `score_prefilter_threshold` (0.05) |
| Hallucination false positives | Сложный контекст | Урезать `max_context_chars` (4000) |
| Multi-agent застрял | Max iterations не задан | `_MAX_ITERATIONS = 2` |
| Z.AI proxy 401 | Missing base_url | `base_url=settings.base_url` |

## Связанные скиллы

- `framework-cli` — CLI команды ask, chat, research
- `framework-config` — .env параметры агентов
- `search-pipeline-debug` — стратегии поиска

## Файлы
- RAG Agent: `src/pdf_framework/agents/rag/agent.py`
- RAG Nodes: `src/pdf_framework/agents/rag/nodes/`
- Multi-Agent: `src/pdf_framework/agents/multi/orchestrator.py`
- Analytical: `src/pdf_framework/agents/analytical/agent.py`
- Research v2: `src/pdf_framework/agents/research_v2/agent.py`
- Plan-Execute: `src/pdf_framework/agents/plan_execute/`
- Routing: `src/pdf_framework/agents/routing/`
- Memory: `src/pdf_framework/agents/memory/conversation.py`, `backends.py`
- Middleware: `src/pdf_framework/agents/rag/middleware.py`
