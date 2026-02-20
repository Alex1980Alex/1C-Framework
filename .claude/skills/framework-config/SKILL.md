---
name: framework-config
description: "Конфигурация PDF Framework через .env. Триггеры: 'настройка', 'конфигурация', '.env', 'переменная окружения', 'config', 'environment', 'профиль', 'configure', 'settings'. НЕ для кода конфигурации — для этого используй operational skills."
---

# Framework Configuration — все .env параметры

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
| `AGENT__MODEL` | `claude-opus-4-6` | Основная модель (ответы, агенты) |
| `AGENT__FAST_MODEL` | `claude-sonnet-4-5-20250929` | Быстрая модель (grading, rewriting) |
| `ANTHROPIC__BASE_URL` | `https://api.anthropic.com` | Base URL API (для proxy) |
| `AGENT__TEMPERATURE` | `0.0` | Температура генерации |

### Embedding

| Переменная | Default | Описание |
|------------|---------|----------|
| `EMBEDDING__MODEL` | `intfloat/multilingual-e5-large` | Модель эмбеддингов |
| `EMBEDDING__DIMENSIONS` | `1024` | Размерность (должна соответствовать модели) |

> E5 модели требуют prefix: `"query: "` для запросов, `"passage: "` для индексации (добавляется автоматически).

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
| `SELF_RAG__GRADER_MODEL` | `claude-haiku-4-5-20251001` | Модель grading |
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
AGENT__MODEL=claude-opus-4-6
AGENT__RERANKER_TYPE=llm
CACHE__SEMANTIC_ENABLED=true
AUTH__ENABLED=true
RATE_LIMIT__ENABLED=true
LANGFUSE__ENABLED=true
```

### Max Quality

```env
AGENT__MODEL=claude-opus-4-6
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


## Незадокументированные Config Variables (.env)

```env
AGENT__SEARCH_K=
AGENT__COLBERT_MODEL=
AGENT__RERANKER_LLM_MODEL=
AGENT__CHECKPOINTER=
AGENT__GRAPH_CONCURRENCY=
AGENT__COST_BUDGET_PER_QUERY=
AGENT__COST_BUDGET_DAILY=
SELF_RAG__GRADING_MODEL=
SELF_RAG__SCORE_PREFILTER_THRESHOLD=
SELF_RAG__MAX_RETRIES=
SELF_RAG__HALLUCINATION_CHECK_ENABLED=
SELF_RAG__MAX_GENERATION_ATTEMPTS=
SELF_RAG__MAX_CONTEXT_CHARS=
SELF_RAG__STRATEGY_ESCALATION_ENABLED=
SELF_RAG__ENRICHMENT_ENABLED=
SELF_RAG__ENRICHMENT_MAX_ROUNDS=
SELF_RAG__ENRICHMENT_SUB_QUERIES=
SELF_RAG__ENRICHMENT_K=
DEEP_RESEARCH__MAX_SUB_QUESTIONS=
DEEP_RESEARCH__MAX_RETRIEVAL_STEPS=
EMBEDDING__BATCH_SIZE=
EMBEDDING__CACHE_ENABLED=
EMBEDDING__CACHE_DIR=
EMBEDDING__DEVICE=
EMBEDDING__BACKEND=
EMBEDDING__JINA_API_KEY=
EMBEDDING__JINA_TASK=
EMBEDDING__JINA_TRUNCATE_DIM=
EMBEDDING__LATE_CHUNKING=
EMBEDDING__LATE_CHUNKING_MAX_TOKENS=
EXTERNAL__WEB_SEARCH_ENABLED=
EXTERNAL__SERPAPI_KEY=
EXTERNAL__CONFIDENCE_THRESHOLD=
EXTERNAL__WEB_TRUST_SCORE=
OPTIMIZATION__DATASET_PATH=
OPTIMIZATION__OPTIMIZED_DIR=
OPTIMIZATION__MAX_TRIALS=
PARENT_CHILD__PARENT_CHUNK_SIZE=
PARENT_CHILD__PARENT_CHUNK_OVERLAP=
PARENT_CHILD__CHILD_CHUNK_SIZE=
PARENT_CHILD__CHILD_CHUNK_OVERLAP=
PARENT_CHILD__FETCH_MULTIPLIER=
PARENT_CHILD__PARENT_STORE_PATH=
ADAPTIVE__CLASSIFIER_CACHE_ENABLED=
ADAPTIVE__DECOMPOSITION_ENABLED=
ADAPTIVE__MAX_SUB_QUESTIONS=
ADAPTIVE__ROUTE_SIMPLE_STRATEGY=
ADAPTIVE__ROUTE_MODERATE_STRATEGY=
ADAPTIVE__ROUTE_COMPLEX_STRATEGY=
ADAPTIVE__ROUTE_THEMATIC_STRATEGY=
ADAPTIVE__FAST_CLASSIFY_ENABLED=
ADAPTIVE__BM25_EARLY_TERMINATION=
ADAPTIVE__BM25_EARLY_THRESHOLD=
ADAPTIVE__PARALLEL_DECOMPOSITION=
ADAPTIVE__PARALLEL_EXPANSION=
CONVERSATION__MEMORY_BACKEND=
CONVERSATION__AUTO_CLEANUP_DAYS=
CONVERSATION__REFORMULATION_ENABLED=
CONVERSATION__REFORMULATION_MODEL=
LAYOUT__LAYOUT_DETECTION_ENABLED=
LAYOUT__LAYOUT_PROVIDER=
LAYOUT__LAYOUT_STRATEGY=
LAYOUT__INFER_TABLE_STRUCTURE=
LAYOUT__EXTRACT_TABLES=
LAYOUT__MIN_TABLE_ROWS=
LAYOUT__MIN_TABLE_COLS=
LAYOUT__EXTRACT_IMAGES=
LAYOUT__IMAGE_DESCRIPTION_MODEL=
LAYOUT__PARSE_TEMPLATE=
LAYOUT__STRUCTURE_AWARE_CHUNK_SIZE=
LAYOUT__STRUCTURE_AWARE_OVERLAP=
RAPTOR__SEARCH_MODE=
RAPTOR__CLUSTER_METHOD=
RAPTOR__SUMMARIZATION_MODEL=
SUMMARY_INDEX__COLLECTION_NAME=
SUMMARY_INDEX__SUMMARIZATION_MODEL=
SUMMARY_INDEX__MIN_CHUNKS_FOR_SUMMARY=
SUGGESTIONS__METHOD=
SUGGESTIONS__CACHE_TTL=
SUGGESTIONS__MAX_SUGGESTIONS=
SUGGESTIONS__LLM_MODEL=
HIERARCHICAL__SECTION_FIRST_ENABLED=
HIERARCHICAL__SUMMARY_ENABLED=
HIERARCHICAL__SUMMARY_DB_PATH=
HIERARCHICAL__CONTEXT_BREADCRUMB=
VISUAL_SEARCH__COLLECTION_NAME=
VISUAL_SEARCH__HYBRID_WEIGHT_VISUAL=
VISUAL_SEARCH__HYBRID_WEIGHT_TEXT=
VISUAL_SEARCH__AUTO_DETECT_ENABLED=
VISUAL_SEARCH__VISUAL_KEYWORDS=
GRAPH_RAG__COMMUNITY_DETECTION_ENABLED=
GRAPH_RAG__LEIDEN_RESOLUTION=
GRAPH_RAG__COMMUNITY_LEVELS=
GRAPH_RAG__SUMMARY_CACHE_ENABLED=
GRAPH_RAG__LOCAL_SEARCH_DEPTH=
GRAPH_RAG__LOCAL_SEARCH_INCLUDE_SUMMARY=
GRAPH_RAG__GLOBAL_SEARCH_MAX_COMMUNITIES=
GRAPH_RAG__GLOBAL_SEARCH_RANK_BY_SIMILARITY=
GRAPH_RAG__GLOBAL_SEARCH_MAP_MODEL=
GRAPH_RAG__GLOBAL_SEARCH_REDUCE_MODEL=
GRAPH_RAG__INCREMENTAL_UPDATES_ENABLED=
GRAPH_RAG__AUTO_UPDATE_ENABLED=
GRAPH_RAG__AUTO_UPDATE_ON_REINDEX=
LIGHT_RAG__COLLECTION_NAME=
LIGHT_RAG__ENTITY_TOP_K=
LIGHT_RAG__RELATION_TOP_K=
LIGHT_RAG__NEIGHBOR_DEPTH=
LIGHT_RAG__MAX_CHUNKS=
LIGHT_RAG__AUTO_SELECT_ENABLED=
LIGHT_RAG__LIGHT_COMPLEXITIES=
LIGHT_RAG__FULL_COMPLEXITIES=
GRAPH_STORE__PERSIST_DIR=
GRAPH_STORE__NEO4J_URI=
GRAPH_STORE__NEO4J_USER=
GRAPH_STORE__NEO4J_PASSWORD=
MCP_SERVER__NAME=
MCP_SERVER__VERSION=
MCP_SERVER__TRANSPORT=
API__PORT=
API__CORS_ORIGINS=
AUTH__JWT_ALGORITHM=
AUTH__TOKEN_EXPIRE_HOURS=
AUTH__DEFAULT_TENANT=
UI__PORT=
UI__SHARE=
UI__THEME=
UI__API_BACKEND_URL=
QUEUE__RETRY_ATTEMPTS=
QUEUE__RETRY_DELAY_SECONDS=
QUEUE__QUEUE_NAME=
QUEUE__HEALTH_CHECK_INTERVAL=
OBSERVABILITY__LANGSMITH_ENABLED=
OBSERVABILITY__LANGFUSE_ENABLED=
OBSERVABILITY__LANGFUSE_PUBLIC_KEY=
OBSERVABILITY__LANGFUSE_SECRET_KEY=
OBSERVABILITY__LANGFUSE_HOST=
OBSERVABILITY__LANGFUSE_PROJECT_NAME=
CACHE__EMBEDDING_TTL_DAYS=
CACHE__EMBEDDING_DB_PATH=
CACHE__LLM_TTL_SECONDS=
CACHE__LLM_DB_PATH=
CACHE__DOCUMENT_ENABLED=
CACHE__DOCUMENT_CACHE_DIR=
CACHE__PROMPT_CACHING_ENABLED=
CACHE__SEMANTIC_TTL_SECONDS=
CACHE__SEMANTIC_MAX_ENTRIES=
CACHE__SEMANTIC_DB_PATH=
FEEDBACK__ASYNC_DB_PATH=
FEEDBACK__FEW_SHOT_MAX_EXAMPLES=
FEEDBACK__FEW_SHOT_SIMILARITY_THRESHOLD=
FEEDBACK__BOOST_MAX=
FEEDBACK__BOOST_MIN_COUNT=
RAGAS_EVAL__EVAL_HISTORY_DB_PATH=
RAGAS_EVAL__REGRESSION_THRESHOLD=
RAGAS_EVAL__BASELINE_PATH=
AUTORAG__MAX_EXPERIMENTS=
AUTORAG__OUTPUT_DIR=
PDF__EXTRACT_TABLES=
PDF__EXTRACT_IMAGES=
PDF__MIN_CHUNK_SIZE=
PDF__MAX_CHUNK_SIZE=
DOCLING__OCR_ENABLED=
DOCLING__OCR_ENGINE=
DOCLING__OCR_LANGUAGES=
DOCLING__FORCE_FULL_PAGE_OCR=
DOCLING__TABLE_STRUCTURE_ENABLED=
DOCLING__TABLE_MODE=
DOCLING__EXTRACT_IMAGES=
DOCLING__GENERATE_PICTURE_IMAGES=
DOCLING__DOCUMENT_TIMEOUT=
DOCLING__LAYOUT_BATCH_SIZE=
DOCLING__OCR_BATCH_SIZE=
DOCLING__TABLE_BATCH_SIZE=
DOCLING__USE_ONNX=
SMART_ROUTER__MIN_TEXT_CHARS_PER_PAGE=
SMART_ROUTER__COMPLEX_LAYOUT_THRESHOLD=
SMART_ROUTER__TABLE_HEAVY_THRESHOLD=
SMART_ROUTER__FAST_LOADER=
SMART_ROUTER__FULL_LOADER=
HYBRID_LOADER__ENABLE_FITZ_TABLES=
HYBRID_LOADER__ENABLE_DOCLING_TABLES=
HYBRID_LOADER__ENABLE_VISION_OCR=
HYBRID_LOADER__VERIFY_COVERAGE=
HYBRID_LOADER__COVERAGE_THRESHOLD=
HYBRID_LOADER__TABLE_DEDUP_ENABLED=
HYBRID_LOADER__TABLE_DEDUP_THRESHOLD=
HYBRID_LOADER__DOCLING_MAX_RETRIES=
HYBRID_LOADER__DOCLING_TABLE_MODE=
HYBRID_LOADER__VISION_MODEL=
HYBRID_LOADER__VISION_MAX_RETRIES=
HYBRID_LOADER__VISION_DPI=
HYBRID_LOADER__VISION_MIN_TEXT_CHARS=
SEARCH__BM25_ENABLED=
SEARCH__BM25_WEIGHT=
SEARCH__BM25_TWO_PASS=
SEARCH__DYNAMIC_WEIGHTING_ENABLED=
SEARCH__MMR_DIVERSITY_LAMBDA=
SEARCH__MMR_FETCH_K=
SEARCH__QUERY_EXPANSION_METHOD=
SEARCH__FLASHRANK_ENABLED=
SEARCH__FLASHRANK_TOKEN_BUDGET=
CONTEXTUAL_RETRIEVAL__MAX_CONTEXT_TOKENS=
CONTEXTUAL_RETRIEVAL__BATCH_CONCURRENCY=
CONTEXTUAL_RETRIEVAL__MIN_CHUNK_TOKENS=
CONTEXTUAL_RETRIEVAL__CACHE_ENABLED=
CONTEXTUAL_RETRIEVAL__CACHE_DB_PATH=
TWO_STAGE__STAGE1_K=
TWO_STAGE__STAGE1_STRATEGY=
TWO_STAGE__STAGE2_RERANK_K=
TWO_STAGE__STAGE2_USE_MMR=
TWO_STAGE__STAGE2_MMR_LAMBDA=
TWO_STAGE__STAGE2_USE_FLASHRANK=
VECTOR_STORE__QDRANT_API_KEY=
VECTOR_STORE__PGVECTOR_DSN=
VECTOR_STORE__PGVECTOR_TABLE_NAME=
VECTOR_STORE__PERSIST_DIR=
VECTOR_STORE__COLLECTION_NAME=
VECTOR_STORE__DISTANCE_METRIC=
VECTOR_STORE__QDRANT_BM25_K=
VECTOR_STORE__QDRANT_BM25_B=
```

## Файлы

- Конфигурация: [_base.py](src/pdf_framework/config/_base.py), [__init__.py](src/pdf_framework/config/__init__.py)
- Settings: [agent.py](src/pdf_framework/config/agent.py), [embedding.py](src/pdf_framework/config/embedding.py)
- Features: [features.py](src/pdf_framework/config/features.py), [graphrag.py](src/pdf_framework/config/graphrag.py)
- Пример: [.env.example](.env.example)
