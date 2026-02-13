# PDF Vector & Graph Framework

Фреймворк для интеллектуальной обработки PDF-документов с использованием векторных и графовых баз данных. Позволяет загружать PDF, разбивать на чанки, строить эмбеддинги, индексировать в ChromaDB, извлекать сущности в граф знаний (NetworkX), выполнять гибридный поиск и отвечать на вопросы через RAG-агента на базе LangGraph.

**Версия:** v0.5.0 (Phases 1-4 Complete)

## Возможности

### Базовые
- **Загрузка PDF** — извлечение текста и метаданных через PyMuPDF
- **Разбивка на чанки** — рекурсивный и семантический сплиттеры
- **Эмбеддинги** — локальные модели (sentence-transformers) с дисковым кэшем
- **Векторное хранилище** — ChromaDB с поддержкой cosine/euclidean/dot и MMR-поиска
- **Граф знаний** — извлечение сущностей через LLM, хранение в NetworkX с JSON-персистенцией
- **RAG-агент** — LangGraph агент с адаптивным выбором стратегии поиска
- **3 интерфейса** — CLI (Typer), REST API (FastAPI), MCP Server

### Поиск (Phase 1-3)
- **Гибридный поиск** — vector + graph через RRF с настраиваемыми весами
- **Реранкинг** — cross-encoder (BAAI/bge-reranker-v2-m3), +40% accuracy
- **Metadata filtering** — фильтрация по языку, типу документа, версии
- **MMR diversity** — Maximal Marginal Relevance для разнообразия результатов
- **Query expansion** — LLM-расширение запросов, синонимы (pymorphy3), HyDE
- **Contextual retrieval** — LLM-генерация контекста при индексации (+20-30% accuracy)
- **FlashRank** — token-budget-aware отбор документов с marginal utility
- **Two-Stage Pipeline** — bi-encoder (broad recall) → cross-encoder + MMR + FlashRank

### Оценка (Phase 4)
- **Ranking metrics** — Precision@k, Recall@k, MRR, NDCG@k, MAP
- **RAG Triad** — LLM-as-a-Judge: Context Relevance, Groundedness, Answer Relevance
- **Benchmark runner** — автоматический запуск оценки по датасету

## Быстрый старт

### Установка

```bash
# Windows
setup.bat

# Или вручную
uv venv .venv
.venv\Scripts\activate
uv pip install -e ".[dev]"
```

### Настройка

Скопируйте `.env.example` в `.env` и заполните API-ключи:

```bash
cp .env.example .env
```

Минимально необходимо:
- `ANTHROPIC_API_KEY` — для RAG-ответов и извлечения сущностей

Для работы без API-ключей доступны: загрузка PDF, разбивка, локальные эмбеддинги, векторный поиск.

### Индексация PDF

```bash
# Базовая индексация
pdf-framework index path/to/document.pdf

# С построением графа знаний
pdf-framework index path/to/document.pdf --graph

# С генерацией контекста (Phase 3.1)
pdf-framework index path/to/document.pdf --contextual
```

### Поиск

```bash
# Векторный поиск (по умолчанию, с reranking)
pdf-framework search "ваш запрос"

# Гибридный поиск (vector + graph)
pdf-framework search "ваш запрос" --strategy hybrid

# MMR — разнообразные результаты
pdf-framework search "ваш запрос" --strategy mmr --diversity 0.7

# Two-Stage Pipeline — максимальное качество
pdf-framework search "ваш запрос" --strategy two_stage

# С фильтрацией по metadata
pdf-framework search "руководство" --language ru --doc-type documentation

# С расширением запроса
pdf-framework search "ваш запрос" --expand-query
```

### Вопрос-ответ (RAG)

```bash
pdf-framework ask "О чем этот документ?"
```

### Оценка (Phase 4)

```bash
# Ranking metrics
pdf-framework eval data/eval/sample_dataset.json --strategy hybrid

# + RAG Triad (LLM-as-a-Judge)
pdf-framework eval data/eval/sample_dataset.json --with-rag-triad
```

### Статистика

```bash
pdf-framework stats
```

### REST API сервер

```bash
pdf-framework server
# Swagger UI: http://localhost:8000/docs
```

## Архитектура

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Интерфейсы                                    │
│   ┌─────────┐     ┌──────────────┐     ┌──────────────────┐         │
│   │   CLI   │     │   REST API   │     │   MCP Server     │         │
│   │ (Typer) │     │  (FastAPI)   │     │  (stdio/SSE)     │         │
│   └────┬────┘     └──────┬───────┘     └────────┬─────────┘         │
│        └────────────┬────┴──────────────────────┘                   │
│                     ▼                                                │
│              ┌─────────────┐                                         │
│              │ Components  │  Dependency Injection                    │
│              └──────┬──────┘                                         │
│        ┌────────────┼───────────────┬──────────────┐                │
│        ▼            ▼               ▼              ▼                │
│  ┌──────────┐ ┌───────────┐ ┌─────────────┐ ┌────────────┐        │
│  │  Loader  │ │ Pipeline  │ │SearchManager│ │ EvalRunner │        │
│  │(PyMuPDF) │ │(Splitter+ │ │  (Router)   │ │(Phase 4)   │        │
│  └────┬─────┘ │ Context)  │ └──────┬──────┘ └────────────┘        │
│       │        └─────┬─────┘ ┌──────┼──────────┬──────┐            │
│       ▼              ▼       ▼      ▼          ▼      ▼            │
│  ┌─────────┐  ┌─────────┐ Vector Graph Hybrid MMR Two-Stage       │
│  │Raw Text │  │ Chunks  │ Search Search Search      Pipeline       │
│  └─────────┘  └────┬────┘   │      │      │           │            │
│                    ▼        ▼      ▼      ▼           ▼            │
│              ┌──────────┐ ┌───────────────────────────────┐        │
│              │ Indexer   │ │ Reranker + FlashRank + MMR    │        │
│              │(Embed+    │ │ (Cross-Encoder Pipeline)      │        │
│              │ Store)    │ └───────────────────────────────┘        │
│              └─────┬─────┘                                          │
│           ┌────────┴────────┐                                       │
│           ▼                 ▼                                       │
│     ┌──────────┐     ┌───────────┐                                  │
│     │ ChromaDB │     │ NetworkX  │                                  │
│     │ (Vector) │     │  (Graph)  │                                  │
│     └──────────┘     └───────────┘                                  │
└──────────────────────────────────────────────────────────────────────┘
```

### Структура проекта

```
src/
├── pdf_framework/           # Ядро фреймворка
│   ├── config.py            # Конфигурация (Pydantic Settings)
│   ├── schemas/             # Модели данных
│   │   ├── documents.py     #   DocumentChunk, SearchResult, ...
│   │   ├── entities.py      #   Entity, Relation, SubGraph
│   │   └── responses.py     #   IndexResult, PipelineResult
│   ├── loaders/             # Загрузчики документов
│   │   └── pdf/pymupdf_loader.py
│   ├── processing/          # Обработка текста
│   │   ├── pipeline.py      #   Оркестратор обработки
│   │   ├── splitters/       #   recursive, semantic (Phase 2.2)
│   │   ├── cleaners/        #   Очистка текста
│   │   ├── extractors/      #   Извлечение сущностей (LLM)
│   │   └── context_generator.py  # Contextual Retrieval (Phase 3.1)
│   ├── embeddings/          # Эмбеддинги
│   │   ├── engine.py        #   Базовый класс
│   │   ├── providers/       #   Провайдеры (local)
│   │   └── cache/           #   Дисковый кэш
│   ├── vector_store/        # Векторное хранилище
│   │   ├── base.py          #   Базовый класс
│   │   ├── providers/       #   Провайдеры (ChromaDB)
│   │   └── indexing/        #   Индексатор (embed → store)
│   ├── graph_store/         # Графовое хранилище
│   │   ├── base.py          #   Базовый класс
│   │   ├── providers/       #   Провайдеры (NetworkX)
│   │   └── construction/    #   Построение графа
│   ├── search/              # Поиск
│   │   ├── manager.py       #   Единая точка входа + query expansion
│   │   ├── strategies/      #   vector, graph, hybrid, mmr (Phase 2.1)
│   │   ├── reranking/       #   cross_encoder, flashrank (Phase 3.2)
│   │   ├── pipelines/       #   two_stage (Phase 3.3)
│   │   └── query_expansion.py  # LLM/synonym/HyDE (Phase 2.3)
│   ├── evaluation/          # Evaluation Framework (Phase 4)
│   │   ├── dataset.py       #   TestCase, EvalDataset
│   │   ├── metrics.py       #   Precision, Recall, MRR, NDCG, MAP
│   │   ├── rag_evaluator.py #   RAG Triad (LLM-as-a-Judge)
│   │   └── runner.py        #   EvalRunner, EvalReport
│   ├── chains/              # LangChain chains
│   │   └── qa/              #   RetrievalQA (RAG-ответы)
│   ├── agents/              # LangGraph агенты
│   │   └── rag/             #   RAG-агент с адаптивной стратегией
│   ├── tools/               # LangChain tools
│   │   ├── retrieval/       #   Поиск документов
│   │   ├── document/        #   Индексация PDF
│   │   └── graph_query/     #   Запросы к графу
│   └── callbacks/           # Логирование и метрики
│       ├── logging/         #   Структурированный логгер
│       └── metrics/         #   Сбор метрик в памяти
├── api/                     # REST API (FastAPI)
│   ├── app.py               #   Фабрика приложения
│   ├── dependencies/        #   DI-контейнер (Components)
│   └── routes/              #   documents, search, health
├── cli/                     # CLI (Typer)
│   └── main.py              #   index, search, ask, stats, server, eval
└── mcp_server/              # MCP Server
    └── server.py            #   5 инструментов для Claude Code
```

## Конфигурация

Все настройки задаются через переменные окружения или `.env` файл. Используется разделитель `__` для вложенных настроек.

### Основные переменные

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `ANTHROPIC_API_KEY` | — | API-ключ Anthropic (для RAG и извлечения сущностей) |
| `OPENAI_API_KEY` | — | API-ключ OpenAI (опционально) |
| `LOG_LEVEL` | `INFO` | Уровень логирования: DEBUG, INFO, WARNING, ERROR |
| `LOG_FORMAT` | `text` | Формат логов: `text` или `json` |

### Эмбеддинги (`EMBEDDING__*`)

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `EMBEDDING__PROVIDER` | `local` | Провайдер: `local`, `openai`, `voyage` |
| `EMBEDDING__MODEL` | `all-MiniLM-L6-v2` | Модель эмбеддингов |
| `EMBEDDING__DIMENSIONS` | `384` | Размерность вектора |
| `EMBEDDING__BATCH_SIZE` | `64` | Размер батча |
| `EMBEDDING__CACHE_ENABLED` | `true` | Включить дисковый кэш |

### Векторное хранилище (`VECTOR_STORE__*`)

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `VECTOR_STORE__PROVIDER` | `chroma` | Провайдер: `chroma`, `qdrant`, `faiss` |
| `VECTOR_STORE__COLLECTION_NAME` | `pdf_documents` | Имя коллекции |
| `VECTOR_STORE__DISTANCE_METRIC` | `cosine` | Метрика: `cosine`, `euclidean`, `dot` |

### Графовое хранилище (`GRAPH_STORE__*`)

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `GRAPH_STORE__PROVIDER` | `networkx` | Провайдер: `networkx`, `neo4j` |
| `GRAPH_STORE__NEO4J_URI` | `bolt://localhost:7687` | URI Neo4j (если provider=neo4j) |
| `GRAPH_STORE__NEO4J_USER` | `neo4j` | Пользователь Neo4j |
| `GRAPH_STORE__NEO4J_PASSWORD` | — | Пароль Neo4j |

### Обработка PDF (`PDF__*`)

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `PDF__LOADER` | `pymupdf` | Загрузчик: `pymupdf`, `pdfplumber`, `unstructured` |
| `PDF__CHUNK_SIZE` | `1000` | Размер чанка (символы) |
| `PDF__CHUNK_OVERLAP` | `200` | Перекрытие чанков |
| `PDF__SPLITTER` | `recursive` | Тип сплиттера: `recursive`, `semantic` |
| `PDF__SEMANTIC_THRESHOLD` | `0.75` | Порог семантического сплиттера |

### Поиск (`SEARCH__*`)

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `SEARCH__HYBRID_VECTOR_WEIGHT` | `0.6` | Вес vector search в hybrid |
| `SEARCH__HYBRID_GRAPH_WEIGHT` | `0.4` | Вес graph search в hybrid |
| `SEARCH__HYBRID_RRF_K` | `60` | RRF параметр k |
| `SEARCH__MMR_DIVERSITY_LAMBDA` | `0.5` | MMR λ (0=diversity, 1=relevance) |
| `SEARCH__QUERY_EXPANSION_ENABLED` | `false` | Расширение запросов |
| `SEARCH__QUERY_EXPANSION_METHOD` | `llm` | Метод: `llm`, `synonym`, `hyde` |
| `SEARCH__FLASHRANK_ENABLED` | `false` | FlashRank token-budget selection |
| `SEARCH__FLASHRANK_TOKEN_BUDGET` | `4096` | Token budget для FlashRank |

### Агент (`AGENT__*`)

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `AGENT__MODEL` | `claude-sonnet-4-5-20250929` | Модель LLM |
| `AGENT__TEMPERATURE` | `0.0` | Температура генерации |
| `AGENT__MAX_TOKENS` | `4096` | Макс. токенов в ответе |
| `AGENT__SEARCH_K` | `5` | Количество результатов поиска |
| `AGENT__RERANKER_ENABLED` | `true` | Включить реранкинг |
| `AGENT__RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Модель реранкера |

### Two-Stage Pipeline (`TWO_STAGE__*`)

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `TWO_STAGE__ENABLED` | `false` | Включить two-stage pipeline |
| `TWO_STAGE__STAGE1_K` | `50` | Количество результатов Stage 1 |
| `TWO_STAGE__STAGE2_RERANK_K` | `20` | Top-k для cross-encoder rerank |
| `TWO_STAGE__STAGE2_USE_MMR` | `true` | MMR diversity в Stage 2 |
| `TWO_STAGE__STAGE2_USE_FLASHRANK` | `false` | FlashRank в Stage 2 |

### Contextual Retrieval (`CONTEXTUAL_RETRIEVAL__*`)

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `CONTEXTUAL_RETRIEVAL__ENABLED` | `false` | Генерация контекста при индексации |
| `CONTEXTUAL_RETRIEVAL__MAX_CONTEXT_TOKENS` | `256` | Макс. токенов контекста |

## CLI

```
pdf-framework --help

Команды:
  index   Индексировать PDF в векторное хранилище
  search  Поиск по индексированным документам
  ask     Задать вопрос (RAG)
  stats   Статистика индекса
  server  Запустить REST API сервер
  eval    Запустить evaluation benchmark (Phase 4)
```

### Флаги команд

```bash
# index
pdf-framework index <file_path> [--graph] [--contextual]

# search
pdf-framework search <query> \
    [--strategy vector|graph|hybrid|mmr|two_stage] \
    [--top-k 5] \
    [--no-rerank] \
    [--language ru] [--doc-type documentation] [--version 8.3] \
    [--diversity 0.7] \
    [--expand-query]

# ask
pdf-framework ask <question> [--strategy hybrid]

# eval
pdf-framework eval <dataset.json> \
    [--strategy vector] \
    [--top-k 5] \
    [--with-rag-triad]

# server
pdf-framework server [--host 0.0.0.0] [--port 8000]
```

## Стратегии поиска

### Vector Search
Эмбеддинг запроса → cosine similarity в ChromaDB → reranking → top-k результатов.

### Graph Search
Поиск сущностей по имени → обход соседей на заданную глубину → извлечение связанных чанков.

### Hybrid Search
Параллельно vector + graph поиск, объединение через **Reciprocal Rank Fusion (RRF)**:
```
score(d) = w_vector / (k + rank_vector(d)) + w_graph / (k + rank_graph(d))
```

### MMR Search (Phase 2.1)
Maximal Marginal Relevance — баланс между релевантностью и разнообразием:
```
MMR = λ * sim(q, d) - (1-λ) * max(sim(d, selected))
```

### Two-Stage Pipeline (Phase 3.3)
Двухэтапный pipeline для максимального качества:
```
Query → [Stage 1: Bi-encoder, top 50] → [Stage 2: Cross-encoder + MMR + FlashRank] → top k
```

## REST API

### Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/health/` | Базовая проверка |
| `GET` | `/health/ready` | Проверка готовности |
| `GET` | `/health/live` | Проверка живости |
| `POST` | `/documents/index` | Индексировать PDF |
| `GET` | `/documents/stats` | Статистика индекса |
| `DELETE` | `/documents/{document_id}` | Удалить документ |
| `POST` | `/search/` | Поиск по документам |
| `POST` | `/search/ask` | Вопрос-ответ (RAG) |

### Примеры запросов

```bash
# Поиск с фильтрацией и реранкингом
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "машинное обучение",
    "strategy": "hybrid",
    "k": 5,
    "filter": {"language": "ru"},
    "rerank": true,
    "expand_query": false
  }'

# Вопрос-ответ
curl -X POST http://localhost:8000/search/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Какие методы описаны?", "strategy": "hybrid"}'
```

## MCP Server

MCP-сервер предоставляет 5 инструментов для использования из Claude Code и других MCP-клиентов.

| Инструмент | Описание |
|------------|----------|
| `index_pdf` | Загрузить и проиндексировать PDF-документ |
| `search_documents` | Поиск по индексированным документам |
| `ask_question` | Задать вопрос и получить RAG-ответ |
| `graph_query` | Запрос к графу знаний (сущности и связи) |
| `get_stats` | Статистика индекса и графа |

### Настройка в Claude Code

```json
{
  "mcpServers": {
    "pdf-vector-graph": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "/path/to/project"
    }
  }
}
```

## RAG-агент

LangGraph агент с 4 узлами:

```
analyze → search → evaluate → generate
                      ↓ (если недостаточно контекста)
                    retry (переключение на hybrid) → search → ...
```

## Provider Pattern

| Компонент | Базовый класс | Реализованные провайдеры | Возможные расширения |
|-----------|--------------|------------------------|---------------------|
| Загрузчик | `BaseLoader` | PyMuPDF | pdfplumber, Unstructured |
| Эмбеддинги | `BaseEmbeddingEngine` | Local (sentence-transformers) | OpenAI, Voyage |
| Векторное хранилище | `BaseVectorStore` | ChromaDB | Qdrant, FAISS |
| Графовое хранилище | `BaseGraphStore` | NetworkX | Neo4j |

## Хранение данных

```
data/
├── vector_db/       # ChromaDB (персистентное хранилище)
├── graph_db/        # NetworkX JSON-файлы графа
├── cache/
│   └── embeddings/  # Дисковый кэш эмбеддингов (SHA-256 → JSON)
├── eval/            # Evaluation datasets (Phase 4)
├── pdfs/            # Входные PDF-файлы
└── temp/            # Временные файлы
```

## Разработка

```bash
pip install -e ".[dev]"
ruff check src/
ruff format src/
pytest --cov=src
```

## Лицензия

MIT
