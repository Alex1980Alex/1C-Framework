# Дорожная карта: GPU-ускоренная индексация BSL кода через Google Colab

**Дата:** 2026-03-26
**Статус:** Планирование
**Приоритет:** Высокий (блокирует итеративную переиндексацию)

## 1. Проблема и контекст

### Текущее состояние (CPU Bottleneck)

| Параметр | Значение |
|----------|---------|
| BSL файлов | 2,027 |
| Chunks | ~22,000 (после дедупликации UUID5) |
| Raw chunks | ~35,000 (до дедупликации) |
| Модель | intfloat/multilingual-e5-large (1024d) |
| Железо | 16 ядер CPU, 32 GB RAM, AMD Radeon (без CUDA) |
| Qdrant | localhost:6333 (Docker, `bsl_code_v3`) |

### Замеры производительности (2026-03-26)

| Подход | Время | Скорость | Примечание |
|--------|-------|----------|-----------|
| PyTorch, 1 процесс | ~7.3 ч (оценка) | ~50 ch/min | Убит досрочно |
| PyTorch, 4 воркера | 13.4 ч | 42 ch/min | CPU contention, медленнее одного |
| FastEmbed ONNX, 1 процесс | 11.7 ч | 32 ch/min | ONNX Runtime, завис в конце |

**Вывод:** На CPU без GPU параллелизация не помогает. Embedding — чистый compute bottleneck.

### Целевое ускорение

| Hardware | Ожидаемая скорость E5-large | Время 22k chunks | Стоимость |
|----------|---------------------------|-------------------|-----------|
| CPU (текущий) | ~50 ch/min | 7-13 часов | $0 |
| **Colab T4 (16GB)** | **~1500 seq/s** | **~15-20 мин** | **$0 (Free)** |
| Colab A100 (40GB) | ~4000 seq/s | ~5-8 мин | Compute Units |
| Vast.ai RTX 3090 | ~2500 seq/s | ~10 мин | ~$0.03 |

## 2. Архитектура решения

Гибридная: **локальная подготовка → облачный GPU → локальный импорт**.

```
LOCAL                          COLAB (T4 GPU)
  │                               │
  ├── Parse BSL files             │
  ├── Chunk (BSLChunker)          │
  ├── Enrich (MetadataExtractor   │
  │   + CallGraphStore)           │
  ├── Export chunks.jsonl ──────► Upload
  │                               ├── Load E5-large (GPU)
  │                               ├── Batch embed (1500 seq/s)
  │                               ├── Export vectors.npz
  │   Download ◄─────────────────── │
  ├── Import vectors + payload    │
  │   → Qdrant upsert             │
  └── DONE                        │
```

**Почему не полностью в Colab:**
- Qdrant в локальном Docker (нет смысла тянуть через ngrok)
- MetadataExtractor и CallGraphStore требуют локальные файлы (cache/bsl_call_graph.db, 380 MB)
- Безопасность: BSL код не уходит в облачное хранилище надолго

## 3. Фазы реализации

### Phase 1: Export Script — подготовка chunks локально

**Цель:** Разделить парсинг/enrichment (CPU) и embedding (GPU).

- [ ] Создать `scripts/export_chunks_for_gpu.py`
  - Парсит BSL файлы (BSLASTParser + BSLChunker)
  - Enriches через MetadataExtractor + CallGraphStore
  - Сохраняет в `data/export/chunks_payload.jsonl` (текст + chunk_id + payload)
  - Формат: `{"chunk_id": "...", "text": "...", "payload": {...}}` per line
- [ ] Создать `data/export/.gitignore` (игнорировать *.jsonl, *.npz)

**Оценка размера:** ~22k chunks * ~500 байт/chunk = ~11 MB JSONL

### Phase 2: Colab Notebook — GPU embedding

**Цель:** Embed всё на T4 за 15-20 минут.

- [ ] Создать `notebooks/colab_bsl_embedder.ipynb`
  - Установка: `pip install sentence-transformers`
  - Upload `chunks_payload.jsonl` (через виджет или Google Drive)
  - Загрузка E5-large на GPU: `SentenceTransformer("intfloat/multilingual-e5-large", device="cuda")`
  - Batch embedding: batch_size=128-256 (T4 16GB VRAM)
  - Prefix: "passage: " + text[:8000]
  - Progress bar (tqdm)
  - Сохранение: `vectors.npz` (numpy, float32, shape [N, 1024])
  - Сохранение: `chunk_ids.json` (список chunk_id в том же порядке)
  - Download архив

**VRAM расчет:** E5-large ~1.2 GB + batch 256 * 512 tokens * 1024d * 4 bytes ~ 0.5 GB → итого ~2 GB, T4 (16 GB) с запасом.

### Phase 3: Import Script — загрузка в Qdrant

**Цель:** Быстрый upsert vectors + payloads в локальный Qdrant.

- [ ] Создать `scripts/import_vectors_to_qdrant.py`
  - Читает `vectors.npz` и `chunks_payload.jsonl`
  - Матчит по chunk_id
  - Генерирует UUID5 point IDs (тот же UUID_NAMESPACE)
  - Batch upsert в Qdrant (batch_size=500, Qdrant upsert быстрый)
  - `--recreate` флаг для пересоздания коллекции
  - Progress bar

**Ожидаемое время импорта:** 22k points → Qdrant ~ 30-60 сек

### Phase 4: Automation Wrapper

**Цель:** Один скрипт для полного цикла.

- [ ] Создать `scripts/gpu_reindex_bsl.py` (или .bat)
  - Step 1: Export chunks (локально, ~2-3 мин)
  - Step 2: Prompt user: "Upload to Colab, run notebook, download vectors.npz"
  - Step 3: Import vectors (локально, ~1 мин)
  - Step 4: Verify (сравнить point count, тестовый поиск)
- [ ] Опционально: автоматизация через Google Drive mount
  - Export → Google Drive sync folder
  - Colab reads from Drive, writes vectors back
  - Import script polls for vectors.npz

### Phase 5 (Optional): Qdrant Cloud

Полностью облачный вариант без локального Docker.

- [ ] Qdrant Cloud Free Tier (1 GB, ~22k points 1024d = ~90 MB — помещается)
- [ ] Colab пишет напрямую в Qdrant Cloud через API key
- [ ] Локальный MCP сервер переключается на облачный URL
- [ ] Backup: export snapshot → local restore

## 4. Ограничения и риски

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| Colab квоты (GPU часы/день) | Средняя | 22k chunks за 15 мин — влезает в Free Tier. При 10x росте → Colab Pro ($10/мес) |
| Несовместимость версий модели | Высокая | Фиксировать версию sentence-transformers в requirements-colab.txt |
| Сетевые задержки upload/download | Низкая | JSONL ~11 MB, vectors ~90 MB — 1-2 мин на приличном канале |
| Синхронизация chunk_id | Низкая | Детерминированные UUID5, строгий порядок в JSONL |
| Colab session disconnect | Средняя | Checkpoint каждые 5000 chunks, resume support |

## 5. Файлы для создания

| Файл | Фаза | Описание |
|------|------|---------|
| `scripts/export_chunks_for_gpu.py` | 1 | Парсинг + enrichment → JSONL |
| `data/export/.gitignore` | 1 | Игнор временных файлов |
| `notebooks/colab_bsl_embedder.ipynb` | 2 | Colab notebook для GPU embedding |
| `scripts/import_vectors_to_qdrant.py` | 3 | Импорт vectors → Qdrant |
| `scripts/gpu_reindex_bsl.py` | 4 | Automation wrapper |

## 6. Критерии завершения

1. **Время:** Полный цикл (Export → Colab → Import) <= 30 минут
2. **Качество:** Векторы идентичны CPU-версии (cosine similarity > 0.999 на тестовом сэмпле)
3. **Автоматизация:** Максимум 3 ручных действия (запуск export, запуск Colab cell, запуск import)
4. **Поиск:** `bsl_hybrid_search` возвращает эквивалентные результаты после GPU-индексации
5. **Документация:** README секция "GPU Indexing via Colab" с пошаговой инструкцией

## 7. Приоритет фаз

| Фаза | Приоритет | Effort | Impact |
|------|-----------|--------|--------|
| Phase 1 (Export) | P0 | 2 часа | Разблокирует Phase 2-3 |
| Phase 2 (Colab) | P0 | 3 часа | Основное ускорение |
| Phase 3 (Import) | P0 | 2 часа | Замыкает цикл |
| Phase 4 (Automation) | P1 | 2 часа | UX improvement |
| Phase 5 (Qdrant Cloud) | P2 | 4 часа | Опционально |
