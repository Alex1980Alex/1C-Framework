---
name: framework-troubleshooting
description: "Устранение ошибок PDF Framework, оптимизация производительности, миграция. Триггеры: 'ошибка', 'не работает', 'error', 'проблема', 'troubleshoot', 'debug', 'медленно', 'slow', 'миграция', 'migration', 'performance', 'timeout'. НЕ для внутренней отладки кода — используй operational skills."
---

# Framework Troubleshooting

## Когда использовать
- "ошибка ConnectionError", "BM25 не находит", "reranker не работает"
- "поиск медленный", "как ускорить", "performance"
- "смена модели", "миграция", "обновление Qdrant"

---

## Quick Diagnostics (5 шагов)

1. **Qdrant жив?** — `curl http://localhost:6333/healthz`
2. **API жив?** — `curl http://localhost:8000/health`
3. **Документы есть?** — `curl http://localhost:8000/documents/list`
4. **BM25 собран?** — `curl -X POST http://localhost:8000/documents/rebuild-bm25`
5. **.env корректен?** — проверить обязательные: `ANTHROPIC__API_KEY`, `VECTOR_STORE__QDRANT_URL`

---

## Частые ошибки

### Подключение и инфраструктура

| Симптом | Причина | Решение |
|---------|---------|---------|
| `ConnectionError: Cannot connect to Qdrant` | Qdrant не запущен | `docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v $(pwd)/data/qdrant_storage:/qdrant/storage qdrant/qdrant:v1.15.5` |
| API не запускается | .env неполный или Qdrant недоступен | Проверить обязательные параметры, `curl http://localhost:6333/healthz` |
| `ModuleNotFoundError: arq` | Не установлены зависимости | `pip install -e ".[all]"` |

### Поиск

| Симптом | Причина | Решение |
|---------|---------|---------|
| BM25 возвращает 0 результатов | FTS5 индекс пуст | `curl -X POST http://localhost:8000/documents/rebuild-bm25` |
| 0 результатов vector search | Нет проиндексированных документов | `python -m src.cli.main index "doc.pdf"` |
| Низкие vector scores | Dimension mismatch | Проверить `EMBEDDING__MODEL` и `EMBEDDING__DIMENSIONS` (1024 для E5) |
| Фильтры не работают | metadata не enriched | Переиндексировать: `python -m src.cli.main index "doc.pdf" --full-reindex` |
| GraphRAG пустой результат | Граф не построен | `python -m src.cli.main index "doc.pdf" --graph --communities` |
| Section-first пустой | Неверный section_number | Проверить `_extract_section_number()`, `section_title` в metadata |

### Reranking и агенты

| Симптом | Причина | Решение |
|---------|---------|---------|
| `ModuleNotFoundError: sentence_transformers` | Не установлен пакет | `pip install sentence-transformers` или `AGENT__RERANKER_TYPE=llm` |
| Reranker timeout | Z.AI proxy latency | Проверить `ANTHROPIC__BASE_URL`, уменьшить `AGENT__RERANKER_TOP_K` |
| Image descriptions пустые | Vision не настроен | Проверить `VISION__MODEL`, API ключ с доступом к Vision |
| `ValueError: Expected dimension 1024, got 384` | Модель не соответствует .env | Обновить `EMBEDDING__DIMENSIONS`, переиндексировать |
| Agent бесконечный loop | max_retries не ограничен | Проверить `SELF_RAG__MAX_REWRITE_ATTEMPTS=2` |

---

## Performance — Latency по стратегиям

| Стратегия | Без reranking | С LLM reranking |
|-----------|--------------|-----------------|
| `bm25` | 5-14 мс | ~5 с |
| `section_first` | 50-100 мс | ~5 с |
| `adaptive` (simple) | 125 мс | — |
| `vector` | 415-475 мс | ~5.5 с |
| `hybrid` | ~500 мс | ~5.5 с |
| `graphrag_local` | 1-3 с | ~8 с |
| `graphrag_global` | 5-15 с | — |
| `deep_research` | 10-30 с | — |

### Turbo Pipeline (автоматический)

```
simple (90% запросов):  BM25 early termination → 125 мс (31x ускорение)
moderate:               Hybrid + Reranking → 3-5 с
complex:                Decomposition + Multi-step → 10-30 с
```

### Оптимизация скорости

| # | Приём | Выигрыш |
|---|-------|---------|
| 1 | `--strategy bm25` для точных терминов | 5-14 мс |
| 2 | `--no-rerank` отключить reranking | -5 секунд |
| 3 | `-k 3` уменьшить top-k | Меньше grading |
| 4 | `CACHE__SEMANTIC_ENABLED=true` | <1 мс повторные |
| 5 | `AGENT__RERANKER_TYPE=flashrank` | ~100 мс вместо ~5 с |
| 6 | GPU для embeddings | 5-10x ускорение |

```bash
# GPU для embeddings
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### Оптимизация качества

| # | Приём | Описание |
|---|-------|----------|
| 1 | `--strategy hybrid` | Лучшее качество (vector + BM25 + graph) |
| 2 | `AGENT__RERANKER_TYPE=llm` | Осмысленное ранжирование |
| 3 | `autorag` | Автоподбор параметров |
| 4 | `--graph --communities` | Индексация с графом |

---

## Guardrails — безопасность (Phase 53)

Три уровня защиты через middleware `GuardrailsMiddleware`:

### PII Detection (`pii_detector.py`)

| Тип | Паттерн | Пример |
|-----|---------|--------|
| EMAIL | regex | user@example.com |
| PHONE | regex | +7 (999) 123-45-67 |
| ИНН | 10-12 цифр + контрольная сумма | 7707083893 |
| СНИЛС | XXX-XXX-XXX XX | 123-456-789 01 |
| Паспорт РФ | XX XX XXXXXX | 45 06 123456 |
| Credit Card | Luhn validation | 4111 1111 1111 1111 |
| SSN | XXX-XX-XXXX | 123-45-6789 |

Режимы: `detect` (логирование), `redact` (замена на `[PII:TYPE]`), `block` (отклонение запроса).

### Prompt Injection Defense (`injection_defense.py`)

9 категорий паттернов с confidence scoring (0.0-1.0):
- Direct override: "ignore previous instructions", "system prompt leak"
- Role-play: "you are DAN", "do anything now"
- Delimiter injection: XML tags, markdown code blocks
- Encoding tricks: Base64 evasion, unicode homoglyphs (Cyrillic/Latin), zero-width chars

Режимы: `log` (только лог), `warn` (предупреждение), `block` (отклонение при score > threshold).

### Content Filter (`content_filter.py`)

| Проверка | Default | Описание |
|----------|---------|----------|
| Max query length | 10,000 символов | Защита от oversized запросов |
| Max file size | 100 MB | Защита при upload |
| Max response length | 50 KB | Защита от explosion |
| URL validation | Safe-domain list | Детекция hallucinated URLs |

### Конфигурация

```env
GUARDRAILS__PII_MODE=detect          # detect|redact|block
GUARDRAILS__INJECTION_MODE=warn      # log|warn|block
GUARDRAILS__INJECTION_THRESHOLD=0.7  # Порог confidence (0.0-1.0)
GUARDRAILS__MAX_QUERY_LENGTH=10000
GUARDRAILS__MAX_FILE_SIZE_BYTES=104857600
```

### Диагностика Guardrails

| Симптом | Причина | Решение |
|---------|---------|---------|
| Запрос блокируется | PII mode=block | Проверить `GUARDRAILS__PII_MODE`, переключить на `redact` |
| False positive injection | Порог слишком низкий | Увеличить `GUARDRAILS__INJECTION_THRESHOLD` (0.8-0.9) |
| Файл отклоняется при upload | Превышен размер | Увеличить `GUARDRAILS__MAX_FILE_SIZE_BYTES` |

---

## Миграция

### Смена модели эмбеддингов

```bash
# 1. Обновить .env
EMBEDDING__MODEL=new-model-name
EMBEDDING__DIMENSIONS=1024

# 2. Полная переиндексация
python -m src.cli.main index "document.pdf" --full-reindex

# 3. Пересобрать BM25
curl -X POST http://localhost:8000/documents/rebuild-bm25
```

**Доступные модели:**

| Модель | Размерность | Prefix |
|--------|------------|--------|
| `intfloat/multilingual-e5-large` | 1024 | `"query: "` / `"passage: "` |
| `BAAI/bge-m3` | 1024 | Нет |
| `ai-sage/Giga-Embeddings-instruct` | 1024 | Instruction-based |
| `jina-embeddings-v3` | 1024 | Нет (API) |

### ChromaDB → Qdrant

```bash
# 1. Запустить Qdrant
docker run -d --name qdrant -p 6333:6333 \
    -v $(pwd)/data/qdrant_storage:/qdrant/storage qdrant/qdrant:v1.15.5

# 2. Обновить .env
VECTOR_STORE__PROVIDER=qdrant
VECTOR_STORE__QDRANT_URL=http://localhost:6333

# 3. Переиндексировать
python -m src.cli.main index "documents/" --recursive --full-reindex --graph
```

### NetworkX → Neo4j

```bash
# 1. Запустить Neo4j
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/password neo4j:5.15

# 2. Обновить .env
GRAPH_STORE__PROVIDER=neo4j
GRAPH_STORE__NEO4J_URI=bolt://localhost:7687
GRAPH_STORE__NEO4J_USER=neo4j
GRAPH_STORE__NEO4J_PASSWORD=password

# 3. Переиндексировать граф
python -m src.cli.main index "documents/" --recursive --graph --communities
```

### Обновление Qdrant

```bash
docker stop qdrant && docker rm qdrant
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/data/qdrant_storage:/qdrant/storage qdrant/qdrant:v1.15.5
# Данные сохраняются через volume
```

### BM25 backend: FTS5 → Qdrant native

```env
SEARCH__BM25_BACKEND=qdrant
```
```bash
curl -X POST http://localhost:8000/documents/rebuild-bm25
```

---

## Связанные скиллы

- `framework-config` — все .env переменные
- `search-pipeline-debug` — отладка поисковых стратегий (internals)
- `indexing-pipeline` — отладка pipeline индексации (internals)

## Файлы

- Health: [health.py](src/api/routes/health.py)
- BM25: [bm25_store.py](src/pdf_framework/search/bm25_store.py)
- Config: [_base.py](src/pdf_framework/config/_base.py)
- Guardrails: [guardrails/](src/pdf_framework/guardrails/) (pii_detector, injection_defense, content_filter)
- Middleware: [guardrails.py](src/api/middleware/guardrails.py)
