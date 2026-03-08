# Фаза 56: 1C-Docs-RAG Migration

**Tier:** 5 — Post-Migration
**Статус:** IN PROGRESS
**Зависимости:** Phase 44 (Infrastructure), Phase 50 (LLM Rotation)
**Оценка:** ~3 часа

---

## Цель

Миграция MCP сервера `1c-docs-rag` из `D:\1C-Enterprise_Framework\scripts\docs-mcp\` в `D:\1С-Framework\tools\1c-docs-rag\`. Перенос SQLite БД + индекса, обновление путей, интеграция в lazy-mcp registry.

---

## Архитектура исходного сервера

### Компоненты (7 модулей)

| Файл | Назначение | Размер |
|------|-----------|--------|
| `mcp_server.py` | MCP entry point, 15 tools | 73KB |
| `hybrid_search_engine.py` | FTS5 + Semantic search | 128KB |
| `rag_module.py` | RAG pipeline + LLM | 29KB |
| `reranker.py` | Cross-encoder/hybrid reranking | 18KB |
| `metadata_filter.py` | Faceted search | 22KB |
| `hallucination_detector.py` | Claim validation | 18KB |
| `smart_index_bsl.py` | Multi-language indexer | 22KB |
| `edt_xml_parser.py` | EDT XML parser | 35KB |

### Storage

| Артефакт | Путь (старый) | Формат |
|----------|---------------|--------|
| Search index | `cache/docs-mcp/hybrid_search.db` | SQLite (WAL, FTS5 + embeddings BLOB) |
| RAG cache | `cache/rag/*.json` | JSON (MD5-hashed query, 24h TTL) |

### Dependencies

- `mcp >= 0.1.0`
- `sentence-transformers` (lazy, model: `paraphrase-multilingual-MiniLM-L12-v2`, 384d)
- `aiohttp` (async HTTP for LLM)
- `watchdog` (optional, file watcher)
- `numpy`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCS_ROOT` | `D:/1C-Enterprise_Framework/docs` | Doc root(s), `;` separated |
| `LLM_ROTATION_URL` | `http://localhost:8000` | LLM proxy endpoint |
| `RAG_CACHE_TTL_HOURS` | `24` | Cache TTL |

---

## Шаги миграции

### 56.1 Создать директорию и скопировать исходники

```
tools/1c-docs-rag/
  src/
    mcp_server.py
    hybrid_search_engine.py
    rag_module.py
    reranker.py
    metadata_filter.py
    hallucination_detector.py
    smart_index_bsl.py
    edt_xml_parser.py
  cache/                  # runtime, .gitignore
  requirements.txt
  README.md
```

### 56.2 Создать venv + установить dependencies

```bash
cd tools/1c-docs-rag
python -m venv .venv
.venv/Scripts/pip install mcp aiohttp numpy watchdog sentence-transformers
```

### 56.3 Перенести SQLite БД

Скопировать `D:\1C-Enterprise_Framework\cache\docs-mcp\hybrid_search.db` → `tools/1c-docs-rag/cache/docs-mcp/hybrid_search.db`

### 56.4 Обновить пути в коде

- `DOCS_ROOT` default → `D:/1С-Framework/docs`
- `LLM_ROTATION_HTTP_SCRIPT` → убрать (LLM Rotation уже мигрирован как MCP)
- `cache/` paths → relative to script dir

### 56.5 Обновить registry.yaml

```yaml
1c-docs-rag:
  command: "D:/1С-Framework/tools/1c-docs-rag/.venv/Scripts/python.exe"
  args: ["src/mcp_server.py"]
  cwd: "D:/1С-Framework/tools/1c-docs-rag"
  env:
    PYTHONIOENCODING: "utf-8"
    DOCS_ROOT: "D:/1С-Framework/docs"
  timeout: 7200
  category: "1c-development"
  description: "1C documentation RAG search (15 tools)"
```

### 56.6 Тест: запуск сервера

```bash
cd tools/1c-docs-rag
.venv/Scripts/python.exe src/mcp_server.py
# Verify MCP initialize response
```

---

## Чеклист

- [ ] Директория `tools/1c-docs-rag/` создана
- [ ] Исходники скопированы (8 модулей)
- [ ] venv создан, dependencies установлены
- [ ] SQLite БД перенесена
- [ ] Пути обновлены (DOCS_ROOT, cache)
- [ ] registry.yaml обновлён (убран NOTE: Not yet migrated)
- [ ] Сервер запускается без ошибок
- [ ] .gitignore для cache/
