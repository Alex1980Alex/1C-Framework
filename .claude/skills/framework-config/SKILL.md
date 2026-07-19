---
name: framework-config
description: "Переменные окружения PDF Vector Framework (.env pdf-framework). ТОЛЬКО при: ANTHROPIC__API_KEY, EMBEDDING__MODEL, QDRANT__URL, .env pdf-framework, профиль конфигурации pdf-framework. НЕ для Claude Code settings (→ claude-code-settings), НЕ для 1С, НЕ для LangChain."
---

# Framework Configuration — все .env параметры

> **Phase 8 defaults aligned (2026-05-01, §2.1):** `EmbeddingSettings`/`VectorStoreSettings` no-env defaults теперь production: `EMBEDDING__PROVIDER=tei`, `MODEL=Qwen/Qwen3-Embedding-8B`, `DIMENSIONS=4096`; `VECTOR_STORE__DIMENSIONS=4096`. Новые поля: `EMBEDDING__TEI_BASE_URL`, `EMBEDDING__TEI_CLIENT_BATCH`. Regression: `tests/unit/test_config.py::test_phase8_invariants`.

## Когда использовать
- "как настроить .env", "какие переменные окружения", "конфигурация фреймворка"
- "ANTHROPIC__API_KEY", "EMBEDDING__MODEL", "какой профиль выбрать"
- Любые вопросы о параметрах запуска и настройки

---

## Обязательные параметры (минимум для старта)

```env
ANTHROPIC__API_KEY=your-anthropic-api-key
VECTOR_STORE__QDRANT_URL=http://localhost:6333
```

---

## Все параметры по категориям

### LLM

| Переменная | Default | Описание |
|------------|---------|----------|
| `AGENT__MODEL` | `claude-opus-4-8` | Основная модель (ответы, агенты) |
| `AGENT__FAST_MODEL` | `claude-sonnet-4-5-20250929` | Быстрая модель (grading, rewriting) |
| `ANTHROPIC__BASE_URL` | `https://api.anthropic.com` | Base URL API (для proxy) |
| `AGENT__TEMPERATURE` | `0.0` | Температура генерации |

### Embedding (Phase 8 production switchover, 2026-04-30)

| Переменная | Default | Описание |
|------------|---------|----------|
| `EMBEDDING__PROVIDER` | `tei` | **Production default**: TEI HTTP. Альтернативы: `local`/`jina`/`giga` |
| `EMBEDDING__MODEL` | `Qwen/Qwen3-Embedding-8B` | **Production default**. Legacy E5 — `intfloat/multilingual-e5-large` |
| `EMBEDDING__DIMENSIONS` | `4096` | **Production**: 4096 (Qwen3). Legacy: 1024 (E5/MRL) или 768 (nomic в memory hooks) |
| `EMBEDDING__TEI_BASE_URL` | `http://localhost:8080` | TEI Docker (`pdf-rag-tei` контейнер) |
| `EMBEDDING__BATCH_SIZE` | `16` | Размер batch на TEI request (sub-batched на 32 server-cap) |
| `EMBEDDING__DEVICE` | `auto` | Для local backend: `cuda` для Qwen3-8B на 16+ GB VRAM |
| `EMBEDDING__DTYPE` | — | Для local: `float16` на 24GB GPU; bf16 fallback на CPU |
| `QWEN3_MODEL_DIR` | `D:/hf-manual/Qwen3-Embedding-8B` | Bind-mount path для TEI Docker (Phase 8.12.6); локальные веса 14.1 GiB |
| `ZAI_API_KEY` | — | Z.AI API key (через `LLMRotationService`) |

> **Qwen3-Embedding-8B** (production default): query instruction `"Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "`; passages — без prefix. Через TEI HTTP (см. `src/framework_search/embedder.py` или `Qwen3TEIEmbedder` из `scripts/reindex_bsl_qwen3.py`).
>
> **E5 модели** (legacy, до Phase 8): prefix `"query: "` / `"passage: "` (auto).

### Vector Store

| Переменная | Default | Описание |
|------------|---------|----------|
| `VECTOR_STORE__PROVIDER` | `qdrant` | Провайдер: `qdrant` / `chroma` / `pgvector` |
| `VECTOR_STORE__QDRANT_URL` | `http://localhost:6333` | URL Qdrant |
| `VECTOR_STORE__QDRANT_COLLECTION` | `pdf_documents` | Имя коллекции |
| `VECTOR_STORE__QDRANT_BM25_ENABLED` | `true` | BM25 sparse vectors в Qdrant |
| `VECTOR_STORE__QDRANT_BM25_LANGUAGE` | `russian` | Язык BM25 |

### Search

| Переменная | Default | Описание |
|------------|---------|----------|
| `SEARCH__HYBRID_VECTOR_WEIGHT` | `0.6` | Вес vector в hybrid |
| `SEARCH__HYBRID_GRAPH_WEIGHT` | `0.4` | Вес graph в hybrid |
| `SEARCH__HYBRID_RRF_K` | `60` | RRF smoothing parameter |
| `SEARCH__MMR_DIVERSITY` | `0.3` | MMR diversity (0.0-1.0) |
| `SEARCH__QUERY_EXPANSION_ENABLED` | `false` | HyDE query expansion |
| `SEARCH__BM25_DB_PATH` | `data/bm25_index.db` | Путь к BM25 SQLite |
| `SEARCH__BM25_BACKEND` | `qdrant` | Backend: `qdrant` / `fts5` / `both` |

### Reranking

| Переменная | Default | Описание |
|------------|---------|----------|
| `AGENT__RERANKER_ENABLED` | `true` | Включить reranking |
| `AGENT__RERANKER_TYPE` | `llm` | Тип: `llm` / `cross_encoder` / `flashrank` / `colbert` |
| `AGENT__RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Модель (для cross_encoder) |
| `AGENT__RERANKER_TOP_K` | `20` | Кандидаты для reranking |

### Self-RAG

| Переменная | Default | Описание |
|------------|---------|----------|
| `SELF_RAG__ENABLED` | `true` | Включить Self-RAG agent |
| `SELF_RAG__GRADING_MODEL` | `claude-sonnet-4-5-20250929` | Модель grading |
| `SELF_RAG__RELEVANCE_THRESHOLD` | `0.5` | Порог релевантности |
| `SELF_RAG__MAX_REWRITE_ATTEMPTS` | `2` | Макс. попыток rewrite |

### GraphRAG

| Переменная | Default | Описание |
|------------|---------|----------|
| `GRAPH_RAG__COMMUNITY_DETECTION` | `true` | Community detection |
| `GRAPH_RAG__COMMUNITY_ALGORITHM` | `leiden` | Алгоритм |
| `GRAPH_RAG__LOCAL_SEARCH_K` | `10` | Количество для local search |
| `GRAPH_RAG__GLOBAL_MAP_LLM` | `claude-haiku-4-5-20251001` | Map модель |
| `GRAPH_RAG__GLOBAL_REDUCE_LLM` | `claude-sonnet-4-5-20250929` | Reduce модель |

### Two-Stage Pipeline

| Переменная | Default | Описание |
|------------|---------|----------|
| `TWO_STAGE__ENABLED` | `true` | Включить |
| `TWO_STAGE__FIRST_STAGE_K` | `50` | Кандидаты 1-го этапа |
| `TWO_STAGE__RERANKER` | `flashrank` | Reranker 1-го этапа |
| `TWO_STAGE__RERANKER_MODEL` | `ms-marco-MiniLM-L-6-v2` | Модель |
| `TWO_STAGE__CONTEXTUAL_RETRIEVAL` | `false` | Contextual Retrieval |

### Adaptive RAG

| Переменная | Default | Описание |
|------------|---------|----------|
| `ADAPTIVE__ROUTING_ENABLED` | `true` | Включить |
| `ADAPTIVE__CLASSIFIER_MODEL` | `claude-haiku-4-5-20251001` | Классификатор |
| `ADAPTIVE__DECOMPOSE_THRESHOLD` | `complex` | Порог декомпозиции |

### Parent-Child Retrieval

| Переменная | Default | Описание |
|------------|---------|----------|
| `PARENT_CHILD__ENABLED` | `true` | Включить |
| `PARENT_CHILD__PARENT_SIZE` | `2000` | Размер parent chunk |
| `PARENT_CHILD__CHILD_SIZE` | `400` | Размер child chunk |
| `PARENT_CHILD__MERGE_THRESHOLD` | `3` | Порог merge |

### Conversational RAG

| Переменная | Default | Описание |
|------------|---------|----------|
| `CONVERSATION__MAX_HISTORY` | `10` | Макс. сообщений в истории |
| `CONVERSATION__STORAGE` | `sqlite` | Хранилище |
| `CONVERSATION__DB_PATH` | `data/conversations.db` | Путь к БД |

### RAPTOR & HyDE

| Переменная | Default | Описание |
|------------|---------|----------|
| `RAPTOR__ENABLED` | `true` | Включить RAPTOR |
| `RAPTOR__MAX_LEVELS` | `4` | Максимум уровней |
| `RAPTOR__CLUSTERING_MODEL` | `kmeans` | Кластеризация |
| `RAPTOR__SUMMARY_MODEL` | `claude-haiku-4-5-20251001` | Модель summary |
| `SUMMARY_INDEX__ENABLED` | `true` | Summary index |
| `SUMMARY_INDEX__MIN_CHUNKS` | `10` | Мин. чанков для summary |

### PDF Processing

| Переменная | Default | Описание |
|------------|---------|----------|
| `PDF__CHUNK_SIZE` | `1000` | Размер chunk |
| `PDF__CHUNK_OVERLAP` | `200` | Overlap |
| `PDF__SPLITTER` | `recursive` | Splitter: `recursive` / `semantic` |
| `PDF__LOADER` | `hybrid` | Loader: `hybrid` / `pymupdf4llm` / `docling` |

### Vision (Images)

| Переменная | Default | Описание |
|------------|---------|----------|
| `VISION__MODEL` | `claude-sonnet-4-5-20250929` | Модель Vision |
| `VISION__MAX_TOKENS` | `2048` | Макс. токенов |
| `VISION__MIN_IMAGE_SIZE` | `50` | Мин. размер изображения (px) |

### Caching

| Переменная | Default | Описание |
|------------|---------|----------|
| `CACHE__SEMANTIC_ENABLED` | `true` | Семантический кеш |
| `CACHE__SEMANTIC_THRESHOLD` | `0.95` | Порог совпадения |
| `CACHE__SEMANTIC_TTL` | `3600` | TTL в секундах |
| `CACHE__EMBEDDING_ENABLED` | `true` | Embedding кеш |
| `CACHE__LLM_ENABLED` | `true` | LLM кеш |

### Indexing

| Переменная | Default | Описание |
|------------|---------|----------|
| `INDEXING__INCREMENTAL` | `true` | Инкрементальная индексация |
| `INDEXING__WATCH_ENABLED` | `false` | File watcher |
| `INDEXING__WATCH_DIR` | `data/pdfs` | Директория для watch |

### Observability

| Переменная | Default | Описание |
|------------|---------|----------|
| `OBSERVABILITY__TRACER` | `jsonfile` | Tracer: `jsonfile` / `langfuse` |
| `OBSERVABILITY__TRACE_DIR` | `data/traces` | Директория трейсов |
| `LANGFUSE__ENABLED` | `false` | Langfuse |
| `LANGFUSE__PUBLIC_KEY` | — | Public key |
| `LANGFUSE__SECRET_KEY` | — | Secret key |
| `LANGFUSE__HOST` | `https://cloud.langfuse.com` | Host |

### Auth & Rate Limiting

| Переменная | Default | Описание |
|------------|---------|----------|
| `AUTH__ENABLED` | `true` | JWT авторизация |
| `AUTH__JWT_SECRET` | — | Secret key (мин. 32 символа) |
| `AUTH__JWT_EXPIRATION_HOURS` | `24` | Срок жизни токена |
| `RATE_LIMIT__ENABLED` | `true` | Rate limiting |
| `RATE_LIMIT__REQUESTS_PER_MINUTE` | `60` | Лимит запросов/мин |
| `RATE_LIMIT__BURST` | `10` | Burst |

### Guardrails (Phase 53)

| Переменная | Default | Описание |
|------------|---------|----------|
| `GUARDRAILS__PII_MODE` | `detect` | PII: `detect` / `redact` / `block` |
| `GUARDRAILS__INJECTION_MODE` | `warn` | Injection: `log` / `warn` / `block` |
| `GUARDRAILS__INJECTION_THRESHOLD` | `0.7` | Порог срабатывания (0.0-1.0) |
| `GUARDRAILS__MAX_QUERY_LENGTH` | `10000` | Макс. длина запроса |
| `GUARDRAILS__MAX_FILE_SIZE_BYTES` | `104857600` | Макс. размер файла (100MB) |

### LightRAG (Phase 38)

| Переменная | Default | Описание |
|------------|---------|----------|
| `LIGHTRAG__ENABLED` | `true` | Включить LightRAG |
| `LIGHTRAG__SIMILARITY_THRESHOLD` | `0.7` | Порог similarity |
| `LIGHTRAG__MAX_ENTITIES` | `50` | Макс. entities |

### External Sources / Web Search (Phase 37)

| Переменная | Default | Описание |
|------------|---------|----------|
| `EXTERNAL__TAVILY_API_KEY` | — | API key для Tavily |
| `EXTERNAL__SEARCH_PROVIDER` | `tavily` | Провайдер: `tavily` / `serpapi` / `duckduckgo` |
| `EXTERNAL__MAX_RESULTS` | `5` | Макс. результатов web search |

### Visual Search / ColPali (Phase 55)

| Переменная | Default | Описание |
|------------|---------|----------|
| `VISUAL_SEARCH__ENABLED` | `false` | Включить visual search |
| `VISUAL_SEARCH__MODEL` | `vidore/colpali-v1.3` | Модель ColPali |
| `VISUAL_SEARCH__RENDER_DPI` | `150` | DPI рендеринга страниц PDF |

### Optimization / DSPy (Phase 34)

| Переменная | Default | Описание |
|------------|---------|----------|
| `OPTIMIZATION__DSPY_MODEL` | — | Модель для DSPy |
| `OPTIMIZATION__MIPRO_TRIALS` | `10` | Количество trials MIPROv2 |

### Async Queue / Workers (Phase 59)

| Переменная | Default | Описание |
|------------|---------|----------|
| `QUEUE__REDIS_URL` | `redis://localhost:6379` | Redis URL для ARQ |
| `QUEUE__MAX_JOBS` | `10` | Макс. параллельных задач |
| `QUEUE__JOB_TIMEOUT` | `3600` | Таймаут задачи (секунды) |

### PDF Loaders (Phase 15.1 / 28)

| Переменная | Default | Описание |
|------------|---------|----------|
| `DOCLING__ENABLED` | `false` | Включить IBM Docling OCR |
| `DOCLING__OCR_LANG` | `ru` | Язык OCR |
| `HYBRID_LOADER__LEVELS` | `4` | Уровней каскада (L1-L4) |
| `SMART_ROUTER__ENABLED` | `true` | Smart auto-selection загрузчика |

---

## Профили конфигурации

### Dev (быстрый старт)

```env
ANTHROPIC__API_KEY=sk-...
VECTOR_STORE__QDRANT_URL=http://localhost:6333
AGENT__MODEL=claude-sonnet-4-5-20250929
AGENT__RERANKER_TYPE=flashrank
CACHE__SEMANTIC_ENABLED=false
AUTH__ENABLED=false
```

### Production

```env
ANTHROPIC__API_KEY=sk-...
VECTOR_STORE__QDRANT_URL=http://qdrant:6333
AGENT__MODEL=claude-opus-4-8
AGENT__RERANKER_TYPE=llm
CACHE__SEMANTIC_ENABLED=true
AUTH__ENABLED=true
RATE_LIMIT__ENABLED=true
LANGFUSE__ENABLED=true
```

### Max Quality

```env
AGENT__MODEL=claude-opus-4-8
AGENT__RERANKER_TYPE=llm
SELF_RAG__ENABLED=true
GRAPH_RAG__COMMUNITY_DETECTION=true
RAPTOR__ENABLED=true
TWO_STAGE__CONTEXTUAL_RETRIEVAL=true
PARENT_CHILD__ENABLED=true
```

---

## Связанные скиллы

- `search-pipeline-debug` — параметры поиска и RRF
- `deployment` — Docker, health checks, запуск серверов
- `framework-troubleshooting` — ошибки конфигурации

## Файлы

- Конфигурация: [_base.py](src/pdf_framework/config/_base.py), [__init__.py](src/pdf_framework/config/__init__.py)
- Settings: [agent.py](src/pdf_framework/config/agent.py), [embedding.py](src/pdf_framework/config/embedding.py)
- Features: [features.py](src/pdf_framework/config/features.py), [graphrag.py](src/pdf_framework/config/graphrag.py)
- Пример: [.env.example](.env.example)
