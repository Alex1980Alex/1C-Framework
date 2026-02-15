# Indexing Pipeline

## Когда использовать
- "как проиндексировать", "ошибка индексации", "потерялись страницы"
- "loader", "splitter", "page_offsets", "batch indexing"
- Работа с новыми PDF, переиндексация, отладка pipeline

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

## Файлы
- Loaders: `src/pdf_framework/loaders/providers/` (hybrid, pymupdf4llm, docling)
- Pipeline: `src/pdf_framework/processing/pipeline.py`
- Splitters: `src/pdf_framework/processing/splitters/`
- Indexer: `src/pdf_framework/indexing/indexer.py`
- ID generator: `src/pdf_framework/utils/id_generator.py`
- Images: `src/pdf_framework/processing/image_extractor.py`
