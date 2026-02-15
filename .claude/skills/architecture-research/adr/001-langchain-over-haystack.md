# ADR-001: LangChain + LangGraph вместо Haystack

**Дата:** 2026-02-14
**Статус:** accepted
**Исследование:** [cache/haystack-vs-langchain-architecture.md](../cache/haystack-vs-langchain-architecture.md)

---

## Контекст

Выбор основного RAG-фреймворка для PDF Vector & Graph Framework. Два основных кандидата:
- **Haystack 2.0** (deepset-ai) — Component + Pipeline архитектура, typed I/O
- **LangChain 1.0 + LangGraph** (langchain-ai) — Agent + Middleware + StateGraph

Исследование включает 18 GitHub-репозиториев, 3 набора бенчмарков, 10 критериев сравнения (см. кеш-файл).

## Решение

**Используем LangChain + LangGraph** как основной фреймворк.

### Обоснование

1. **LangGraph agents** — Haystack НЕ имеет зрелых аналогов: persistent state, checkpointing, token-level streaming, mature HITL. Наш RAG agent (43 фазы) использует всё это [exp]
2. **Deep Agents SDK** — planning, filesystem, subagents. У Haystack нет аналога [docs]
3. **700+ интеграций** — Qdrant, Claude, sentence-transformers, pymorphy3 — все работают [web]
4. **Middleware (v1.0)** — SummarizationMiddleware, Human-in-the-loop middleware — мы используем [exp]
5. **Миграция нецелесообразна** — 43 фазы + 1012 chunks indexed + production API [exp]

### Объективные данные (из бенчмарков)

Haystack объективно лучше по метрикам:
- 1.7x меньше framework overhead [web: AIMultiple]
- 35% меньше токенов [web: AIMultiple]
- Стабильнее ответы (ниже std deviation) [web: Tonic.ai]
- Лучше документация [web: Tonic.ai]

Но эти преимущества не перевешивают зрелость агентной оркестровки LangGraph.

## Последствия

### Положительные
- Зрелая агентная архитектура (StateGraph, checkpointing, HITL)
- Огромная экосистема интеграций (700+)
- Активная разработка (LangGraph v1.0, Deep Agents SDK)
- Большое сообщество (туториалы, StackOverflow, Reddit)

### Отрицательные
- Больший framework overhead (~10ms vs ~5.9ms Haystack)
- Больше потребление токенов (~2.4k vs ~1.57k Haystack)
- Глубокие стеки абстракций (5+ слоёв при отладке)
- Зависимость от LangSmith для мониторинга production

### Уроки из Haystack (actionable)

| Урок от Haystack | Что делать у нас | Где |
|------------------|------------------|-----|
| Typed I/O validation | Валидация config при старте pipeline | `config.py`, `pipeline.py` |
| Component-level testing | Каждая Strategy тестируется изолированно | `tests/strategies/` |
| YAML serialization | Pipeline config в YAML → reproducible runs | уже частично через `.env` |
| Pipeline snapshots | Error recovery + checkpoints (уже есть через LangGraph) | `agent.py` |
| SuperComponent pattern | Наш SearchManager = аналог SuperComponent | `manager.py` |
| Hayhooks → MCP | Наш MCP server уже делает это (12 tools) | `src/mcp_server/` |

## Альтернативы

1. **Haystack 2.0** — отклонён (незрелые agents, нет persistent state, меньше интеграций)
2. **Vanilla Python + direct API** — отклонён (нужны agents, memory, tool calling, complex orchestration)
3. **DSPy** — рассмотрен как дополнение (Phase 34: DSPy Prompt Optimization — COMPLETE), не замена
4. **Hybrid: Haystack RAG + LangGraph agents** — теоретически возможен, но увеличивает complexity и maintenance

## Связанные файлы фреймворка

- `src/pdf_framework/search/manager.py` — SearchManager (Strategy pattern ~ Haystack Component)
- `src/pdf_framework/agents/rag/agent.py` — RAG Agent (LangGraph — то чего нет у Haystack)
- `src/pdf_framework/config.py` — pydantic-settings конфигурация
- `src/pdf_framework/search/pipelines/` — наши pipeline (section_first, turbo)
- `src/mcp_server/` — MCP server (12 tools ~ Hayhooks pattern)
- `docs/documentation/Lang Chain Docs/` — документация LangChain в проекте

## Сравнение с Haystack + Qdrant

| Аспект | Haystack + Qdrant | Наш PDF Framework + Qdrant |
|--------|-------------------|----------------------------|
| Dense vectors | qdrant-haystack retriever | QdrantStore + EmbeddingEngine |
| BM25 sparse | BM25Retriever (native) | Qdrant sparse vectors + FTS5 fallback |
| Hybrid fusion | Haystack reciprocal rank | Qdrant native RRF + graph merge |
| Reranking | Component в pipeline | LLM Reranker (Claude Sonnet) |
| Graph | Нет (нужен отдельный) | NetworkX GraphRAG + LightRAG |
