# Архитектура фреймворка

## Обзор

PDF Vector & Graph Framework построен по принципу **Provider Pattern** с **Dependency Injection**. Все ключевые компоненты определяют абстрактные интерфейсы (ABC), а конкретные реализации подключаются через фабричные функции на основе конфигурации.

## Слои архитектуры

```
┌──────────────────────────────────────────────────────────────┐
│                    Интерфейсный слой                         │
│           CLI  │  REST API  │  MCP Server                    │
├──────────────────────────────────────────────────────────────┤
│                    Слой оркестрации                          │
│  Components (DI) │ SearchManager │ RAG Agent │ Evaluation    │
├──────────────────────────────────────────────────────────────┤
│                    Слой бизнес-логики                        │
│  Loader │ Pipeline │ Indexer │ Chains │ Tools │ Reranking    │
├──────────────────────────────────────────────────────────────┤
│                    Слой хранения                             │
│         ChromaDB (Vector)  │  NetworkX (Graph)               │
├──────────────────────────────────────────────────────────────┤
│                    Инфраструктурный слой                     │
│  Embeddings │ Cache (3 types) │ Logger │ Metrics │ Config    │
└──────────────────────────────────────────────────────────────┘
```

## Ключевые компоненты

### Components (DI-контейнер)

`src/api/dependencies/components.py` — центральная точка сборки всех компонентов.

```python
class Components:
    loader: BaseLoader              # Загрузчик PDF
    pipeline: ProcessingPipeline    # Обработка текста (recursive / semantic splitter)
    embedding_engine: BaseEmbeddingEngine  # Генерация эмбеддингов
    vector_store: BaseVectorStore   # Векторное хранилище
    graph_store: BaseGraphStore     # Графовое хранилище
    indexer: DocumentIndexer        # Оркестратор индексации
    search_manager: SearchManager   # Маршрутизатор поиска (vector, graph, hybrid, mmr, two_stage)
    context_generator: ContextGenerator  # Контекстуальный ретривал (Phase 3.1)
    eval_runner: EvalRunner         # Бенчмарк-раннер (Phase 4)
```

Зарегистрированные стратегии поиска:

| Стратегия | Класс | Описание |
|-----------|-------|----------|
| `vector` | `VectorSearchStrategy` | Cosine similarity через bi-encoder |
| `graph` | `GraphSearchStrategy` | Поиск по графу сущностей |
| `hybrid` | `HybridSearchStrategy` | Vector + Graph с RRF-слиянием |
| `mmr` | `MMRSearchStrategy` | Maximal Marginal Relevance (баланс релевантность/разнообразие) |
| `two_stage` | `TwoStagePipeline` | Двухэтапный пайплайн: broad recall → precise selection |

Дополнительные возможности поиска:
- **Reranking** (Phase 1.1) — CrossEncoder переранжирование (`BAAI/bge-reranker-v2-m3`)
- **Query Expansion** (Phase 2.3) — расширение запросов (LLM / synonyms / HyDE)
- **FlashRank** (Phase 3.2) — выбор по маргинальной полезности в пределах токен-бюджета

Все три интерфейса (CLI, API, MCP) используют `Components` как единую точку доступа к функциональности.

### SearchManager (Маршрутизатор стратегий)

```python
search_manager = SearchManager(agent_settings=..., search_settings=...)
search_manager.register_strategy("vector", VectorSearchStrategy(...))
search_manager.register_strategy("graph", GraphSearchStrategy(...))
search_manager.register_strategy("hybrid", HybridSearchStrategy(...))
search_manager.register_strategy("mmr", MMRSearchStrategy(...))
search_manager.register_strategy("two_stage", TwoStagePipeline(...))

# Единый интерфейс для всех потребителей
response = await search_manager.search(query="...", strategy="hybrid", k=5)

# С reranking и query expansion
response = await search_manager.search(
    query="...", strategy="vector", k=5,
    rerank=True, expand_query=True,
)
```

### Поток данных

#### Индексация

```
PDF файл
  → PyMuPDFLoader.load()              # ProcessedDocument (raw_text + metadata)
  → ProcessingPipeline.process()      # Splitter (recursive ИЛИ semantic) → list[DocumentChunk]
  │   ├─ RecursiveTextSplitter        #   фиксированный размер + overlap
  │   └─ SemanticTextSplitter         #   разбиение по семантическим границам (Phase 2.2)
  → MetadataEnricher.enrich_chunks()  # структурированные метаданные (Phase 1.3)
  → ContextGenerator.enrich_chunks()  # LLM-контекст для каждого чанка (Phase 3.1, опционально)
  │   chunk.metadata["contextual_content"] = context + content
  → DocumentIndexer.index_chunks()    # embed_batch → add_documents
  → ChromaDB                          # персистентное хранение
```

Семантический сплиттер (Phase 2.2) определяет точки разрыва по косинусному
сходству между последовательными предложениями и формирует когерентные чанки
с учётом ограничений `min_chunk_size` / `max_chunk_size`.

Contextual Retrieval (Phase 3.1) генерирует для каждого чанка короткое описание
его места в документе через LLM. Поле `contextual_content` используется при
создании эмбеддинга, что улучшает точность поиска на 20-30%.

#### Поиск (Vector)

```
Текстовый запрос
  → EmbeddingEngine.embed_text()   # query_embedding
  → VectorStore.search()           # cosine similarity → top-k
  → list[SearchResult]             # chunk + score + source
```

#### Поиск (Hybrid)

```
Текстовый запрос
  ├→ VectorSearch → ranked results (vector)
  └→ GraphSearch  → ranked results (graph)
       ↓
  RRF Merge (Reciprocal Rank Fusion)
       ↓
  list[SearchResult] (merged + re-scored)
```

#### RAG (вопрос-ответ)

```
Вопрос
  → RAG Agent: analyze_query()     # Классификация + выбор стратегии
  → RAG Agent: execute_search()    # SearchManager.search()
  → RAG Agent: evaluate_results()  # Проверка релевантности
  → RAG Agent: generate_answer()   # LLM + контекст → ответ с источниками
```

#### Поиск (Two-Stage)

Двухэтапный пайплайн (Phase 3.3): широкий охват на первом этапе, точный отбор на втором.

```
Текстовый запрос
  ↓
  [Этап 1: Bi-Encoder — Быстрый, Широкий]
    stage1_strategy.search(k=stage1_k)        # top 50 (hybrid / vector)
  ↓
  [Этап 2: Cross-Encoder — Точный]
    CrossEncoderReranker.rerank(stage2_rerank_k)  # top 20
    ↓ (опционально)
    MMR diversity filtering                       # убрать дубли
    ↓ (опционально)
    FlashRank token-budget selection              # маргинальная полезность
  ↓
  Финальные результаты (top-k)
```

Конфигурируется через `TwoStageSettings`: выбор стратегии первого этапа,
количество кандидатов, пороги MMR и FlashRank.

#### Evaluation (Phase 4)

Оценка качества поиска и RAG через бенчмарки.

```
EvalDataset (JSON: запросы + ground-truth chunk IDs)
  ↓
  EvalRunner.run(dataset, strategy, k)
  ├─ Для каждого test case:
  │   ├─ SearchManager.search(query, strategy)   # получить результаты
  │   ├─ Ranking-метрики:
  │   │   Precision@k, Recall@k, MRR, nDCG@10, MAP
  │   └─ RAG Triad (опционально, через RAGEvaluator):
  │       ├─ Context Relevance   (LLM-as-a-Judge)
  │       ├─ Groundedness        (LLM-as-a-Judge)
  │       └─ Answer Relevance    (LLM-as-a-Judge)
  ↓
  EvalReport
    ├─ Агрегированные метрики (mean precision, recall, mrr, ndcg, map)
    ├─ Латентность (avg, p95)
    └─ Детализация по каждому запросу
```

## Абстрактные базовые классы

| ABC | Файл | Абстрактные методы |
|-----|------|--------------------|
| `BaseLoader` | `loaders/base.py` | `load()`, `load_batch()`, `supported_extensions()` |
| `BaseEmbeddingEngine` | `embeddings/engine.py` | `embed_text()`, `embed_batch()`, `get_dimensions()`, `get_model_name()` |
| `BaseVectorStore` | `vector_store/base.py` | `initialize()`, `add_documents()`, `search()`, `search_mmr()`, `delete()`, `get_by_ids()`, `count()`, `clear()` |
| `BaseGraphStore` | `graph_store/base.py` | `initialize()`, `add_entity()`, `add_relation()`, `get_entity()`, `find_entities()`, `get_neighbors()`, `find_path()`, `query()`, `get_statistics()`, `delete_entity()`, `clear()` |

## Фабричные функции

Каждый модуль с провайдерами имеет фабричную функцию в `__init__.py`:

```python
# loaders/__init__.py
def get_loader(settings: PDFSettings) -> BaseLoader

# embeddings/__init__.py
def get_embedding_engine(settings: EmbeddingSettings) -> BaseEmbeddingEngine
def get_embedding_cache(**kwargs) -> EmbeddingCache  # Phase 11

# vector_store/__init__.py
def get_vector_store(settings: VectorStoreSettings) -> BaseVectorStore

# graph_store/__init__.py
def get_graph_store(settings: GraphStoreSettings) -> BaseGraphStore

# agents/__init__.py
def get_llm_cache(**kwargs) -> LLMResponseCache  # Phase 11

# processing/__init__.py
def get_document_cache(**kwargs) -> DocumentProcessingCache  # Phase 11

# observability/__init__.py
def get_tracer(tracer_type, **kwargs) -> BaseTracer  # Phase 11
def get_metrics_collector() -> MetricsCollector  # Phase 11

# multitenancy/__init__.py
def get_tenant_store_manager(**kwargs) -> TenantVectorStoreManager  # Phase 12
def get_tenant_graph_manager(**kwargs) -> TenantGraphManager  # Phase 12

# api/auth/__init__.py
def get_jwt_handler(**kwargs) -> JWTHandler  # Phase 12

# processing/__init__.py
def get_version_manager(**kwargs) -> DocumentVersionManager  # Phase 12
```

Фабрика читает `provider` из настроек и создаёт соответствующую реализацию.

## Модели данных (Pydantic)

### Документы

```
DocumentMetadata     → Метаданные PDF (автор, название, страницы)
DocumentChunk        → Фрагмент текста с привязкой к документу
ProcessedDocument    → Полный документ: метаданные + текст + чанки
SearchResult         → Результат поиска: чанк + оценка + источник
SearchResponse       → Ответ поиска: запрос + результаты + время
```

### Сущности

```
Entity               → Именованная сущность (имя, тип, свойства)
Relation             → Связь между сущностями (тип, направление)
SubGraph             → Подграф: сущности + связи вокруг центра
ExtractionResult     → Результат извлечения из одного чанка
```

### Ответы

```
IndexResult          → Результат индексации одного документа
PipelineResult       → Результат обработки пакета документов
```

### Кэши и метрики (Phase 11-12)

```
CacheStats           → Статистика кэша (hits, misses, total, hit_rate)
CachedDocument       → Кэшированный документ (file_hash, chunks, embeddings, metadata)
Span                 → Единица трассировки (name, duration_ms, status, attributes)
SpanStatus           → Статус спана (ok, error)
TenantMetadata       → Метаданные tenant (tenant_id, collection_name, created_at, doc_count)
TokenPayload         → JWT токен (tenant_id, role, exp, iat)
VersionInfo          → Информация о версии документа (version_id, file_hash, chunk_count)
```

## Конфигурация

Иерархическая конфигурация через `pydantic-settings`:

```
Settings (root)
├── EmbeddingSettings              # провайдер, модель, кэш
├── VectorStoreSettings            # провайдер, коллекция, метрика расстояния
├── GraphStoreSettings             # провайдер, Neo4j / NetworkX
├── PDFSettings                    # загрузчик, сплиттер (recursive / semantic), размеры чанков
├── AgentSettings                  # LLM, reranker, checkpointer
├── SearchSettings                 # гибридные веса, MMR, query expansion, FlashRank
├── ContextualRetrievalSettings    # Phase 3.1: LLM-контекст для чанков
├── TwoStageSettings               # Phase 3.3: двухэтапный пайплайн
├── ObservabilitySettings          # Phase 11: tracer, trace_dir
├── CacheSettings                  # Phase 11: embedding_ttl, llm_ttl, prompt_caching
├── AuthSettings                   # Phase 12: enabled, jwt_secret, jwt_algorithm
├── MCPServerSettings
└── APISettings
```

Ключевые параметры новых настроек:

| Настройка | Параметр | По умолчанию | Описание |
|-----------|----------|--------------|----------|
| `SearchSettings` | `mmr_diversity_lambda` | `0.5` | Баланс релевантность/разнообразие (0..1) |
| `SearchSettings` | `query_expansion_enabled` | `false` | Включить расширение запросов |
| `SearchSettings` | `query_expansion_method` | `llm` | Метод: `llm` / `synonyms` / `hyde` |
| `SearchSettings` | `flashrank_enabled` | `false` | FlashRank с токен-бюджетом |
| `ContextualRetrievalSettings` | `enabled` | `false` | Генерация LLM-контекста при индексации |
| `ContextualRetrievalSettings` | `max_context_tokens` | `128` | Максимум токенов контекста |
| `TwoStageSettings` | `enabled` | `false` | Включить двухэтапный поиск |
| `TwoStageSettings` | `stage1_k` | `50` | Кандидатов на первом этапе |
| `TwoStageSettings` | `stage1_strategy` | `hybrid` | Стратегия первого этапа |
| `TwoStageSettings` | `stage2_rerank_k` | `20` | Кандидатов после reranking |
| `TwoStageSettings` | `stage2_use_mmr` | `true` | MMR-фильтрация на втором этапе |
| `TwoStageSettings` | `stage2_use_flashrank` | `false` | FlashRank на втором этапе |

Вложенные настройки задаются через `__` разделитель:
`EMBEDDING__PROVIDER=local`, `VECTOR_STORE__DISTANCE_METRIC=cosine`, `TWO_STAGE__STAGE1_K=100`.

## Async-first

Все I/O операции асинхронны:
- Загрузка PDF — `asyncio.to_thread()` (PyMuPDF синхронный)
- Эмбеддинги — `asyncio.to_thread()` (sentence-transformers синхронный)
- Векторное хранилище — нативный async ChromaDB
- Графовое хранилище — обёртка над синхронным NetworkX
- REST API — FastAPI (нативный async)
- LangChain/LangGraph — `ainvoke()` для всех вызовов LLM

## Observability & Caching (Phase 11)

### Три уровня кэширования

| Кэш | Бэкенд | TTL | Ключ |
|-----|--------|-----|-----|
| **Embedding Cache** | SQLite | 30 дней | SHA-256(text + model) |
| **LLM Response Cache** | SQLite | 1 час | SHA-256(model + messages + temperature) |
| **Document Cache** | Pickle | Бессрочно | SHA-256(file contents) |

### Трассировка (Tracing)

Поддержка нескольких бэкендов:
- **JsonFileTracer** — JSON Lines файлы с ежедневной ротацией
- **LangSmithTracer** — интеграция с LangSmith Dashboard
- **OpenTelemetryTracer** — экспорт в Jaeger/Zipkin (опционально)

### Metrics Dashboard

API endpoints:
```
GET  /metrics          # JSON метрики
GET  /metrics/html     # HTML дашборд
POST /metrics/reset    # Сброс счётчиков
```

CLI команды:
```bash
pdf-framework cache stats                    # Статистика всех кэшей
pdf-framework cache clear                    # Очистить все кэши
pdf-framework cache clear --type embedding   # Очистить конкретный кэш
```

### Prompt Caching

Anthropic prompt caching для системных промптов > 1024 токенов:
- Автоматическое добавление `cache_control` в SystemMessage
- Логирование экономии токенов из `response.usage`
- Graceful fallback при отсутствии поддержки

## Multi-Tenancy & Production Hardening (Phase 12)

### Tenant Isolation

Каждый tenant получает изолированное хранилище данных:

| Компонент | Изоляция | Хранилище |
|-----------|----------|-----------|
| **Vector Store** | Отдельная ChromaDB коллекция | `tenant_{sanitized_id}` |
| **Graph Store** | Фильтрация по `tenant_id` атрибуту | `data/graph_db/tenant_{id}.json` |
| **Document Cache** | Префикс по tenant_id | `data/cache/documents/{tenant}/{hash}.pkl` |

### JWT Authentication

Аутентификация через JWT токены:

```python
# Создать токен
token = jwt_handler.create_token(tenant_id="myorg", role="editor")

# FastAPI dependency
from src.api.auth import TenantId

async def my_endpoint(tenant_id: TenantId):
    # tenant_id извлекается из Bearer токена
    store = await get_tenant_store_manager().get_store(tenant_id)
```

### RBAC (Role-Based Access Control)

Три роли с разными правами:

| Роль | Права |
|------|-------|
| **viewer** | search:read, ask:read, documents:get, stats:read |
| **editor** | viewer + documents:index, documents:delete, documents:update |
| **admin** | editor + tenants:create/delete, users:manage, metrics:read |

```python
from src.api.auth import require_role, TokenPayloadDep

@require_role("editor")
async def upload_document(payload: TokenPayloadDep):
    # Требуется роль editor или выше
    pass
```

### Document Versioning

Отслеживание версий с возможностью отката:

```python
from src.pdf_framework.processing import get_version_manager

version_mgr = get_version_manager()

# Создать версию при индексации
await version_mgr.create_version(doc_id, chunks, embeddings, metadata)

# Откатиться к предыдущей версии
chunks, embeddings, metadata = await version_mgr.rollback(doc_id)
```

### Health Checks

Production-ready health checks для Kubernetes:

```bash
GET /health          # Полный статус с компонентами
GET /health/ready    # Readiness probe
GET /health/live     # Liveness probe
```

### CLI команды (Phase 12)

```bash
# Управление tenants
pdf-framework tenant create myorg
pdf-framework tenant list
pdf-framework tenant delete myorg

# Генерация JWT токенов
pdf-framework auth token --tenant myorg --role editor

# Health check
curl http://localhost:8000/health
```

### Конфигурация (Phase 12)

```ini
# Phase 12: Multi-Tenancy
AUTH__ENABLED=false
AUTH__JWT_SECRET=change-me-in-production
AUTH__JWT_ALGORITHM=HS256
AUTH__TOKEN_EXPIRE_HOURS=24
AUTH__DEFAULT_TENANT=default
```
