# MCP Server Reference

MCP (Model Context Protocol) сервер предоставляет инструменты для работы с фреймворком из Claude Code и других MCP-совместимых клиентов.

## Запуск

```bash
python -m src.mcp_server.server
```

Транспорт по умолчанию: **stdio**.

## Настройка в Claude Code

### VS Code (`.vscode/mcp.json`)

```json
{
  "mcpServers": {
    "pdf-vector-graph": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "D:/1С-Framework"
    }
  }
}
```

### Claude Code Settings

Добавьте в конфигурацию MCP-серверов:

```json
{
  "mcpServers": {
    "pdf-vector-graph": {
      "command": ".venv/Scripts/python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "D:/1С-Framework"
    }
  }
}
```

---

## Инструменты

### index_pdf

Загрузить и проиндексировать PDF-документ.

**Параметры:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|-------------|----------|
| `file_path` | string | да | Путь к PDF-файлу |

**Ответ (JSON):**
```json
{
  "document_id": "a1b2c3d4e5f6g7h8",
  "chunks_stored": 42,
  "embeddings_computed": 42
}
```

---

### search_documents

Поиск по индексированным документам.

**Параметры:**

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `query` | string | да | — | Поисковый запрос |
| `strategy` | string | нет | `"vector"` | `vector`, `graph`, `hybrid` |
| `k` | integer | нет | `5` | Количество результатов |

**Ответ (JSON):**
```json
[
  {
    "chunk_id": "doc1_chunk_abc123",
    "content": "Текст фрагмента (до 500 символов)...",
    "score": 0.892,
    "source": "vector"
  }
]
```

---

### ask_question

Задать вопрос и получить RAG-ответ от LLM.

**Параметры:**

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `question` | string | да | — | Вопрос |
| `strategy` | string | нет | `"hybrid"` | Стратегия поиска контекста |

**Ответ:** текстовый ответ LLM с цитированием источников.

---

### graph_query

Запрос к графу знаний: поиск сущностей и их связей.

**Параметры:**

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `query` | string | да | — | Имя сущности или поисковый термин |
| `entity_type` | string | нет | `""` | Фильтр по типу: `PERSON`, `ORG`, `LOCATION`, `DATE`, `CONCEPT`, `DOCUMENT` |
| `depth` | integer | нет | `1` | Глубина обхода графа |

**Ответ (JSON):**
```json
[
  {
    "entity": {
      "id": "abc123",
      "name": "OpenAI",
      "type": "ORG"
    },
    "relations": [
      {"type": "LOCATED_IN", "target": "def456"},
      {"type": "AUTHORED_BY", "target": "ghi789"}
    ]
  }
]
```

---

### get_stats

Статистика индекса и графа знаний.

**Параметры:** нет.

**Ответ (JSON):**
```json
{
  "vector_store": {
    "document_count": 150
  },
  "graph_store": {
    "node_count": 89,
    "edge_count": 134,
    "connected_components": 5,
    "density": 0.034
  }
}
```
