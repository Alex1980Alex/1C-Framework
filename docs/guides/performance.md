# Performance Tuning Guide

Руководство по оптимизации производительности PDF Vector & Graph Framework.

## Содержание

- [Эмбеддинги](#эмбеддинги)
- [Поиск](#поиск)
- [BM25](#bm25)
- [Индексация](#индексация)
- [LLM вызовы](#llm-вызовы)
- [Инфраструктура](#инфраструктура)

---

## Эмбеддинги

### Backend Selection

| Backend | Throughput | Latency | Зависимости |
|---------|-----------|---------|-------------|
| `torch` (default) | Baseline | ~415ms/query | sentence-transformers |
| `onnx` | ~3x CPU | ~140ms/query | onnxruntime |
| `openvino` | ~7x CPU | ~60ms/query | openvino |

```env
# Переключение backend (не требует переиндексации)
EMBEDDING__BACKEND=onnx        # torch | onnx | openvino
```

### GPU Acceleration

```env
# Автоматически, если CUDA доступна
EMBEDDING__DEVICE=cuda         # cuda | cpu | mps (Mac)
EMBEDDING__BATCH_SIZE=256      # Увеличить для GPU (default: 64)
```

При GPU: batch_size=256 даёт ~10x ускорение на индексации. На CPU оптимально 32-64.

### Model Selection

| Модель | Dims | Качество (RU) | Скорость |
|--------|------|---------------|----------|
| `intfloat/multilingual-e5-large` | 1024 | Лучшее | Baseline |
| `intfloat/multilingual-e5-base` | 768 | Хорошее | 2x быстрее |
| `BAAI/bge-m3` | 1024 | Отличное | ~1.5x |
| `all-MiniLM-L6-v2` | 384 | Плохое (EN only) | 5x быстрее |

**Рекомендация**: `multilingual-e5-large` для русских документов. BGE-M3 — альтернатива с встроенными sparse vectors.

> **Важно**: Смена модели требует полной переиндексации!

---

## Поиск

### Latency Breakdown

Типичный запрос (без реранкинга):

| Этап | Время | Доля |
|------|-------|------|
| Классификация запроса | 0-1ms | <1% (rule-based fast classify) |
| BM25 | 5-14ms | 3% |
| Vector search | 415-475ms | 92% |
| Graph merge | 10-20ms | 4% |
| **Итого** | ~450-510ms | |

С LLM реранкером (+1-3s):

| Этап | Время |
|------|-------|
| Retrieval (выше) | ~500ms |
| LLM Reranker | 1-3s |
| **Итого** | ~1.5-3.5s |

### BM25 Early Termination

Для простых фактологических запросов (например, "что такое справочник?") BM25 может вернуть ответ без vector search:

```env
# Порог BM25 для раннего завершения (default: 0.7)
SEARCH__BM25_EARLY_THRESHOLD=0.7

# Минимальное количество результатов BM25 для early termination
SEARCH__BM25_EARLY_MIN_RESULTS=3
```

Результат: 134-191ms вместо 500ms+ для ~40% запросов.

### Section-Aware Search

Two-pass поиск: сначала BM25 определяет доминирующую секцию, затем hybrid search в пределах секции.

```env
SEARCH__SECTION_AWARE_ENABLED=true

# Порог согласия секций (>50% BM25 результатов из одной секции)
SEARCH__SECTION_AGREEMENT_THRESHOLD=0.5
```

### Qdrant Tuning

```env
# Connection pool
VECTOR_STORE__QDRANT_URL=http://localhost:6333
VECTOR_STORE__QDRANT_PREFER_GRPC=true    # gRPC быстрее HTTP на 20-30%
VECTOR_STORE__QDRANT_TIMEOUT=30

# HNSW параметры (set при создании коллекции)
# ef=128 (default) — баланс speed/recall
# ef=256 — лучше recall, медленнее
# m=16 (default) — количество соседей в графе
```

---

## BM25

### FTS5 Optimization

```env
# Вес section_title vs body в FTS5
# title=10x означает: совпадение в заголовке в 10 раз важнее
SEARCH__BM25_TITLE_WEIGHT=10
SEARCH__BM25_BODY_WEIGHT=1
```

### Lemmatization

pymorphy3 лемматизация для русского языка:

```env
# Включена по умолчанию при установке [morphology]
# Даёт +15-20% recall для русских запросов
```

Без лемматизации: "справочники" не найдёт "справочник". С лемматизацией — найдёт.

### BM25 Index Rebuild

После изменения настроек BM25 — обязательно перестроить индекс:

```bash
curl -X POST http://localhost:8000/documents/rebuild-bm25
```

---

## Индексация

### Batch Size

```env
# Chunks per batch при индексации (default: 256)
INDEXING__BATCH_SIZE=256

# Для GPU с большой VRAM: увеличить
INDEXING__BATCH_SIZE=512
```

### Loader Selection

| Loader | Скорость | Качество | Когда использовать |
|--------|----------|----------|--------------------|
| PyMuPDF4LLM | Быстрый (~5s/100p) | Хорошее | Нативные PDF без сложных таблиц |
| Docling | Медленный (~30s/100p) | Отличное | Сложные layout, но теряет страницы |
| Hybrid (default) | Средний (~15s/100p) | Лучшее | 100% coverage, таблицы + images |

```env
# Принудительный выбор loader
PDF__LOADER=hybrid             # hybrid | pymupdf4llm | docling

# Vision OCR для сканированных страниц
PDF__VISION_OCR_ENABLED=true
PDF__VISION_OCR_DPI=200        # 150=быстрее, 200=качественнее, 300=медленно
```

### Image Processing

```env
# Максимум параллельных Vision API вызовов
PDF__VISION_MAX_CONCURRENT=5

# Таймаут для одного изображения (секунды)
PDF__VISION_TIMEOUT=60

# Для PDF с 100+ изображениями: установить общий таймаут
PDF__TOTAL_TIMEOUT=3600        # 1 час
```

### Chunking

```env
# Размер chunk (символов)
SPLITTING__CHUNK_SIZE=1500     # Default. Меньше = точнее retrieval, больше = больше контекста
SPLITTING__CHUNK_OVERLAP=200   # Перекрытие между chunks

# Semantic splitting (медленнее, но лучше качество)
SPLITTING__STRATEGY=recursive  # recursive | semantic | structure_aware
```

---

## LLM вызовы

### Reranker

| Тип | Latency | Качество | Стоимость |
|-----|---------|----------|-----------|
| `llm` (Claude Sonnet) | 1-3s | Лучшее | $0.01-0.03/query |
| `cross_encoder` | 60-120s | Среднее | Бесплатно (локально) |
| `colbert` | 200-500ms | Хорошее | Бесплатно (локально) |
| `flashrank` | 50-100ms | Базовое | Бесплатно (локально) |
| `none` | 0ms | Без реранкинга | Бесплатно |

```env
AGENT__RERANKER_TYPE=llm       # llm | cross_encoder | colbert | flashrank | none
AGENT__RERANKER_TOP_K=5        # Количество результатов после реранкинга
```

### Score Prefilter

Пропуск LLM grading для результатов с низким score:

```env
# Результаты ниже этого порога не отправляются на grading
AGENT__SCORE_PREFILTER=0.1     # 0.0 = грейдить всё, 0.5 = только высокие scores
```

### Ralph Wiggum (Self-Correction)

```env
# Макс. попыток самокоррекции (default: 2)
AGENT__MAX_RETRIES=2

# На каждую retry тратится 1 LLM вызов
# Если качество важнее latency — оставить 2
# Если latency критична — поставить 1
```

---

## Инфраструктура

### Qdrant Docker

```yaml
# docker/docker-compose.yml — Qdrant
qdrant:
  image: qdrant/qdrant:v1.12.0
  environment:
    # Ограничить RAM для индексов
    - QDRANT__STORAGE__WAL_CAPACITY_MB=64
    # Включить mmap для больших коллекций (>100K chunks)
    - QDRANT__STORAGE__ON_DISK_PAYLOAD=true
  deploy:
    resources:
      limits:
        memory: 2G  # 1GB достаточно для <50K chunks
```

### Uvicorn Workers

```bash
# Development (1 worker, auto-reload)
uvicorn src.api.app:app --reload

# Production (4 workers, no reload)
uvicorn src.api.app:app --workers 4 --host 0.0.0.0

# Количество workers: 2 * CPU_CORES + 1
```

### Semantic Cache

```env
# TTL кэша семантического поиска (секунды)
SEARCH__CACHE_TTL=3600         # 1 час

# Порог similarity для cache hit
SEARCH__CACHE_SIMILARITY=0.95  # 0.95 = почти идентичные запросы
```

### LangGraph Checkpointing

```env
# Сохранение state агентов между запросами
AGENT__CHECKPOINTER=sqlite     # sqlite | memory | none
# sqlite: data/agent_checkpoints.db (~1MB per 1000 sessions)
# memory: быстрее, но теряется при перезапуске
```

---

## Quick Reference

### Профили настройки

**Быстрый (минимальная latency)**:
```env
EMBEDDING__BACKEND=openvino
AGENT__RERANKER_TYPE=none
SEARCH__BM25_EARLY_THRESHOLD=0.6
AGENT__SCORE_PREFILTER=0.2
```
Ожидаемая latency: 60-200ms

**Сбалансированный (default)**:
```env
EMBEDDING__BACKEND=torch
AGENT__RERANKER_TYPE=llm
SEARCH__BM25_EARLY_THRESHOLD=0.7
AGENT__SCORE_PREFILTER=0.1
```
Ожидаемая latency: 500ms-3s

**Максимальное качество**:
```env
EMBEDDING__BACKEND=torch
EMBEDDING__MODEL=BAAI/bge-m3
AGENT__RERANKER_TYPE=llm
AGENT__RERANKER_TOP_K=10
SEARCH__SECTION_AWARE_ENABLED=true
AGENT__SCORE_PREFILTER=0.0
AGENT__MAX_RETRIES=2
```
Ожидаемая latency: 3-8s
