# Руководство по быстрому старту

## Предварительные требования

- **Python 3.11+**
- **uv** (рекомендуется) или pip

## 1. Установка

```bash
# Клонировать / скопировать проект
cd D:\1С-Framework

# Windows — автоматическая установка
setup.bat

# Или вручную
uv venv .venv
.venv\Scripts\activate
uv pip install -e ".[dev]"
```

## 2. Настройка

```bash
# Скопировать шаблон настроек
cp .env.example .env
```

Отредактируйте `.env`:

```ini
# Обязательно для RAG и извлечения сущностей
ANTHROPIC_API_KEY=sk-ant-...

# Опционально — эмбеддинги работают локально по умолчанию
# OPENAI_API_KEY=sk-...
```

## 3. Индексация первого документа

```bash
# Активировать виртуальное окружение
.venv\Scripts\activate

# Индексировать PDF
pdf-framework index path/to/your/document.pdf
```

Вывод:
```
Indexed: 42 chunks, 42 embeddings
```

При первом запуске модель эмбеддингов `all-MiniLM-L6-v2` (~90 MB) будет скачана автоматически.

## 4. Поиск

```bash
# Семантический поиск (с автоматическим reranking)
pdf-framework search "ключевые выводы документа"

# С фильтрацией по metadata
pdf-framework search "руководство" --language ru --doc-type documentation
```

Результат — таблица с найденными фрагментами, их оценкой релевантности и источником.

## 5. Вопрос-ответ

```bash
pdf-framework ask "О чём этот документ?"
```

Фреймворк найдёт релевантные фрагменты и сгенерирует ответ через Claude с указанием источников.

## 6. Построение графа знаний (опционально)

Требует `ANTHROPIC_API_KEY` — сущности извлекаются через LLM.

```bash
pdf-framework index path/to/document.pdf --graph

# С контекстуальным обогащением (Phase 3.1)
pdf-framework index path/to/document.pdf --graph --contextual
```

Вывод:
```
Context: generated for 42 chunks
Indexed: 42 chunks, 42 embeddings
Graph: 15 entities, 23 relations
```

После этого доступен граф-поиск:

```bash
pdf-framework search "OpenAI" --strategy graph
```

## 7. Гибридный поиск

```bash
pdf-framework search "нейронные сети" --strategy hybrid
```

Объединяет семантический (vector) и структурный (graph) поиск через Reciprocal Rank Fusion.

## 8. Продвинутый поиск

```bash
# MMR — разнообразные результаты
pdf-framework search "нейронные сети" --strategy mmr --diversity 0.7

# Two-Stage Pipeline — максимальное качество
pdf-framework search "нейронные сети" --strategy two_stage

# С расширением запроса через LLM
pdf-framework search "нейронные сети" --expand-query
```

## 9. Evaluation (Phase 4)

```bash
# Оценка ranking metrics по датасету
pdf-framework eval data/eval/sample_dataset.json --strategy hybrid

# + RAG Triad (LLM-as-a-Judge)
pdf-framework eval data/eval/sample_dataset.json --with-rag-triad
```

## 10. REST API

```bash
# Запустить сервер
pdf-framework server
```

Открыть в браузере:
- Swagger UI: `http://localhost:8000/docs`

Примеры:

```bash
# Индексация
curl -X POST http://localhost:8000/documents/index \
  -H "Content-Type: application/json" \
  -d '{"file_path": "path/to/document.pdf"}'

# Поиск
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "ваш запрос", "strategy": "vector"}'

# RAG-ответ
curl -X POST http://localhost:8000/search/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Ваш вопрос?"}'
```

## 11. Статистика

```bash
pdf-framework stats
```

Покажет количество документов в векторном хранилище и статистику графа знаний.

## Типичные сценарии

### Анализ одного документа

```bash
pdf-framework index report.pdf --graph
pdf-framework ask "Какие основные выводы?"
pdf-framework search "рекомендации" --strategy hybrid
```

### Индексация множества документов

```bash
pdf-framework index doc1.pdf
pdf-framework index doc2.pdf
pdf-framework index doc3.pdf
pdf-framework search "общая тема" -k 10
```

### Использование через API из другого приложения

```python
import httpx

async with httpx.AsyncClient() as client:
    # Индексация
    await client.post("http://localhost:8000/documents/index", json={
        "file_path": "report.pdf"
    })

    # Поиск
    response = await client.post("http://localhost:8000/search/", json={
        "query": "ключевые выводы",
        "strategy": "hybrid",
        "k": 5,
    })
    results = response.json()
```

## Решение проблем

### Ошибка: модель не найдена

При первом запуске sentence-transformers загружает модель. Убедитесь в наличии интернет-соединения.

### Ошибка: ANTHROPIC_API_KEY не задан

Для команд `ask` и `--graph` необходим API-ключ Anthropic. Задайте его в `.env`.

### Медленная индексация

Локальные эмбеддинги вычисляются на CPU. Для ускорения:
- Уменьшите `EMBEDDING__BATCH_SIZE`
- Используйте GPU-совместимую версию PyTorch
- Включите кэш: `EMBEDDING__CACHE_ENABLED=true` (по умолчанию включён)
