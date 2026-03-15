---
name: indexing-pipeline
description: "Indexing Pipeline — индексация PDF документов, загрузчики, сплиттеры, page_offsets. ИСПОЛЬЗУЙ когда индексируешь PDF, отлаживаешь потерянные страницы, настраиваешь loader/splitter, выбираешь флаги индексации, переиндексируешь. Триггеры: 'индексировать', 'индексация', 'loader', 'splitter', 'page_offsets', 'batch indexing', 'потерялись страницы', 'ошибка индексации', 'переиндексация'. НЕ для поиска после индексации (→ search-pipeline-debug)."
---

# Indexing Pipeline

## Когда использовать
- "как проиндексировать", "ошибка индексации", "потерялись страницы"
- "loader", "splitter", "page_offsets", "batch indexing"
- "какие флаги индексации", "как индексировать с графом"
- Работа с новыми PDF, переиндексация, отладка pipeline

---

## Для пользователя — индексация документов

### Quick Reference

| Задача | Команда |
|--------|---------|
| Быстрая индексация | `python -m src.cli.main index "doc.pdf"` |
| С графом знаний | `python -m src.cli.main index "doc.pdf" --graph` |
| Максимальное качество | `python -m src.cli.main index "doc.pdf" --graph --communities --parent-child --raptor --contextual` |
| Директория рекурсивно | `python -m src.cli.main index "docs/" --recursive --graph` |
| Полная переиндексация | `python -m src.cli.main index "doc.pdf" --full-reindex` |

### Все флаги индексации

| Флаг | Описание | Default |
|------|----------|---------|
| `--graph` | Извлечь сущности и связи для графа знаний | Выкл |
| `--communities` | Community detection (Leiden, требует `--graph`) | Выкл |
| `--parent-child` | Parent-child иерархия (parent=2000, child=400) | Выкл |
| `--raptor` | RAPTOR tree (иерархическая суммаризация) | Выкл |
| `--summarize` | Summary index | Выкл |
| `--layout-aware` | Layout-aware парсинг (Docling) | Вкл |
| `--extract-images` | Извлечь изображения + Vision OCR | Вкл |
| `--extract-tables` | Извлечь таблицы | Вкл |
| `--contextual` | Contextual Retrieval (контекст документа к каждому чанку) | Выкл |
| `--recursive` | Рекурсивная индексация директории | Выкл |
| `--full-reindex` | Полная переиндексация (удалить старые данные) | Выкл |
| `--tenant` | Tenant ID для multi-tenancy | `default` |

### Рекомендуемые комбинации

```bash
# Быстрая (1-3 мин на 200 стр) — текст + embeddings + BM25
python -m src.cli.main index "document.pdf"

# Стандартная (5-15 мин) — + граф знаний
python -m src.cli.main index "document.pdf" --graph

# Полная (30-60 мин) — все фичи
python -m src.cli.main index "document.pdf" \
    --graph --communities --parent-child --raptor --summarize --contextual

# Batch директория
python -m src.cli.main index "docs/" --recursive --graph
```

### Что даёт каждая опция

| Опция | Что создаёт | Зачем |
|-------|-------------|-------|
| `--graph` | Entities + Relations | Графовый поиск, GraphRAG |
| `--communities` | Кластеры сущностей + LLM-суммаризации | GraphRAG Local/Global search |
| `--parent-child` | Двухуровневые чанки (parent 2000 / child 400) | Точный поиск + полный контекст |
| `--raptor` | Иерархическое дерево суммаризаций | Высокоуровневые запросы |
| `--contextual` | Контекст документа в каждом чанке | +15-20% качество retrieval |
| `--extract-images` | Image → Vision OCR → текстовый чанк | Поиск по содержимому изображений |

### API

```bash
# Upload + index
curl -X POST http://localhost:8000/documents/upload \
    -F "file=@document.pdf" -F "graph=true"

# Streaming индексация (прогресс в реальном времени)
curl -X POST http://localhost:8000/documents/index/stream \
    -H "Content-Type: application/json" \
    -d '{"file_path": "document.pdf", "graph": true}'

# Удаление документа (каскадное, 9 слоёв)
curl -X DELETE http://localhost:8000/documents/{document_id}

# Пересборка BM25 индекса
curl -X POST http://localhost:8000/documents/rebuild-bm25
```

### Инкрементальная индексация (Delta — Phase 18)

SHA-256 change detection: при повторном вызове индексирует только изменённые/новые PDF.

```env
INDEXING__INCREMENTAL=true    # Delta updates (только изменённые)
```

```bash
# Delta — только изменённые файлы
python -m src.cli.main index "docs/" --recursive

# Принудительно переиндексировать всё
python -m src.cli.main index "docs/" --recursive --full-reindex

# API: delta индексация
curl -X POST http://localhost:8000/documents/index/delta \
    -d '{"directory": "data/pdfs"}'

# API: статистика delta
curl http://localhost:8000/documents/index/delta/stats

# API: очистка delta cache
curl -X POST http://localhost:8000/documents/index/delta/clear
```

**Как работает Delta:**
1. Вычисляет SHA-256 для всех PDF в директории
2. Сравнивает с хешами в SQLite (`data/document_hashes.db`)
3. Категории: `added` (новый), `modified` (хеш изменился), `deleted` (файл удалён), `unchanged`
4. Индексирует только added + modified, удаляет deleted из vector store

### Visual Indexing (ColPali — Phase 55)

Индексация визуального содержимого страниц PDF через ColPali multi-vector embeddings.

```bash
# API: visual search по проиндексированным страницам
curl -X POST http://localhost:8000/search/visual \
    -d '{"query": "таблица сравнения типов данных", "k": 5}'
```

```env
VISUAL_SEARCH__ENABLED=false           # Включить visual indexing
VISUAL_SEARCH__MODEL=vidore/colpali-v1.3  # Модель ColPali
VISUAL_SEARCH__RENDER_DPI=150          # DPI рендеринга страниц
```

**Pipeline:** PDF → Render pages as images (PageRenderer) → ColPali embeddings → Qdrant named vectors

### Document Versioning (Phase 12.5)

Отслеживание версий документов с возможностью rollback.

| Метод | Описание |
|-------|----------|
| `check_status(file_path)` | `"new"` / `"unchanged"` / `"modified"` |
| `compute_delta(file_path, new_chunks)` | Diff: added, modified, removed, unchanged chunks |
| `create_version(doc_id, chunks, ...)` | Snapshot текущего состояния |
| `rollback(doc_id, version_id)` | Восстановить предыдущую версию |

**Resilient Indexing:** checkpoint-based — при сбое возобновляет с последнего batch, а не с начала.

### Граф знаний — статистика

```bash
curl http://localhost:8000/graph/stats
# → {"entities": 3166, "edges": 3528, "communities": 45}
```

---

## Internals — pipeline и отладка

## End-to-End Pipeline

```
PDF → LOAD (Hybrid Loader) → PROCESS (split+metadata) → EMBED (E5 1024d) → INDEX (Qdrant+BM25+Graph)
```

### 1. LOAD — Hybrid Loader (4 уровня)

| Level | Метод | Когда | Выход |
|-------|-------|-------|-------|
| L1 | PyMuPDF4LLM | Всегда (fast) | Text + page_offsets (1-based!) |
| L2 | fitz find_tables() | Парсинг таблиц | Markdown tables (dedup vs L1) |
| L3 | Docling TableFormer | Сложные таблицы | ML-detected tables |
| L4 | Claude Vision OCR | Сканы (<50 chars + images) | Full-page OCR via Vision API |

### 2. PROCESS — Splitting + Metadata

- **Splitter**: recursive, chunk_size=1000, overlap=200
- **Header propagation**: markdown headings → section_headers[], breadcrumb
- **Page assignment**: bisect на page_offsets
- **Dedup**: hash content, remove exact duplicates

### 3. INDEX — Storage

- **Qdrant**: dense (1024d) + BM25 sparse vectors
- **BM25 FTS5**: title (10x) + body (1x)
- **Deterministic IDs**: SHA-256[:16] от file_path (doc) и doc_id+idx+content (chunk)
- **Batch**: 256 chunks/batch, checkpoint after each
- **Resume**: detect checkpoint → skip completed batches

## Конфиг

```env
PDF__CHUNK_SIZE=1000
PDF__CHUNK_OVERLAP=200
PDF__SPLITTER=recursive          # recursive|semantic
PDF__LOADER=hybrid               # hybrid|pymupdf4llm|docling|smart
```

## Диагностика

| Симптом | Причина | Решение |
|---------|---------|---------|
| 0 страниц | Docling timeout на больших PDF | Использовать hybrid loader, увеличить timeout до 1800s |
| 50% потеря страниц | Level 4 Vision timeout | Проверить `vision_timeout`, использовать hybrid fallback |
| Дубли при переиндексации | Dedup не сработал | Вызвать `delete_by_source()` перед `index_chunks()` |
| BM25 schema error | Старая single-column FTS5 | `_migrate_fts_schema()` автоматически, или rebuild |
| page_number +1 ошибка | pymupdf4llm уже 1-based | НЕ добавлять +1 к metadata["page"] |

## Связанные скиллы

- `framework-config` — .env параметры индексации
- `framework-cli` — все CLI команды index
- `graph-operations` — детали работы с графом
- `framework-troubleshooting` — ошибки индексации

## Файлы
- Loaders: [providers/](src/pdf_framework/loaders/providers/) (hybrid, pymupdf4llm, docling)
- Pipeline: [pipeline.py](src/pdf_framework/processing/pipeline.py)
- Splitters: [splitters/](src/pdf_framework/processing/splitters/)
- Indexer: [indexer.py](src/pdf_framework/indexing/indexer.py)
- Delta Indexer: [delta_indexer.py](src/pdf_framework/indexing/delta_indexer.py)
- Visual Indexer: [visual_indexer.py](src/pdf_framework/indexing/visual_indexer.py)
- Versioning: [versioning.py](src/pdf_framework/processing/versioning.py)
- Page Renderer: [page_renderer.py](src/pdf_framework/processing/page_renderer.py)
- ID generator: [id_generator.py](src/pdf_framework/utils/id_generator.py)
- Images: [image_extractor.py](src/pdf_framework/processing/image_extractor.py)
