# Framework MCP, UI & Python API

## Когда использовать
- "MCP", "MCP server", "Claude Code integration"
- "Gradio", "Web UI", "интерфейс", "веб-интерфейс"
- "Python API", "QuickRAG", "Components"
- "какой интерфейс выбрать", "как подключить"

---

## Сравнение интерфейсов

| Интерфейс | Когда использовать | Скорость старта |
|-----------|-------------------|-----------------|
| **CLI** | Скрипты, автоматизация, разовые задачи | `python -m src.cli.main ...` |
| **REST API** | Интеграция с внешними сервисами | `curl http://localhost:8000/...` |
| **MCP Server** | Работа через Claude Code / AI агентов | `claude mcp add ...` |
| **Web UI** | Визуальный интерфейс, демо, non-tech users | `python -m src.ui.app` |
| **Python API** | Встраивание в Python-приложения | `from src.pdf_framework import QuickRAG` |

Для CLI → `framework-cli`, для REST API → `framework-api`

---

## MCP Server (18 инструментов)

### Запуск

```bash
python -m src.mcp_server.server
```

### Настройка в Claude Code

Добавить в `.claude/settings.local.json`:

```json
{
    "mcpServers": {
        "pdf-framework": {
            "command": "python",
            "args": ["-m", "src.mcp_server.server"],
            "cwd": "/path/to/1C-Framework"
        }
    }
}
```

### 18 инструментов

| # | Инструмент | Описание |
|---|-----------|----------|
| 1 | `index_pdf` | Индексация PDF файла |
| 2 | `search_documents` | Поиск (16 стратегий: vector, graph, hybrid, bm25, section_first, graphrag_local, graphrag_light, graphrag_global, mmr, adaptive, auto_merge, raptor, two_stage, visual, graphrag_auto, web_search) |
| 3 | `ask_question` | RAG question-answering |
| 4 | `graph_query` | Поиск по графу знаний (entity, depth) |
| 5 | `analyze` | Analytical RAG — evidence + comparison (Phase 33) |
| 6 | `research` | Deep Research v2 — plan-execute-verify (Phase 36) |
| 7 | `web_search` | Web search via Tavily/SerpAPI/DuckDuckGo (Phase 37) |
| 8 | `search_with_fallback` | Local docs + web fallback fusion (Phase 37) |
| 9 | `list_collections` | Список коллекций документов (Phase 32) |
| 10 | `list_documents` | Список проиндексированных документов |
| 11 | `get_toc` | Оглавление документа |
| 12 | `get_stats` | Статистика (vector store, graph, cache) |
| 13 | `visual_search` | Visual search по описанию (Phase 55) |
| 14 | `visual_hybrid_search` | RRF visual + text hybrid (Phase 55) |
| 15 | `plan_execute` | Plan-Execute agent — DAG план (Phase 57) |

### Примеры вызовов

```
search_documents(query="конфигуратор", strategy="hybrid", k=5)

ask_question(query="Что такое конфигуратор?", strategy="hybrid")

index_pdf(path="data/pdfs/document.pdf", graph=true, communities=true)

web_search(query="RAG best practices 2025", k=5)

visual_search(query="таблица сравнения типов данных", k=3)
```

---

## Web UI (Gradio)

### Запуск

```bash
# Backend
python -m src.api.app       # → http://localhost:8000

# UI (отдельный терминал)
python -m src.ui.app         # → http://localhost:7860

# Или через Makefile
make serve   # API
make ui      # UI
```

### Опции запуска

```bash
python -m src.ui.app --port 7860 --api-url http://localhost:8000
python -m src.ui.app --share   # Публичная ссылка через Gradio
```

### 5 вкладок

| Вкладка | Возможности |
|---------|------------|
| **Chat** | Диалог с AI, streaming, источники под ответом, thumbs up/down |
| **Search** | Поиск с выбором стратегии, top-k, фильтры (язык, тип), scores |
| **Documents** | Загрузка PDF (drag & drop), список, удаление, пересборка BM25 |
| **Graph** | Визуализация entities + relations, фильтрация, статистика |
| **Settings** | Конфигурация, статистика кэша/индекса, сброс |

---

## Python API

### QuickRAG — 3 строки

```python
from src.pdf_framework import QuickRAG

rag = QuickRAG()
rag.add("data/pdfs/document.pdf")
answer = rag.ask("Что такое конфигуратор?")
```

### Async QuickRAG

```python
import asyncio
from src.pdf_framework import QuickRAG

async def main():
    rag = QuickRAG()
    await rag.aadd("data/pdfs/document.pdf")
    results = await rag.asearch("конфигуратор", k=3)
    answer = await rag.aask("Что это?")
    stats = await rag.astats()
    print(answer)

asyncio.run(main())
```

### Components API (полный доступ)

```python
from src.api.dependencies.components import Components

async def main():
    components = Components()
    await components.initialize()

    # Компоненты:
    # components.search_manager   — SearchManager (14 стратегий)
    # components.loader           — PDF Loader
    # components.pipeline         — Processing Pipeline
    # components.indexer          — Indexer
    # components.vector_store     — Qdrant
    # components.graph_store      — NetworkX/Neo4j
    # components.bm25_store       — BM25 (FTS5)
    # components.settings         — Configuration
```

### Поиск через Components

```python
# Простой
response = await components.search_manager.search(
    query="конфигуратор", strategy="vector", k=5
)

# Hybrid с фильтрацией и reranking
response = await components.search_manager.search(
    query="конфигуратор", strategy="hybrid", k=10,
    filter={"language": "ru", "document_type": "documentation"},
    rerank=True,
)

for result in response.results:
    print(f"Score: {result.score:.4f}, Section: {result.chunk.metadata.get('section_title')}")
```

### Индексация через Components

```python
document = await components.loader.load("document.pdf")
chunks = components.pipeline.process(document)
result = await components.indexer.index_chunks(
    chunks, document_id=document.id, source_path=document.source_path
)
print(f"Indexed: {result.chunks_stored} chunks")
```

### RAG ответ через Components

```python
from src.pdf_framework.chains.qa.retrieval_qa import RetrievalQAChain

search_response = await components.search_manager.search(
    query="Что такое конфигуратор?", strategy="hybrid", k=5
)
chain = RetrievalQAChain(
    settings=components.settings.agent,
    api_key=components.settings.anthropic_api_key,
)
answer = await chain.answer(
    question="Что такое конфигуратор?",
    search_response=search_response,
)
```

### Evaluation через Components

```python
from src.pdf_framework.evaluation.rag_triad import RAGTriadEvaluator

evaluator = RAGTriadEvaluator(settings=components.settings)
result = await evaluator.evaluate(
    question="Что такое конфигуратор?",
    answer="Конфигуратор — это...",
    contexts=search_response.results,
)
print(f"Faithfulness: {result.faithfulness:.2f}")
print(f"Answer Relevance: {result.answer_relevance:.2f}")
print(f"Context Relevance: {result.context_relevance:.2f}")
```

---

## Связанные скиллы

- `framework-cli` — все CLI команды
- `framework-api` — все REST endpoints
- `framework-config` — .env параметры
- `framework-quickstart` — установка и первый запуск

## Файлы
- MCP Server: `src/mcp_server/server.py`
- Web UI: `src/ui/app.py`
- UI Pages: `src/ui/pages/` (chat, search, documents, graph, settings)
- Components: `src/api/dependencies/components.py`
- QuickRAG: `src/pdf_framework/__init__.py`
