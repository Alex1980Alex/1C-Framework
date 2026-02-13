# Phase 18: Incremental Indexing & Delta Updates

**Приоритет:** ВЫСОКИЙ | **Квартал:** Q2 2026 | **Версия:** v0.9.0
**Источники:** Pathway, LightRAG, Cognita
**Статус: РЕАЛИЗОВАНО**

---

## Проблема

Добавление 1 PDF требует полной переиндексации: загрузка → парсинг → чанкинг → эмбеддинг → ChromaDB + BM25 + Graph.
При 54 PDF это занимает 50+ минут. Изменение одного документа вызывает пересчёт всего.

## Текущее состояние

### Что уже есть
- **Document Processing Cache** (`src/pdf_framework/processing/cache.py`): SHA-256 hash файла → pickle с чанками
- **Dedup по source_path** (`src/api/routes/documents.py:22-65`): `_remove_existing_document()` удаляет старые чанки перед переиндексацией
- **BM25 dedup** (`bm25_store.delete_by_source()`): очистка FTS5 индекса
- **Semantic cache invalidation** (`semantic_cache.invalidate_by_document()`): Phase 17

### Чего не хватает
- Нет delta detection (определение изменённых секций внутри PDF)
- Нет chunk-level versioning (версионирование чанков)
- Нет file watcher (автоматическое обнаружение изменений)
- Нет инкрементального обновления графа

---

## Архитектура решения

```
data/pdfs/document.pdf
  ↓ SHA-256 hash
DocumentVersionManager.check(file_path)
  ├─ hash == stored_hash → SKIP (не изменился)
  ├─ hash != stored_hash → DELTA UPDATE
  │   ├─ Загрузить и распарсить новую версию
  │   ├─ Сравнить чанки: added / modified / deleted
  │   ├─ Удалить removed chunks из vector + BM25 + graph
  │   ├─ Добавить new chunks (embed + index)
  │   └─ Обновить hash в версионном хранилище
  └─ hash not found → FULL INDEX (новый документ)

FileWatcher (watchdog)
  ├─ Мониторинг data/pdfs/
  ├─ on_created → FULL INDEX
  ├─ on_modified → DELTA UPDATE
  └─ on_deleted → REMOVE ALL CHUNKS
```

---

## Пошаговый план

### 18.1. Document Version Manager

**Новый файл:** `src/pdf_framework/processing/versioning.py`

```python
class DocumentVersion(BaseModel):
    file_path: str
    file_hash: str           # SHA-256 содержимого файла
    chunk_hashes: dict[str, str]  # chunk_id → SHA-256(content)
    indexed_at: datetime
    chunks_count: int
    document_id: str

class DocumentVersionManager:
    """Track document versions for incremental indexing."""

    def __init__(self, db_path: Path = "data/cache/versions.db"):
        ...

    async def check_status(self, file_path: str) -> Literal["new", "unchanged", "modified"]:
        """Compare current file hash with stored version."""

    async def get_version(self, file_path: str) -> DocumentVersion | None:
        """Get stored version info for a document."""

    async def save_version(self, file_path: str, document_id: str,
                          chunks: list[DocumentChunk]) -> None:
        """Store version after successful indexing."""

    async def remove_version(self, file_path: str) -> None:
        """Remove version tracking for deleted document."""
```

**SQLite schema:**
```sql
CREATE TABLE document_versions (
    file_path TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL,
    document_id TEXT NOT NULL,
    chunks_json TEXT NOT NULL,      -- JSON: {chunk_id: content_hash}
    chunks_count INTEGER NOT NULL,
    indexed_at REAL NOT NULL
);
```

### 18.2. Delta Detection

**Модификация:** `src/pdf_framework/processing/versioning.py`

```python
class ChunkDelta(BaseModel):
    added: list[DocumentChunk]       # Новые чанки
    modified: list[DocumentChunk]    # Изменённые чанки (content hash изменился)
    removed: list[str]               # chunk_ids для удаления
    unchanged: int                   # Количество неизменённых

class DocumentVersionManager:
    async def compute_delta(
        self,
        file_path: str,
        new_chunks: list[DocumentChunk],
    ) -> ChunkDelta:
        """Compare new chunks with stored version, return delta."""
        old_version = await self.get_version(file_path)
        if old_version is None:
            return ChunkDelta(added=new_chunks, modified=[], removed=[], unchanged=0)

        old_hashes = old_version.chunk_hashes  # {chunk_id: hash}
        new_hashes = {c.id: hashlib.sha256(c.content.encode()).hexdigest()[:16]
                      for c in new_chunks}

        added = [c for c in new_chunks if c.id not in old_hashes]
        modified = [c for c in new_chunks
                    if c.id in old_hashes and new_hashes[c.id] != old_hashes[c.id]]
        removed = [cid for cid in old_hashes if cid not in new_hashes]
        unchanged = len(new_hashes) - len(added) - len(modified)

        return ChunkDelta(added=added, modified=modified,
                         removed=removed, unchanged=unchanged)
```

### 18.3. Incremental Indexer

**Модификация:** `src/pdf_framework/vector_store/indexing/indexer.py`

```python
class DocumentIndexer:
    async def index_incremental(
        self,
        chunks: list[DocumentChunk],
        delta: ChunkDelta,
        document_id: str,
        source_path: str,
    ) -> IndexResult:
        """Index only changed chunks (delta update)."""

        # 1. Удалить removed + modified chunks
        to_delete = delta.removed + [c.id for c in delta.modified]
        if to_delete:
            await self._vector_store.delete(to_delete)
            if self._bm25_store:
                await self._bm25_store.delete_chunks(to_delete)

        # 2. Добавить added + modified (новая версия)
        to_index = delta.added + delta.modified
        if to_index:
            return await self.index_chunks(to_index, document_id, source_path)

        return IndexResult(document_id=document_id, source_path=source_path,
                          chunks_stored=0, embeddings_computed=0)
```

### 18.4. File Watcher

**Новый файл:** `src/pdf_framework/processing/watcher.py`

```python
class PDFFileWatcher:
    """Watch data/pdfs/ directory for changes and trigger re-indexing."""

    def __init__(self, watch_dir: Path, indexing_callback: Callable):
        self._watch_dir = watch_dir
        self._callback = indexing_callback
        self._debounce_seconds = 5.0  # Задержка перед индексацией

    async def start(self) -> None:
        """Start watching in background asyncio task."""

    async def stop(self) -> None:
        """Stop watching."""

    async def _on_file_event(self, event_type: str, file_path: Path) -> None:
        """Handle file system event."""
        if not file_path.suffix.lower() == ".pdf":
            return
        if event_type == "created":
            await self._callback("index", file_path)
        elif event_type == "modified":
            await self._callback("reindex", file_path)
        elif event_type == "deleted":
            await self._callback("remove", file_path)
```

**Зависимость:** `watchdog` (Python library) или `watchfiles` (async-native).

### 18.5. API эндпоинт для инкрементальной индексации

**Модификация:** `src/api/routes/documents.py`

```python
@router.post("/index/incremental")
async def index_incremental(request: IndexRequest, components=Depends(get_components)):
    """Index a document incrementally (only changed chunks)."""
    version_mgr = components.version_manager
    status = await version_mgr.check_status(request.file_path)

    if status == "unchanged":
        return {"status": "skipped", "reason": "document unchanged"}

    # Загрузить и обработать
    document = await components.loader.load(request.file_path)
    processed = components.pipeline.process(document)
    chunks = processed.chunks

    if status == "modified":
        delta = await version_mgr.compute_delta(request.file_path, chunks)
        result = await components.indexer.index_incremental(
            chunks=chunks, delta=delta, ...)
    else:  # "new"
        result = await components.indexer.index_chunks(chunks, ...)

    await version_mgr.save_version(request.file_path, result.document_id, chunks)
    return {"status": status, "result": result}
```

### 18.6. CLI команда batch reindex

**Модификация:** `src/cli/main.py`

```bash
pdf-framework reindex --incremental --dir data/pdfs/
# Для каждого PDF:
#   unchanged → skip
#   modified → delta update
#   new → full index
#   missing → remove from stores
```

---

## Модифицируемые файлы

| Файл | Изменение |
|------|-----------|
| `src/pdf_framework/processing/versioning.py` | **NEW**: DocumentVersionManager |
| `src/pdf_framework/processing/watcher.py` | **NEW**: PDFFileWatcher |
| `src/pdf_framework/vector_store/indexing/indexer.py` | **MODIFY**: +`index_incremental()` |
| `src/pdf_framework/search/bm25_store.py` | **MODIFY**: +`delete_chunks(ids)` |
| `src/api/routes/documents.py` | **MODIFY**: +`/index/incremental` endpoint |
| `src/api/dependencies/components.py` | **MODIFY**: +DocumentVersionManager DI |
| `src/pdf_framework/config.py` | **MODIFY**: +IncrementalSettings |
| `src/cli/main.py` | **MODIFY**: +`reindex --incremental` |
| `pyproject.toml` | **MODIFY**: +`watchfiles` dependency |

## Настройки

```python
class IncrementalSettings(BaseSettings):
    enabled: bool = True
    watch_dir: Path = PROJECT_ROOT / "data" / "pdfs"
    auto_watch: bool = False           # Автозапуск file watcher
    debounce_seconds: float = 5.0      # Задержка перед индексацией
    version_db_path: Path = PROJECT_ROOT / "data" / "cache" / "versions.db"
```

## Верификация

1. Проиндексировать PDF → записать version
2. Изменить PDF → `check_status()` = "modified"
3. `compute_delta()` → показывает added/modified/removed
4. `index_incremental()` → обновляет только дельту
5. Неизменённый PDF → `check_status()` = "unchanged" → skip
6. `reindex --incremental` → пакетная обработка всех PDF
7. File watcher → автоматическая переиндексация при изменении
