# PDF Vector & Graph Framework

[![CI](https://github.com/your-org/pdf-vector-graph-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/pdf-vector-graph-framework/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/your-org/pdf-vector-graph-framework/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/pdf-vector-graph-framework)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Фреймворк для интеллектуальной обработки PDF-документов с использованием векторных и графовых баз данных. Загрузка PDF, разбивка на чанки, построение эмбеддингов, индексация в Qdrant (dense + sparse BM25 vectors), извлечение сущностей в граф знаний (NetworkX), гибридный поиск и ответы на вопросы через RAG-агента на базе LangGraph.

**Версия:** v1.5.0 (43 фазы реализованы)

## Возможности

### Загрузка и индексация
- **Hybrid Loader** — PyMuPDF4LLM + fitz tables + Docling tables + Vision OCR (Level 4)
- **Resilient Indexing** — детерминированные ID, батчевые чекпоинты, resume
- **Image Understanding** — Claude Vision для описания изображений (таблицы → markdown)
- **Page-Aware Chunks** — каждый чанк знает свой номер страницы и раздел

### Поиск
- **Hybrid Search** — Qdrant native RRF (dense + BM25 sparse vectors)
- **BM25 Lexical** — FTS5 multi-column (title 10x, body 1x), pymorphy3 лемматизация (5-14ms)
- **Section-Aware** — двухпроходной: BM25 определяет раздел → hybrid внутри раздела
- **LLM Reranker** — Claude Sonnet via Z.AI (1-3s vs 60-120s cross-encoder)
- **Turbo Pipeline** — rule-based fast classify (0ms), BM25 early termination для простых запросов
- **ColBERT** — late interaction MaxSim, 70/30 blending
- **GraphRAG** — local, global, LightRAG (auto-select по сложности запроса)

### Агенты
- **RAG Agent** — LangGraph с self-correction (Ralph Wiggum pattern)
- **Analytical Agent** — planner + evidence collector + comparator + structured output
- **Research Agent v2** — plan-tree DAG, evidence graph, quality gates, session persistence
- **Multi-Agent** — 4 агента, verify→rewrite loop

### Enterprise
- **RBAC** — JWT аутентификация, роли (viewer/editor/admin)
- **Rate Limiting** — middleware для ограничения запросов
- **Analytics** — QueryTracker, CostTracker, AuditLogger
- **OpenAI-Compatible API** — `/v1/chat/completions`, `/v1/embeddings`
- **DSPy Optimization** — MIPROv2 для автоматической оптимизации промптов
- **Multi-Document KB** — коллекции, реестр документов, scoped search

## Быстрый старт

### Установка

```bash
# Windows
setup.bat

# Или вручную
uv venv .venv
.venv\Scripts\activate
uv pip install -e ".[dev,qdrant,docling,morphology]"
```

### Настройка

```bash
cp .env.example .env
```

Минимальные переменные:
```env
ANTHROPIC_API_KEY=sk-...          # Для RAG-ответов и извлечения сущностей
ANTHROPIC_BASE_URL=https://...    # Z.AI proxy (если используется)
EMBEDDING__MODEL=intfloat/multilingual-e5-large
EMBEDDING__DIMENSIONS=1024
VECTOR_STORE__PROVIDER=qdrant
VECTOR_STORE__QDRANT_URL=http://localhost:6333
```

### Docker (Qdrant)

```bash
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
```

### Индексация PDF

```bash
# Базовая индексация (Hybrid Loader)
pdf-framework index path/to/document.pdf

# С построением графа знаний
pdf-framework index path/to/document.pdf --graph

# С генерацией контекста
pdf-framework index path/to/document.pdf --contextual
```

### Поиск

```bash
# Гибридный поиск (vector + BM25, по умолчанию)
pdf-framework search "ваш запрос" --strategy hybrid

# BM25 — быстрый лексический (5-14ms)
pdf-framework search "справочники" --strategy bm25

# Section-aware — поиск внутри раздела
pdf-framework search "регистры накопления" --strategy section

# Two-Stage Pipeline — максимальное качество
pdf-framework search "ваш запрос" --strategy two_stage

# С расширением запроса
pdf-framework search "ваш запрос" --expand-query
```

### Вопрос-ответ (RAG)

```bash
pdf-framework ask "О чем этот документ?"
```

### REST API

```bash
pdf-framework server
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

## Архитектура

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Interface Layer                                │
│    CLI (Typer)  │  REST API (FastAPI)  │  MCP Server  │  Streamlit UI  │
├────────────────────────────────────────────────────────────────────────┤
│                       Orchestration Layer                               │
│  Components (DI) │ SearchManager │ RAG Agent │ Multi-Agent │ DSPy      │
├────────────────────────────────────────────────────────────────────────┤
│                       Business Logic Layer                              │
│  Hybrid Loader │ Pipeline │ Indexer │ Chains │ Reranking │ Evaluation  │
├────────────────────────────────────────────────────────────────────────┤
│                         Storage Layer                                   │
│  Qdrant (Dense+BM25) │ FTS5 (BM25 fallback) │ NetworkX (Graph)        │
├────────────────────────────────────────────────────────────────────────┤
│                       Infrastructure Layer                              │
│  E5 Embeddings │ Cache (3 types) │ Observability │ Config │ Analytics  │
├────────────────────────────────────────────────────────────────────────┤
│                      Claude Code Integration                            │
│  Hooks (12) │ Skills (9) │ MCP Tools (12) │ Ralph Wiggum │ Triad      │
└────────────────────────────────────────────────────────────────────────┘
```

### Структура проекта

```
src/
├── pdf_framework/           # Ядро фреймворка
│   ├── config/              # Pydantic settings (12 модулей)
│   ├── schemas/             # Модели данных (Pydantic)
│   ├── loaders/             # Загрузчики (hybrid, pymupdf4llm, docling)
│   ├── processing/          # Splitting, cleaning, metadata, pipeline
│   ├── embeddings/          # E5 multilingual (1024d) + ONNX/OpenVINO
│   ├── vector_store/        # Qdrant, ChromaDB, PgVector
│   ├── graph_store/         # NetworkX + LightRAG
│   ├── search/              # Strategies, pipelines, reranking, BM25
│   ├── agents/              # RAG, analytical, research v2, multi-agent
│   ├── analytics/           # QueryTracker, CostTracker, AuditLogger
│   ├── knowledge_base/      # Collections, document registry
│   ├── optimization/        # DSPy modules, MIPROv2, metrics
│   ├── evaluation/          # RAGAS, benchmarks
│   ├── feedback/            # Self-learning store
│   ├── callbacks/           # Token tracking middleware
│   ├── indexing/            # Batch indexing, dedup
│   ├── chains/              # QA chains, enrichment
│   ├── tools/               # LangChain tools
│   └── utils/               # ID generator, helpers
├── api/                     # REST API (FastAPI, 14 routers)
├── cli/                     # CLI (Typer)
├── mcp_server/              # MCP Server (12 tools)
└── ui/                      # Streamlit UI
```

## Конфигурация

Все настройки через переменные окружения (`.env`) с разделителем `__`.

### Ключевые переменные

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `ANTHROPIC_API_KEY` | — | API-ключ Anthropic |
| `ANTHROPIC_BASE_URL` | — | Proxy URL (Z.AI) |
| `EMBEDDING__MODEL` | `intfloat/multilingual-e5-large` | Модель эмбеддингов (1024d) |
| `EMBEDDING__BACKEND` | `torch` | Backend: `torch`, `onnx`, `openvino` |
| `VECTOR_STORE__PROVIDER` | `qdrant` | Провайдер: `qdrant`, `chroma`, `pgvector` |
| `VECTOR_STORE__QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `AGENT__RERANKER_TYPE` | `llm` | Реранкер: `llm`, `cross_encoder`, `colbert` |
| `AGENT__MODEL` | `claude-sonnet-4-5-20250929` | Модель LLM |
| `SEARCH__BM25_WEIGHT` | `0.3` | Вес BM25 в hybrid |

Полный список переменных: `src/pdf_framework/config/`

## Стратегии поиска

| Стратегия | Латентность | Описание |
|-----------|------------|----------|
| `bm25` | 5-14ms | FTS5 лексический поиск (pymorphy3 лемматизация) |
| `vector` | 400-500ms | Cosine similarity через E5 embeddings |
| `hybrid` | 400-500ms | Qdrant native RRF (dense + BM25 sparse) |
| `section` | 10-500ms | BM25 → определение раздела → hybrid внутри |
| `mmr` | 400-500ms | Maximal Marginal Relevance |
| `two_stage` | 1-3s | Bi-encoder → LLM Reranker |
| `graph` | 200-400ms | Entity graph traversal |
| `graphrag_local` | 1-2s | Community-based local context |
| `graphrag_global` | 2-5s | Cross-community global context |
| `lightrag` | 600-900ms | Entity/relation embedding search |

## REST API

14 групп эндпоинтов (84+ endpoints):

| Группа | Prefix | Endpoints | Описание |
|--------|--------|-----------|----------|
| Health | `/health` | 3 | Readiness, liveness probes |
| Auth | `/auth` | 2 | JWT tokens |
| Documents | `/documents` | 16 | Indexing, management, rebuild |
| Search | `/search` | 5 | Vector, hybrid, analytical, research |
| Chat | `/chat` | 5 | Multi-turn conversations |
| Graph | `/graph` | 7 | Knowledge graph operations |
| Cache | `/cache` | 2 | Cache management |
| Metrics | `/metrics` | 3 | System metrics |
| Feedback | `/feedback` | 5 | Self-learning feedback |
| ToC | `/toc` | 3 | Table of contents |
| Collections | `/collections` | 8 | Multi-document KB |
| OpenAI | `/v1` | 3 | OpenAI-compatible API |
| Optimization | `/optimization` | 5 | DSPy optimization |
| Analytics | `/analytics` | 7 | Enterprise analytics |

Полная документация: [docs/api/rest-api.md](docs/api/rest-api.md)

Swagger UI: `http://localhost:8000/docs`

## MCP Server

12 инструментов для Claude Code и MCP-клиентов:

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

## Provider Pattern

| Компонент | Базовый класс | Реализованные провайдеры |
|-----------|--------------|------------------------|
| Загрузчик | `BaseLoader` | Hybrid, PyMuPDF4LLM, Docling |
| Эмбеддинги | `EmbeddingEngine` | Local (E5, BGE-M3), ONNX, OpenVINO |
| Векторное хранилище | `BaseVectorStore` | Qdrant, ChromaDB, PgVector |
| Графовое хранилище | `BaseGraphStore` | NetworkX |
| Реранкер | `BaseReranker` | LLM (Claude), CrossEncoder, FlashRank, ColBERT |

## Хранение данных

```
data/
├── qdrant/          # Qdrant Docker volume (dense + sparse vectors)
├── bm25_index.db    # FTS5 SQLite (BM25 fallback)
├── graph_db/        # NetworkX JSON-файлы графа
├── cache/
│   └── embeddings/  # Дисковый кэш эмбеддингов
├── eval/            # Evaluation datasets
└── pdfs/            # Входные PDF-файлы
```

## Разработка

```bash
pip install -e ".[dev]"
ruff check src/
ruff format src/
pytest --cov=src
mypy src/
```

## Лицензия

MIT
