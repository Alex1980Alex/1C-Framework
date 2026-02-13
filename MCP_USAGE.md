# Использование PDF Framework через MCP

## ✅ Настройка завершена

MCP сервер настроен в [.vscode/mcp.json](.vscode/mcp.json) с 5 инструментами.

## 🔄 Перезапуск Claude Code

**Чтобы активировать MCP инструменты:**
1. Закройте текущую сессию Claude Code
2. Перезапустите VS Code или откройте новое окно Claude Code
3. MCP инструменты станут доступны

## 🛠 Доступные MCP инструменты

### 1. `index_pdf` - Индексация PDF

```python
# Пример вызова (из Claude Code)
mcp__pdf-vector-graph__index_pdf(
    file_path="data/pdfs/your_document.pdf"
)
```

**Возвращает:**
```json
{
  "document_id": "abc123",
  "chunks_stored": 31,
  "embeddings_computed": 31
}
```

### 2. `search_documents` - Поиск по документам

```python
# Vector search (семантический)
mcp__pdf-vector-graph__search_documents(
    query="что такое 1С Предприятие",
    strategy="vector",
    k=5
)

# Hybrid search (vector + graph)
mcp__pdf-vector-graph__search_documents(
    query="конфигурация и платформа",
    strategy="hybrid",
    k=5
)
```

**Возвращает:** JSON массив с результатами
```json
[
  {
    "chunk_id": "abc_0",
    "content": "текст найденного фрагмента...",
    "score": 0.624,
    "source": "vector"
  }
]
```

### 3. `ask_question` - Вопросы-ответы через RAG

```python
mcp__pdf-vector-graph__ask_question(
    question="Объясни основные компоненты 1С Предприятие",
    strategy="hybrid"
)
```

**Возвращает:** Текстовый ответ с цитатами источников

### 4. `graph_query` - Запрос к графу знаний

```python
mcp__pdf-vector-graph__graph_query(
    query="компания",
    entity_type="",
    depth=1
)
```

**Возвращает:** JSON с найденными сущностями и связями

### 5. `get_stats` - Статистика индексации

```python
mcp__pdf-vector-graph__get_stats()
```

**Возвращает:**
```json
{
  "vector_store": {
    "document_count": 31
  },
  "graph_store": {
    "node_count": 0,
    "edge_count": 0,
    "connected_components": 0,
    "density": 0
  }
}
```

## 🎯 Примеры использования в Claude Code

После перезапуска вы сможете просто писать:

```
Вы: Найди в документах информацию про установку 1С

Claude Code: [Автоматически вызовет mcp__pdf-vector-graph__search_documents]
```

```
Вы: Проиндексируй новый файл data/pdfs/manual.pdf

Claude Code: [Вызовет mcp__pdf-vector-graph__index_pdf]
```

## 📊 Текущий статус

- ✅ **Vector Store:** 31 chunks проиндексировано
- ✅ **Файл:** "Введение __ 1С_Предприятие 8.3.26. Документация.pdf"
- ❌ **Graph Store:** пустой (требуется валидный Anthropic API ключ)

## 🔧 Проблемы и решения

### Проблема: Graph Store пустой

**Причина:** API ключ не распознается как валидный Anthropic ключ

**Решения:**
1. **Получить ключ Anthropic:** [console.anthropic.com](https://console.anthropic.com/)
2. **Использовать только Vector Search:** работает без LLM
3. **Настроить custom endpoint:** если используете локальный AI

### Проблема: Кодировка в консоли Windows

**Решение:** Используйте:
- Python скрипт [test_search.py](test_search.py)
- MCP инструменты через Claude Code (после перезапуска)
- REST API (запустить через `python -m src.cli.main server`)

## 🚀 Быстрый старт сейчас

Пока MCP не перезапущен, используйте Python API:

```bash
# Запустить тестовый скрипт
python test_search.py

# Или REST API сервер
python -m src.cli.main server
# Доступен на http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

## 📚 Дополнительно

- **CLI команды:** `python -m src.cli.main --help`
- **Конфигурация:** [.env](.env)
- **Результаты поиска:** [data/search_results.json](data/search_results.json)
- **Документация:** [CLAUDE.md](CLAUDE.md)
