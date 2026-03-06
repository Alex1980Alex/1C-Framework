# Фаза 45: BSL Semantic Search + SonarQube

**Tier:** 1 — Фундамент
**Статус:** DONE
**Зависимости:** Фаза 44 (Infrastructure)
**Оценка:** ~6 часов
**Блокирует:** Фаза 53 (Fine-tuning)
**Завершено:** 2026-03-06

---

## Цель

Перенести систему семантического поиска по BSL-коду (3,908 модулей, Qdrant, Neo4j) и интеграцию SonarQube в `src/bsl/`.

---

## Компоненты

### BSL Semantic Search

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\bsl-semantic-search\` |
| **Цель** | `D:\1С-Framework\src\bsl\semantic_search\` |
| **Технологии** | Python, FastMCP, Qdrant, Neo4j, Ollama |
| **LOC** | ~5,000 |
| **Qdrant коллекция** | `bsl_code_v2` |
| **Embedding модель** | `nomic-embed-text` (768d) — НЕ E5 (1024d как в PDF) |
| **Индекс** | 3,908 BSL модулей |
| **MCP сервер** | FastMCP (server_fastmcp.py) |

**Архитектура:**
- MCP Server (FastMCP) — основной интерфейс для Claude Code
- Qdrant — хранение и поиск embeddings (коллекция `bsl_code_v2`, 768d, cosine)
- Neo4j — граф-аналитика зависимостей модулей (bolt://localhost:17687)
- OllamaManager — автозапуск Ollama для embeddings
- Context Manager — управление контекстом поиска

**Исходная структура:**
```
bsl-semantic-search/
├── mcp_server/
│   └── server_fastmcp.py       # MCP server entry point
├── services/
│   ├── search_engine.py        # Semantic search core
│   ├── context_manager.py      # Context management
│   └── ollama_manager.py       # Ollama auto-restart
├── mcp_local_scripts/
│   └── memory_server_fixed.py  # Memory server (conversation-memory)
├── ARCHITECTURE_MEMORY.md
└── README.md
```

### SonarQube Integration

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\sonar_integration\` |
| **Цель** | `D:\1С-Framework\src\bsl\sonar\` |
| **Технологии** | Python |
| **LOC** | ~3,000 |

---

## Шаги

### 45.1 Перенести bsl-semantic-search

```bash
cp -r D:/1C-Enterprise_Framework/bsl-semantic-search/mcp_server src/bsl/semantic_search/mcp_server
cp -r D:/1C-Enterprise_Framework/bsl-semantic-search/services src/bsl/semantic_search/services
cp D:/1C-Enterprise_Framework/bsl-semantic-search/ARCHITECTURE_MEMORY.md src/bsl/semantic_search/
```

**Целевая структура:**
```
src/bsl/semantic_search/
├── __init__.py
├── mcp_server/
│   ├── __init__.py
│   └── server_fastmcp.py
├── services/
│   ├── __init__.py
│   ├── search_engine.py
│   ├── context_manager.py
│   └── ollama_manager.py
├── config.py                   # НОВЫЙ: pydantic-settings
├── mcp.py                      # НОВЫЙ: entry point
└── ARCHITECTURE_MEMORY.md
```

**Критерий:** `from src.bsl.semantic_search import search_engine` работает.

### 45.2 Адаптировать Qdrant-клиент

Создать `config.py` — pydantic-settings конфиг с env_prefix `BSL_`:

- `qdrant_url` = http://localhost:6333 (общий инстанс)
- `collection_name` = bsl_code_v2 (изолированная коллекция)
- `embedding_model` = nomic-embed-text
- `embedding_dim` = 768
- `neo4j_url` = bolt://localhost:17687

**ВАЖНО — изоляция от PDF коллекций:**
- PDF: E5-large (1024d) + named vectors (dense + bm25 sparse)
- BSL: nomic-embed-text (768d) + только dense

Один Qdrant инстанс, разные коллекции — конфликтов нет.

### 45.3 Перенести sonar_integration

```bash
cp -r D:/1C-Enterprise_Framework/sonar_integration src/bsl/sonar
```

Адаптация: обновить импорты `sonar_integration.*` -> `src.bsl.sonar.*`

**Критерий:** `python -m src.bsl.sonar.cli --help` работает.

### 45.4 Создать MCP entry point

`src/bsl/semantic_search/mcp.py` — запуск через `python -m src.bsl.semantic_search.mcp`.

**MCP Tools:**
1. `bsl_search` — семантический поиск по BSL-коду
2. `bsl_context` — контекст модуля
3. `bsl_similar` — похожие модули
4. `bsl_graph` — граф зависимостей (Neo4j)

### 45.5 Интеграционный тест

`tests/integration/test_bsl_search.py` — 3 теста:
1. Поиск по запросу возвращает результаты с score > 0.5
2. Коллекция содержит >= 3900 points
3. Размерность векторов = 768

Используется qdrant_client (см. скилл `qdrant-operations`).

### 45.6 Создать кеш знаний

`.claude/skills/bsl-development/cache/bsl-semantic-search.md` — 8 категорий:
идентификация, конфигурация, структура, API, паттерны, связи, диагностика, источники.

### 45.7 Перенести/проверить Qdrant-коллекцию

```bash
# Проверка
curl http://localhost:6333/collections/bsl_code_v2 | python -m json.tool
# points_count ~= 3908, vector_size = 768

# Если новый инстанс — snapshot или re-index
curl -X POST "http://localhost:6333/collections/bsl_code_v2/snapshots"
```

---

## Qdrant архитектура после миграции

```
Qdrant (localhost:6333)
├── pdf_documents          # 1024d, E5-large, named (dense+bm25), 1012 chunks
├── graph_embeddings       # 1024d, E5-large, 6694 points
├── bsl_code_v2            # 768d, nomic-embed-text, ~3908 modules  <-- ЭТА ФАЗА
├── ai_memory              # 768d (Фаза 49)
└── learned_patterns       # 768d, Google Gemini (Фаза 49)
```

---

## Чеклист завершения

- [x] `src/bsl/semantic_search/` содержит все модули (config.py, mcp.py, services/search.py, services/embedding.py)
- [x] `src/bsl/sonar/` содержит SonarQube integration (cli.py, config_manager.py, report_generator.py, rules_manager.py)
- [x] `config.py` с BSLSearchSettings (pydantic-settings) — импорт OK
- [x] MCP entry point `mcp.py` работает (9.4 KB)
- [x] Импорты адаптированы к `src.bsl.semantic_search.*`
- [x] Интеграционные тесты созданы (tests/integration/test_bsl_search.py)
- [x] Кеш знаний создан (cache/bsl-semantic-search.md)
- [ ] Qdrant коллекция bsl_code_v2 доступна (3,908 points, 768d) — требует запущенный Qdrant
- [x] `.mcp.json` содержит bsl-semantic-search
- [ ] Git commit: `feat: Phase 45 — BSL Semantic Search + Sonar migration`
