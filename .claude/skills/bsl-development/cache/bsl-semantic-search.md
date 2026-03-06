# BSL Semantic Search - Кеш знаний

**Версия:** 1.0.0 | **Дата:** 2026-03-06 | **Фаза:** 45

---

## 1. Идентификация

| Параметр | Значение |
|----------|----------|
| **Название** | BSL Semantic Search |
| **Путь** | `src/bsl/semantic_search/` |
| **Entry point** | `python -m src.bsl.semantic_search.mcp` |
| **MCP Tools** | `bsl_search`, `bsl_similar`, `bsl_context`, `bsl_stats` |
| **Qdrant коллекция** | `bsl_code_v2` |

---

## 2. Конфигурация

### Переменные окружения (префикс `BSL_`)

```bash
# Qdrant
BSL_QDRANT_HOST=localhost
BSL_QDRANT_PORT=6333
BSL_COLLECTION_NAME=bsl_code_v2

# Embeddings (Ollama)
BSL_EMBEDDING_MODEL=nomic-embed-text
BSL_EMBEDDING_DIM=768
BSL_OLLAMA_HOST=http://localhost:11434

# Neo4j Graph
BSL_NEO4J_URI=bolt://localhost:17687
BSL_NEO4J_USER=neo4j
BSL_NEO4J_PASSWORD=1c_framework_2026
```

### Важно: Изоляция от PDF коллекций

| Компонент | PDF Framework | BSL Search |
|-----------|---------------|------------|
| **Модель** | E5-large | nomic-embed-text |
| **Размерность** | 1024d | 768d |
| **Коллекция** | `pdf_documents` | `bsl_code_v2` |
| **Тип векторов** | named (dense+bm25) | только dense |

---

## 3. Структура

```
src/bsl/semantic_search/
├── __init__.py           # Публичный API
├── config.py             # pydantic-settings конфигурация
├── mcp.py                # MCP Server entry point
└── services/
    ├── __init__.py
    ├── search.py         # BSLSearchService
    └── embedding.py      # EmbeddingService
```

---

## 4. API

### MCP Tools

#### `bsl_search(query, limit=10, mode="semantic")`

Семантический поиск по BSL коду.

**Параметры:**
- `query` (str): Поисковый запрос
- `limit` (int): Макс. результатов
- `mode` (str): `semantic` | `graph` | `hybrid` | `intelligent`

**Возвращает:**
```
### Результат 1 (релевантность: 0.85)
**Файл**: src/Documents/Doc1/Module.bsl
**Тип модуля**: ObjectModule
**Источник**: semantic
**Функций**: 5
**Описание**: ...
```

#### `bsl_similar(file_path, limit=5)`

Поиск похожих модулей.

#### `bsl_context(file_path, include_dependencies=True)`

Контекст модуля: зависимости, функции.

#### `bsl_stats()`

Статистика индекса.

### Python API

```python
from bsl.semantic_search import BSLSearchService, SearchRequest, SearchMode

service = BSLSearchService()
request = SearchRequest(
    query="обработка проведения",
    mode=SearchMode.INTELLIGENT,
    limit=10
)
results = await service.search(request)
```

---

## 5. Паттерны использования

### Поиск по функциональности

```
query: "обработка проведения документа движения регистры"
→ Найдёт модули с ОбработкаПроведения
```

### Поиск по типу объекта

```
query: "справочник контрагенты форма элемента"
→ Найдёт формы справочников
```

### Поиск по API

```
query: "СправочникМенеджер НайтиПоКоду"
→ Найдёт использование менеджеров справочников
```

---

## 6. Связи с другими компонентами

| Компонент | Связь |
|-----------|-------|
| **Qdrant** | Хранение embeddings, коллекция `bsl_code_v2` |
| **Ollama** | Генерация embeddings через nomic-embed-text |
| **Neo4j** | Граф зависимостей (порт 17687) |
| **ast-grep-mcp** | AST анализ BSL кода |
| **serena** | LSP для BSL |
| **auto-documenter** | Генерация документации |

---

## 7. Диагностика проблем

### Проблема: "Результаты не найдены"

1. Проверить Qdrant: `curl http://localhost:6333/collections/bsl_code_v2`
2. Проверить Ollama: `curl http://localhost:11434/api/tags`
3. Проверить размерность: должна быть 768d

### Проблема: "Qdrant connection refused"

1. Запустить Qdrant: `docker run -p 6333:6333 qdrant/qdrant`
2. Проверить порт: `netstat -an | grep 6333`

### Проблема: "Embedding creation failed"

1. Запустить Ollama: `ollama serve`
2. Загрузить модель: `ollama pull nomic-embed-text`
3. Проверить: `ollama list`

---

## 8. Источники

- **Оригинал:** `D:\1C-Enterprise_Framework\bsl-semantic-search\`
- **Документация:** `docs/roadmap/MIGRATION_1C_ENTERPRISE_FRAMEWORK/PHASE_45_BSL_SEMANTIC_SEARCH.md`
- **Индекс:** `ai-memory-system/data/index/bsl_index_full.json` (3,908 модулей)
