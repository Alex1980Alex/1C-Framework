# P1 — Качество поиска

**Effort:** 7-10 дней | **Impact:** HIGH | **Phases:** 47-50
**Зависимости:** P0 (CI/CD + tests для валидации)

---

## Q1 — Embedding Upgrade (Phase 47)

**Текущее:** `intfloat/multilingual-e5-large` (2022, MTEB ~63%, 1024d). Prefix: "query: " / "passage: ". Provider: `LocalEmbeddingProvider` в `src/pdf_framework/embeddings/providers/local.py`. ONNX/OpenVINO backend (Phase 43).
**Gap:** Устарел на 2 поколения. MTEB лидеры 2025-2026: NV-Embed-v2 (72.3%), Jina-v3 (68.5%), BGE-M3 (67.5%).
**Целевая модель:** `jinaai/jina-embeddings-v3` — 1024d, Late Chunking support, MTEB 68.5%, multilingual.

### Q1.1 Benchmark текущей модели

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q1.1.1 | Создать benchmark script (recall@5, recall@10, MRR) | `scripts/embedding_benchmark.py` | ~80 | Запуск с E5 |
| Q1.1.2 | Подготовить evaluation dataset (50 Q&A pairs) | `data/eval/embedding_benchmark.json` | ~200 | JSON valid |
| Q1.1.3 | Зафиксировать baseline метрики E5 | `data/eval/embedding_baseline.json` | — | Файл сохранён |

**Acceptance:** Baseline метрики записаны для сравнения.

---

### Q1.2 Добавить Jina-v3 provider

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q1.2.1 | Создать `JinaEmbeddingProvider(BaseEmbeddingProvider)` | `src/pdf_framework/embeddings/providers/jina.py` | ~100 | Unit test |
| Q1.2.2 | Реализовать `embed_texts()` с task-type prompting | Тот же файл | ~30 | "retrieval.query" / "retrieval.passage" |
| Q1.2.3 | Реализовать `embed_batch()` с batch_size=256 | Тот же файл | ~20 | Батчинг работает |
| Q1.2.4 | Добавить dimension truncation (1024 → 512/256) | Тот же файл | ~15 | matryoshka dimensions |
| Q1.2.5 | Конфиг: `EMBEDDING__PROVIDER=jina` | `src/pdf_framework/config/embedding.py` | +3 | Config загружается |
| Q1.2.6 | Конфиг: `EMBEDDING__JINA_API_KEY` (если API) | `src/pdf_framework/config/embedding.py` | +2 | — |
| Q1.2.7 | Factory: `create_embedding_provider()` → jina | `src/pdf_framework/embeddings/__init__.py` | +5 | Provider создаётся |
| Q1.2.8 | Unit test: embed single text | `tests/unit/embeddings/test_jina.py` | ~30 | Вектор 1024d |
| Q1.2.9 | Unit test: batch embed + truncation | `tests/unit/embeddings/test_jina.py` | ~30 | Batch корректен |

**Acceptance:** `EMBEDDING__PROVIDER=jina` — embed работает, 1024d вектора.

---

### Q1.3 Migration pipeline

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q1.3.1 | Скрипт миграции: re-embed all chunks | `scripts/migrate_embeddings.py` | ~60 | Все чанки переэмбеддены |
| Q1.3.2 | Recreate Qdrant collection (new dims если отличаются) | Тот же скрипт | ~30 | Collection пересоздана |
| Q1.3.3 | Rebuild BM25 sparse vectors | Тот же скрипт | ~10 | BM25 индекс обновлён |
| Q1.3.4 | Rebuild graph entity embeddings | Тот же скрипт | ~10 | LightRAG collection обновлена |
| Q1.3.5 | Benchmark: сравнение E5 vs Jina-v3 | `scripts/embedding_benchmark.py` | — | recall@10 improvement > 3% |
| Q1.3.6 | Обновить `.env.example` и docs | `docs/guides/migration.md` | +20 | Инструкция миграции |

**Acceptance:** recall@10 улучшение ≥3%. Все индексы обновлены.

---

## Q2 — Late Chunking (Phase 48)

**Текущее:** Chunking до embedding. Каждый чанк теряет контекст документа.
**Gap:** Jina Late Chunking — embed full doc, затем chunk embeddings. Сохраняет cross-chunk контекст.
**Зависимость:** Q1 (Jina-v3 поддерживает Late Chunking нативно).

### Q2.1 Late Chunking strategy

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q2.1.1 | Изучить Jina Late Chunking API | Research | — | Документация прочитана |
| Q2.1.2 | Создать `LateChunkingEmbedder` | `src/pdf_framework/embeddings/late_chunking.py` | ~80 | Unit test |
| Q2.1.3 | Реализовать: full-doc embed → split by token spans | Тот же файл | ~40 | Chunk embeddings корректны |
| Q2.1.4 | Реализовать: fallback на обычный embed для коротких | Тот же файл | ~15 | Short docs обрабатываются |
| Q2.1.5 | Конфиг: `EMBEDDING__LATE_CHUNKING=true/false` | `src/pdf_framework/config/embedding.py` | +2 | Toggle работает |

---

### Q2.2 Integration с pipeline

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q2.2.1 | Модифицировать indexer: late chunking path | `src/pdf_framework/indexing/indexer.py` | +20 | Индексация с late chunking |
| Q2.2.2 | Модифицировать pipeline: chunk boundaries → spans | `src/pdf_framework/processing/pipeline.py` | +15 | Spans сохраняются |
| Q2.2.3 | Benchmark: regular vs late chunking recall@10 | `scripts/embedding_benchmark.py` | +30 | Improvement measured |
| Q2.2.4 | Unit test: late chunking split | `tests/unit/embeddings/test_late_chunking.py` | ~50 | Token spans корректны |
| Q2.2.5 | Integration test: index with late chunking | `tests/integration/test_late_chunking.py` | ~40 | Full pipeline works |

**Acceptance:** Late chunking даёт +2-5% recall@10 на тестовом датасете.

---

## Q3 — LLM Token Streaming (Phase 49)

**Текущее:** SSE streaming уже реализован! `StreamingRAGRunner` в `agents/rag/streaming.py`. Endpoints: `/chat/message`, `/search/ask-stream`, `/v1/chat/completions`. Типы: TOKEN, SOURCE, STATUS, ERROR, DONE.
**Gap:** Нет SSE для основного `/search/ask`. Chat использует SSE, но search — batch JSON.

### Q3.1 Унификация streaming

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q3.1.1 | Добавить SSE mode в `/search/ask` (параметр `stream=true`) | `src/api/routes/search.py` | +30 | curl с Accept: text/event-stream |
| Q3.1.2 | Reuse StreamingRAGRunner для search endpoint | `src/api/routes/search.py` | +10 | Токен streaming работает |
| Q3.1.3 | Добавить SSE mode в MCP `ask_question` tool | `src/mcp_server/server.py` | +20 | MCP streaming |
| Q3.1.4 | Клиентский пример: JavaScript EventSource | `docs/api/streaming-example.md` | ~40 | Документация |
| Q3.1.5 | Клиентский пример: Python httpx-sse | Тот же файл | ~30 | Документация |

---

### Q3.2 WebSocket upgrade

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q3.2.1 | Добавить WebSocket endpoint `/ws/search` | `src/api/routes/websocket.py` | ~80 | WS connection opens |
| Q3.2.2 | Реализовать bidirectional: query → stream results | Тот же файл | ~40 | Результаты стримятся |
| Q3.2.3 | Реализовать: cancel in-flight request | Тот же файл | ~20 | Cancel прерывает |
| Q3.2.4 | Регистрация WebSocket route в app.py | `src/api/app.py` | +3 | Route доступен |
| Q3.2.5 | Unit test: WS connect + message | `tests/unit/api/test_websocket.py` | ~40 | Unit test |

**Acceptance:** `/search/ask?stream=true` стримит токены. WebSocket `/ws/search` работает.

---

### Q3.3 Streaming optimization

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q3.3.1 | Добавить flush для первого токена (TTFT) | `src/pdf_framework/agents/rag/streaming.py` | +5 | TTFT < 500ms |
| Q3.3.2 | Добавить progress events (retrieval %, grading %) | Тот же файл | +15 | Progress видны |
| Q3.3.3 | Добавить source streaming (не ждать конца) | Тот же файл | +10 | Sources приходят рано |

**Acceptance:** Time-to-first-token < 500ms. Progress events отображаются.

---

## Q4 — Contextual Retrieval (Phase 50)

**Текущее:** Чанки индексируются как есть. Header propagation добавляет section_title. Но чанк без контекста документа.
**Gap:** Anthropic Contextual Retrieval — LLM добавляет 1-2 предложения контекста к каждому чанку перед embedding.

### Q4.1 Context generator

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q4.1.1 | Создать `ContextualRetrieval` class | `src/pdf_framework/processing/contextual_retrieval.py` | ~100 | Unit test |
| Q4.1.2 | Реализовать: full-doc + chunk → LLM → context prefix | Тот же файл | ~40 | Context генерируется |
| Q4.1.3 | Реализовать: batch processing (N chunks parallel) | Тот же файл | ~30 | Параллельный вызов |
| Q4.1.4 | Реализовать: кеш контекстов (SQLite) | Тот же файл | ~30 | Повторный вызов из кеша |
| Q4.1.5 | Prompt template: "Given the document about X, this chunk is about..." | Тот же файл | ~15 | Prompt корректен |
| Q4.1.6 | Ralph Wiggum: retry on bad context (too short, irrelevant) | Тот же файл | ~20 | Self-correction |
| Q4.1.7 | Конфиг: `FEATURES__CONTEXTUAL_RETRIEVAL=true/false` | `src/pdf_framework/config/features.py` | +3 | Toggle |
| Q4.1.8 | Конфиг: `FEATURES__CONTEXTUAL_MODEL=claude-haiku-4-5` | `src/pdf_framework/config/features.py` | +2 | Haiku для экономии |

---

### Q4.2 Pipeline integration

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q4.2.1 | Вызвать ContextualRetrieval в pipeline (после split) | `src/pdf_framework/processing/pipeline.py` | +10 | Chunks обогащены |
| Q4.2.2 | Хранить original_content + contextual_content | `src/pdf_framework/schemas/document.py` | +2 | Schema обновлена |
| Q4.2.3 | Embed contextual_content (не original) | `src/pdf_framework/indexing/indexer.py` | +5 | Правильный контент |
| Q4.2.4 | BM25 index: contextual_content для body | `src/pdf_framework/search/bm25_store.py` | +5 | BM25 использует контекст |
| Q4.2.5 | Display: original_content в результатах (без prefix) | `src/pdf_framework/agents/rag/nodes/` | +3 | Юзер видит чистый текст |

---

### Q4.3 Cost optimization

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| Q4.3.1 | Prompt caching (Anthropic): передать full-doc как cache_control | Тот же файл | +10 | Cache hit для 2+ chunks |
| Q4.3.2 | Batch concurrency limiter (max 10 parallel LLM calls) | Тот же файл | +5 | Не больше 10 |
| Q4.3.3 | Skip context for short chunks (< 50 tokens) | Тот же файл | +5 | Short chunks не обогащаются |
| Q4.3.4 | Benchmark: with vs without contextual retrieval | `scripts/embedding_benchmark.py` | +30 | recall improvement measured |

**Acceptance:** Contextual retrieval даёт +5-10% recall@10. Стоимость обогащения: ~$0.01/page (Haiku).

---

## Чеклист завершения P1

- [x] Jina-v3 provider работает, `EMBEDDING__PROVIDER=jina` (Phase 47 — JinaEmbeddingEngine + factory + config)
- [x] Migration script переиндексирует все чанки (Phase 47 — scripts/migrate_embeddings.py)
- [x] Benchmark script (recall@5/10, MRR, NDCG) (Phase 47 — scripts/embedding_benchmark.py + --contextual flag)
- [x] Evaluation dataset 50 Q&A pairs (data/eval/embedding_benchmark.json)
- [x] .env.example + migration.md обновлены (Jina setup + migration instructions)
- [x] recall@10 benchmark запущен (E5: 0.9933 vs Jina: 0.9733 — E5 лучше на простом датасете, потолок ~100%)
- [x] Late Chunking опционально включается (Phase 48 — `EMBEDDING__LATE_CHUNKING=true`, windowed, 7 unit tests)
- [x] `/search/ask?stream=true` стримит токены (Phase 49 — SSE with early sources + progress)
- [x] WebSocket `/ws/search` работает (Phase 49 — bidirectional, cancel support)
- [x] TTFT (Time To First Token) метрика в SSE и WebSocket (Phase 49 — ttft event + done metadata)
- [x] Клиентские примеры JS/Python для SSE и WebSocket (docs/api/streaming-example.md)
- [~] MCP ask_question SSE (deferred — MCP протокол не поддерживает streaming tool results)
- [x] Contextual Retrieval генерирует context prefix (Phase 50 — SQLite cache, batch, prompt caching)
- [x] BM25 и vector используют contextual content (Phase 50 — indexer.py + bm25_store)
- [x] Benchmark contextual vs non-contextual (--contextual flag в embedding_benchmark.py)
- [x] All new code покрыт unit tests (35 tests: 9 contextual + 5 websocket + 21 jina+late_chunking)
