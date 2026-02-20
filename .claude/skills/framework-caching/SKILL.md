# Framework Caching

## Когда использовать
- "кеш", "кэш", "cache", "TTL"
- "семантический кеш", "semantic cache"
- "очистить кеш", "cache stats", "cache clear"
- "медленный поиск", "ускорить", "повторный запрос"

---

## 3 уровня кеша

| Уровень | Что кеширует | Ускорение | Настройка |
|---------|-------------|-----------|-----------|
| **Семантический** | Результаты поиска (cosine ≥ 0.95) | 5-30 с → < 1 мс | `CACHE__SEMANTIC_ENABLED=true` |
| **Embedding** | Vectorы запросов (LRU) | 415-475 мс → < 1 мс | `CACHE__EMBEDDING_ENABLED=true` |
| **LLM** | Ответы LLM (hash-based) | 3-30 с → < 1 мс | `CACHE__LLM_ENABLED=true` |

---

## Семантический кеш

Сохраняет результаты поиска и возвращает для **похожих** запросов:

```
"конфигуратор в 1С Предприятие"
  → embedding → cosine similarity с кешем
  → "конфигуратор 1С" (similarity 0.97 > 0.95) → HIT → < 1 мс
```

### Настройка

```env
CACHE__SEMANTIC_ENABLED=true
CACHE__SEMANTIC_THRESHOLD=0.95    # Cosine similarity порог
CACHE__SEMANTIC_TTL=3600          # TTL в секундах (1 час)
```

### Автоматическая инвалидация

Кеш очищается при:
- Переиндексации документа
- Удалении документа
- Ручной очистке через API/CLI/UI

---

## Embedding кеш

LRU кеш embedding-векторов запросов:

```
Запрос → embedding model → 1024d vector (415-475 мс)
Повторный запрос → LRU cache hit → 1024d vector (< 1 мс)
```

```env
CACHE__EMBEDDING_ENABLED=true
```

---

## LLM кеш

Кеш ответов LLM по хешу запроса + стратегии + контекста:

```
Ключ = hash(query + strategy + context_hash)
  → Есть в кеше? → мгновенный возврат
  → Нет? → LLM генерация → сохранение
```

```env
CACHE__LLM_ENABLED=true
```

---

## Управление кешем

### CLI

```bash
# Статистика
pdf-framework cache stats
# → Embedding: 156 entries, 23% hit rate
# → LLM: 42 entries, 67% hit rate

# Очистить LLM кеш
pdf-framework cache clear --type llm

# Очистить embedding кеш
pdf-framework cache clear --type embedding

# Очистить весь кеш
pdf-framework cache clear --type all
```

### API

```bash
# Статистика
curl http://localhost:8000/cache/stats

# Очистка
curl -X DELETE http://localhost:8000/cache/clear
```

### Python API

```python
from src.pdf_framework.search.semantic_cache import SemanticCache

cache = SemanticCache(threshold=0.95, ttl=3600)

# Проверить кеш
cached = await cache.get(query="конфигуратор 1С", strategy="hybrid")
if cached:
    return cached  # < 1 мс

# Сохранить в кеш
await cache.put(
    query="конфигуратор 1С",
    strategy="hybrid",
    response=search_response,
)
```

---

## Contextual Retrieval Cache (Phase 50)

Кеш LLM-generated context summaries для Contextual Retrieval:

```
Chunk → hash(content) → SQLite cache
  → Есть? → мгновенный возврат context summary
  → Нет? → LLM генерация → сохранение
```

Экономит **~90% LLM вызовов** при повторной индексации (контекст не меняется для неизменённых чанков).

Файл: `src/pdf_framework/processing/context_generator.py`

---

## Рекомендации

| Сценарий | Рекомендация |
|----------|-------------|
| Development / отладка | Отключить все кеши, чтобы видеть реальные результаты |
| Production | Включить все 3 уровня |
| После переиндексации | Семантический кеш инвалидируется автоматически |
| Изменили промпт / стратегию | `pdf-framework cache clear --type all` |
| Низкий hit rate | Понизить `SEMANTIC_THRESHOLD` (0.90) |

---

## Связанные скиллы

- `framework-config` — все .env параметры кеша
- `framework-cli` — CLI команды cache
- `framework-api` — REST endpoints кеша
- `framework-troubleshooting` — проблемы производительности

## Файлы
- Semantic Cache: `src/pdf_framework/search/semantic_cache.py`
- Cache Config: `src/pdf_framework/config/cache.py`
