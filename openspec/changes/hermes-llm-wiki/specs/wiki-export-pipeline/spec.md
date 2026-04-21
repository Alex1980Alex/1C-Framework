# Spec: wiki-export-pipeline

**Change:** hermes-llm-wiki
**Phase:** 4
**Profile:** python-framework

## Контекст

Phase 38 LightRAG ([`src/pdf_framework/graph_store/entity_embeddings.py`](../../../../src/pdf_framework/graph_store/entity_embeddings.py), 556 LoC) реализован и находится в production. Класс `EntityEmbeddingBuilder` обеспечивает интеграцию с Qdrant для entity/relation embeddings, а `LightRAGStrategy` ([`src/pdf_framework/search/strategies/graphrag_light.py`](../../../../src/pdf_framework/search/strategies/graphrag_light.py)) предоставляет search strategy поверх graph store. Инфраструктура DI в [`src/api/dependencies/components.py`](../../../../src/api/dependencies/components.py) уже регистрирует Phase 38 компоненты.

Phase 6.5 Incremental Graph Updates реализован: `IncrementalGraphUpdater` ([`src/pdf_framework/graph_store/incremental.py`](../../../../src/pdf_framework/graph_store/incremental.py), 293 LoC) с 80-95% экономией. `GraphChangeDetector` ([`src/pdf_framework/graph_store/change_detector.py`](../../../../src/pdf_framework/graph_store/change_detector.py), 254 LoC) обеспечивает diff графов. `community.py` и `summarizer.py` отвечают за community detection и summaries.

Phase 0 предоставляет `MemoryCube.to_wiki_page()` для сериализации в markdown с frontmatter, `UnifiedSearchEngine` с адаптерами `WikiSearchAdapter` / `GraphSearchAdapter`, link types `LinkType.MIRRORS` (L3 wiki ↔ L4 embedding) и `LinkType.GRAPH_NODE` (L3 wiki ↔ LightRAG entity). Hybrid search доступен через `HybridSearchService` ([`src/memory/orchestrator/search/hybrid_search.py`](../../../../src/memory/orchestrator/search/hybrid_search.py), 12KB) с BM25 + RRF fusion.

**Ключевой принцип:** LightRAG не внедряется заново — реализуется read-only доступ к `GraphStore` для генерации wiki-страниц, incremental sync через events Phase 6.5, и reverse sync для round-trip обновлений. Новый код — только integration glue (~500-800 LoC), не базовый engine.

---

## ## ADDED REQ-1: WikiExporter компонент

**Файл:** `src/pdf_framework/indexing/wiki_exporter.py` (новый)

Основной компонент для экспорта graph entities в wiki-страницы. Читает из `GraphStore` (Phase 38), генерирует markdown через `MemoryCube.to_wiki_page()` (Phase 0), сохраняет в `docs/wiki/entities/`.

### API

```python
# src/pdf_framework/indexing/wiki_exporter.py

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.pdf_framework.graph_store.entity_embeddings import EntityEmbeddingBuilder
from src.memory.orchestrator.memcube import MemoryCube, ContentType


@dataclass
class WikiExportConfig:
    output_dir: Path = field(default_factory=lambda: Path("docs/wiki/entities"))
    templates_dir: Path = field(default_factory=lambda: Path("docs/wiki/templates"))
    batch_size: int = 50
    overwrite_existing: bool = False
    include_relations: bool = True
    include_communities: bool = True
    dry_run: bool = False


@dataclass
class ExportResult:
    total_entities: int
    exported_pages: int
    skipped_pages: int
    failed_pages: int
    errors: list[dict[str, str]] = field(default_factory=list)
    duration_seconds: float = 0.0


class WikiExporter:
    """Exports GraphStore entities to canonical markdown wiki pages.

    Reads entities from existing LightRAG GraphStore (Phase 38),
    generates wiki pages via MemoryCube.to_wiki_page(), maintains
    bidirectional links via LinkType.MIRRORS and LinkType.GRAPH_NODE.
    """

    def __init__(
        self,
        graph_store: EntityEmbeddingBuilder,
        config: WikiExportConfig | None = None,
    ) -> None: ...

    async def export_all(self) -> ExportResult:
        """Export all entities from GraphStore to wiki pages."""

    async def export_entity(self, entity_id: str) -> Optional[Path]:
        """Export single entity to wiki page. Raises WikiExportError on failure."""

    async def export_batch(self, entity_ids: list[str]) -> ExportResult:
        """Export batch with FIFO concurrency limit."""

    def _entity_to_cube(self, entity: dict) -> MemoryCube:
        """Build MemoryCube(content_type=WIKI) from GraphStore entity."""

    def _resolve_template(self, entity_type: str) -> Path:
        """entity.md | concept.md | procedure.md, fallback entity.md."""

    def _generate_wiki_links(self, relations: list[dict]) -> list[str]:
        """Generate [[entity-id|Display Name]] syntax."""


class WikiExportError(Exception):
    def __init__(self, entity_id: str, reason: str) -> None:
        self.entity_id = entity_id
        self.reason = reason
        super().__init__(f"Wiki export failed for {entity_id}: {reason}")
```

### Сценарий 1: Export all entities с wiki-links

**Given** GraphStore содержит 150 entities с relations
**And** `docs/wiki/entities/` существует и writable
**And** templates существуют в `docs/wiki/templates/`
**When** `await exporter.export_all()` вызывается
**Then** 150 markdown файлов создаётся в `docs/wiki/entities/`
**And** каждый файл имеет YAML frontmatter с `unified_id`, `content_type: wiki`, `source: graph_exporter`, `graph_node_id`
**And** каждый файл содержит `[[wiki-links]]` для related entities
**And** `ExportResult(total_entities=150, exported_pages=150, failed_pages=0)`

### Сценарий 2: Missing template fallback

**Given** entity с `type="custom_type"`
**And** `docs/wiki/templates/custom_type.md` **не существует**
**And** fallback `docs/wiki/templates/entity.md` существует
**When** `export_entity("custom-entity-1")` вызывается
**Then** wiki page создан через `entity.md` template
**And** frontmatter содержит `original_type: "custom_type"`

### Граничные условия

- Entity без relations → страница без секции Related Entities, не падает
- Entity с пустым description → `entity_id` используется как заголовок
- Concurrent `export_all()` calls → file lock через `asyncio.Lock`, второй ждёт или получает `ExportResult(failed=...)`
- Disk full → `WikiExportError(reason="disk_full")`, partial results в `ExportResult`
- GraphStore недоступен → `WikiExportError(reason="graph_store_unavailable")` на первом entity, остальные skipped

### Ссылки

- [`src/pdf_framework/graph_store/entity_embeddings.py`](../../../../src/pdf_framework/graph_store/entity_embeddings.py) — `EntityEmbeddingBuilder`
- [`src/memory/orchestrator/memcube.py`](../../../../src/memory/orchestrator/memcube.py) — `MemoryCube.to_wiki_page()` (Phase 0)
- [`src/memory/orchestrator/link_registry.py`](../../../../src/memory/orchestrator/link_registry.py) — `LinkType.GRAPH_NODE`, `LinkType.MIRRORS` (Phase 0)

---

## ## ADDED REQ-2: Forward sync (Graph → Wiki)

**Файл:** `src/pdf_framework/indexing/wiki_exporter.py` (часть REQ-1)

Компонент `ForwardSyncService` читает entities из `GraphStore` через `EntityEmbeddingBuilder`, transforms в `EntityPage`, пишет через `WikiExporter`.

### API

```python
@dataclass
class EntityPage:
    entity_id: str
    entity_type: str
    title: str
    content: str
    frontmatter: dict[str, Any]
    relations: list[dict[str, str]]
    communities: list[str]
    source_graph: str = "lightrag_v38"
    generated_at: datetime = field(default_factory=datetime.utcnow)


class ForwardSyncService:
    def __init__(
        self,
        graph_store: EntityEmbeddingBuilder,
        exporter: WikiExporter,
    ) -> None: ...

    async def sync_entity(self, entity_id: str) -> Optional[Path]:
        """Steps:
        1. graph_store.get_entity(entity_id)
        2. graph_store.get_relations(entity_id)
        3. CommunityDetector.find_for(entity_id) из community.py
        4. Build EntityPage → _build_frontmatter + _format_page_content
        5. exporter.export_entity(entity_id)
        """

    async def sync_since(self, since: datetime) -> ExportResult:
        """Catch-up sync для entities с updated_at > since."""

    def _build_frontmatter(self, entity: dict, relations: list[dict]) -> dict:
        """Обязательные поля: entity_id, entity_type, source_graph,
        generated_at, relation_count, community_ids, graph_node_link,
        mirrors_link (через LinkType.MIRRORS/GRAPH_NODE).
        """

    def _format_page_content(
        self, entity: dict, relations: list[dict], communities: list[str]
    ) -> str:
        """Секции: Description / Properties / Related Entities (с
        [[wiki-links]]) / Communities.
        """
```

### Сценарий 1: Frontmatter корректно сформирован

**Given** entity `"python-asyncio"` с type `"concept"`, 3 outgoing relations, community `"async-programming"`
**When** `sync_entity("python-asyncio")` вызывается
**Then** создаётся `docs/wiki/entities/python-asyncio.md`
**And** frontmatter содержит `entity_id: python-asyncio`, `source_graph: lightrag_v38`, `relation_count: 3`, `community_ids: ["async-programming"]`
**And** content содержит секцию `## Related Entities`
**And** content содержит `[[event-loop|Event Loop]]` wiki-link

### Сценарий 2: sync_since для catch-up

**Given** 5 entities updated после `2026-04-10T10:00:00Z`, 3 entities — раньше
**When** `sync_since(datetime(2026, 4, 10, 10, 0, 0))` вызывается
**Then** exactly 5 wiki-страниц регенерируются
**And** `ExportResult.exported_pages == 5`

### Граничные условия

- Entity удалён из GraphStore → `sync_entity` возвращает `None`, log warning
- Circular relations (A → B → A) → wiki-links создаются, no infinite loop
- Entity с 1000+ relations → пагинация в Related Entities, ≤50 на секцию, остальное в `related_overflow` frontmatter field
- Concurrent `sync_entity` для одного id → file lock, FIFO

### Ссылки

- [`src/pdf_framework/graph_store/community.py`](../../../../src/pdf_framework/graph_store/community.py) — `CommunityDetector`
- [`src/pdf_framework/graph_store/summarizer.py`](../../../../src/pdf_framework/graph_store/summarizer.py) — community summaries

---

## ## ADDED REQ-3: Incremental sync через IncrementalGraphUpdater events

**Файл:** `src/pdf_framework/indexing/wiki_exporter.py` (часть)

Подписка на события от `IncrementalGraphUpdater` (Phase 6.5) — реэкспортируются **только affected entities**, 80-95% экономия CPU.

### API

```python
from enum import Enum
from typing import Awaitable, Callable

class GraphEventType(str, Enum):
    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    ENTITY_DELETED = "entity_deleted"
    RELATION_ADDED = "relation_added"
    RELATION_REMOVED = "relation_removed"
    COMMUNITY_MERGED = "community_merged"


@dataclass
class GraphChangeEvent:
    event_type: GraphEventType
    entity_id: str
    timestamp: datetime
    affected_entity_ids: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


class IncrementalWikiSync:
    def __init__(
        self,
        graph_updater: "IncrementalGraphUpdater",
        forward_sync: ForwardSyncService,
        max_retries: int = 3,
        retry_delay_s: float = 1.0,
    ) -> None: ...

    async def start(self) -> None:
        """Subscribe на events от IncrementalGraphUpdater."""

    async def stop(self) -> None: ...

    async def _handle_entity_change(self, event: GraphChangeEvent) -> None:
        """Created/Updated → forward_sync.sync_entity().
        Deleted → remove wiki page file + create LinkType.SUPERSEDED_BY link.
        """

    async def _handle_relation_change(self, event: GraphChangeEvent) -> None:
        """Sync both source + target entities (их Related Entities секции изменились)."""

    async def _handle_community_change(self, event: GraphChangeEvent) -> None:
        """Sync all entities в merged communities."""

    def _should_sync(self, event: GraphChangeEvent) -> bool:
        """Фильтр для noisy events (embedding-only updates)."""
```

### Сценарий 1: Entity update triggers incremental sync

**Given** `IncrementalWikiSync` started и listening
**And** entity `"fastapi"` существует в GraphStore и wiki
**When** `IncrementalGraphUpdater` emits `ENTITY_UPDATED` для `"fastapi"`
**Then** `IncrementalWikiSync` получает event
**And** `forward_sync.sync_entity("fastapi")` вызывается
**And** `docs/wiki/entities/fastapi.md` регенерируется
**And** **другие wiki-страницы не меняются** (80-95% экономия vs full export)

### Сценарий 2: Relation change syncs both endpoints

**Given** entities `"python"` и `"fastapi"` существуют
**And** relation `fastapi --uses--> python` добавлен
**When** `IncrementalGraphUpdater` emits `RELATION_ADDED`
**Then** `event.affected_entity_ids == ["fastapi", "python"]`
**And** `sync_entity("fastapi")` вызван
**And** `sync_entity("python")` вызван
**And** оба wiki-файла регенерируются

### Сценарий 3: Entity deletion removes wiki page

**Given** entity `"deprecated-lib"` существует в GraphStore и wiki
**When** `IncrementalGraphUpdater` emits `ENTITY_DELETED`
**Then** файл `docs/wiki/entities/deprecated-lib.md` удаляется
**And** other wiki pages со ссылками показывают broken-link marker (auto-librarian Фаза 3 отследит)

### Граничные условия

- Event storm (1000 events/s) → batch processing с debounce 5s
- Event для несуществующего entity → warning log, no crash
- Retry exhaustion (>3) → dead letter queue в `docs/wiki/_failed_events.jsonl`
- Late start (после пропущенных events) → catch-up через `sync_since()`

### Ссылки

- [`src/pdf_framework/graph_store/incremental.py`](../../../../src/pdf_framework/graph_store/incremental.py) — `IncrementalGraphUpdater`
- [`src/memory/infrastructure/event_bus.py`](../../../../src/memory/infrastructure/event_bus.py) — можно использовать вместо graph_updater direct subscribe

---

## ## ADDED REQ-4: Reverse sync (Wiki → Graph)

**Файл:** `src/pdf_framework/indexing/wiki_exporter.py` (часть)

`ReverseSyncService` watches `docs/wiki/entities/` через `watchdog`, при изменениях обновляет GraphStore через existing `GraphChangeDetector` (Phase 6.5).

### API

```python
from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer


@dataclass
class WikiPageChange:
    entity_id: str
    page_path: Path
    change_type: str  # "created" | "modified" | "deleted"
    frontmatter: dict[str, Any]
    content_diff: Optional[str] = None
    added_links: list[str] = field(default_factory=list)
    removed_links: list[str] = field(default_factory=list)


class ReverseSyncService:
    def __init__(
        self,
        graph_store: EntityEmbeddingBuilder,
        change_detector: "GraphChangeDetector",
        wiki_dir: Path = Path("docs/wiki/entities"),
        debounce_s: float = 2.0,
    ) -> None: ...

    async def start_watching(self) -> None:
        """Запуск watchdog Observer на wiki_dir."""

    async def stop_watching(self) -> None: ...

    async def handle_page_change(self, change: WikiPageChange) -> None:
        """Steps:
        1. Parse frontmatter и content
        2. Extract [[wiki-links]] как relations
        3. GraphChangeDetector.compute_diff(old, new)
        4. Apply changes в GraphStore
        5. Publish event 'wiki.graph.synced' через EventBus
        """

    def _parse_wiki_page(self, path: Path) -> WikiPageChange:
        """Parse markdown → WikiPageChange. Raises WikiParseError."""

    def _links_to_relations(
        self, links: list[str], source_entity_id: str
    ) -> list[dict[str, str]]:
        """[[target-id|Display]] → {source, target, type: 'related_to'}."""


class ReverseSyncError(Exception): ...
class WikiParseError(Exception): ...
```

### Сценарий 1: Wiki edit adds new relation

**Given** `docs/wiki/entities/fastapi.md` существует с `[[python|Python]]`
**When** пользователь редактирует и добавляет `[[starlette|Starlette]]`
**Then** `ReverseSyncService` детектит file modification (через watchdog)
**And** `_parse_wiki_page` возвращает `WikiPageChange(added_links=["starlette"])`
**And** `GraphChangeDetector.compute_diff` возвращает добавленную relation
**And** GraphStore получает `fastapi --related_to--> starlette`

### Сценарий 2: Malformed frontmatter

**Given** `docs/wiki/entities/broken.md` с невалидным YAML frontmatter
**When** file modification детектится
**And** `_parse_wiki_page` вызывается
**Then** `WikiParseError(line=N)` raised
**And** error logged, watcher продолжает
**And** GraphStore **НЕ модифицируется**

### Граничные условия

- Rapid saves (editor auto-save) → debounce 2s, обрабатывается финальная версия
- Broken wiki-link `[[nonexistent]]` → создаёт relation, log warning, auto-librarian Фаза 3 создаст задачу
- Circular edit (graph → wiki → graph) → `change_detector.compute_diff()` обнаруживает no-op, skip
- Permission denied при чтении → log error, watcher продолжает

### Ссылки

- [`src/pdf_framework/graph_store/change_detector.py`](../../../../src/pdf_framework/graph_store/change_detector.py) — `GraphChangeDetector`
- `watchdog` PyPI package — filesystem events

---

## ## MODIFIED REQ-5: LightRAGStrategy.search() возвращает wiki_page_path

**Файл:** [`src/pdf_framework/search/strategies/graphrag_light.py`](../../../../src/pdf_framework/search/strategies/graphrag_light.py)
**Было:** `LightRAGStrategy.search()` возвращает результаты только с graph data
**Стало:** результаты enriched с путём к wiki-странице, если файл существует

### Изменения

```python
# src/pdf_framework/search/strategies/graphrag_light.py (модификация)

from pathlib import Path


@dataclass
class LightRAGSearchResult:
    entity_id: str
    entity_type: str
    score: float
    content: str
    relations: list[dict[str, str]]
    # NEW:
    wiki_page_path: Path | None = None
    wiki_page_exists: bool = False


class LightRAGStrategy:
    def __init__(
        self,
        graph_store: EntityEmbeddingBuilder,
        wiki_entities_dir: Path = Path("docs/wiki/entities"),  # NEW
    ) -> None:
        # ... existing init ...
        self._wiki_dir = wiki_entities_dir

    async def search(
        self, query: str, top_k: int = 10, filters: dict | None = None
    ) -> list[LightRAGSearchResult]:
        # ... existing search logic unchanged ...
        results = await self._execute_search(query, top_k, filters)

        # NEW: Enrich с wiki paths
        for result in results:
            wiki_path = self._wiki_dir / f"{result.entity_id}.md"
            result.wiki_page_exists = wiki_path.exists()
            result.wiki_page_path = wiki_path if result.wiki_page_exists else None

        return results
```

### Сценарий 1: Search returns wiki path для exported entity

**Given** entity `"python-asyncio"` в GraphStore
**And** `docs/wiki/entities/python-asyncio.md` существует
**When** `search("async programming")` вызывается
**And** `"python-asyncio"` в результатах
**Then** `result.wiki_page_path == Path("docs/wiki/entities/python-asyncio.md")`
**And** `result.wiki_page_exists == True`

### Сценарий 2: None для non-exported entity

**Given** entity `"new-concept"` в GraphStore
**And** `docs/wiki/entities/new-concept.md` **не существует**
**When** `search("new concept")` вызывается
**Then** `result.wiki_page_path is None`
**And** `result.wiki_page_exists is False`

### Граничные условия

- `wiki_entities_dir` не существует → `wiki_page_path` всегда `None`, не crash
- 1000 результатов → `exists()` check O(1), не блокирует
- Обратная совместимость: код без `wiki_page_path` продолжает работать

### Ссылки

- [`src/pdf_framework/search/strategies/graphrag_light.py`](../../../../src/pdf_framework/search/strategies/graphrag_light.py)

---

## ## ADDED REQ-6: Wiki индексация через HybridSearchService

**Файл:** `src/pdf_framework/indexing/wiki_exporter.py` (часть)

Wiki-страницы индексируются через **существующий** [`HybridSearchService`](../../../../src/memory/orchestrator/search/hybrid_search.py) из `src/memory/orchestrator/search/`. **НЕ** писать свой BM25.

### API

```python
from src.memory.orchestrator.search.hybrid_search import HybridSearchService


class WikiSearchIndexer:
    """Indexes wiki pages through existing HybridSearchService.

    Reuses BM25Index + RRF fusion from orchestrator/search/hybrid_search.py.
    No separate BM25 for wiki.
    """

    def __init__(
        self,
        hybrid_search: HybridSearchService,
        wiki_dir: Path = Path("docs/wiki/entities"),
    ) -> None: ...

    async def index_page(self, page_path: Path) -> None:
        """Extract text (excluding frontmatter), index через hybrid_search."""

    async def index_all_pages(self) -> int:
        """Индексировать все wiki pages. Returns count."""

    async def remove_page(self, entity_id: str) -> None:
        """Remove doc_id=entity_id из hybrid_search index."""

    def _extract_searchable_text(self, page_path: Path) -> str:
        """Strip YAML frontmatter, resolve [[wiki-links]] to display text."""
```

### Сценарий 1: Wiki page searchable via HybridSearchService

**Given** `docs/wiki/entities/fastapi.md` с контентом о web framework
**And** `WikiSearchIndexer.index_page()` был вызван
**When** `hybrid_search.search("web framework python")` вызывается
**Then** результаты содержат doc с `entity_id == "fastapi"`
**And** RRF fusion объединяет BM25 + dense scores

### Сценарий 2: Deleted page removed from index

**Given** entity `"deprecated"` indexed в `HybridSearchService`
**When** `remove_page("deprecated")` вызывается
**Then** `hybrid_search.search("deprecated")` не возвращает wiki результат

### Граничные условия

- Page с пустым content (после strip frontmatter) → не индексируется, log warning
- Duplicate `index_page()` → upsert semantics (обновляет doc)
- `HybridSearchService` недоступен → методы возвращают error, не crash

### Ссылки

- [`src/memory/orchestrator/search/hybrid_search.py`](../../../../src/memory/orchestrator/search/hybrid_search.py) — `HybridSearchService`, `BM25Index`
- [`src/memory/orchestrator/search/bsl_scorer.py`](../../../../src/memory/orchestrator/search/bsl_scorer.py) — для справки (BSL-aware tokenization)

---

## ## ADDED REQ-7: CLI script и eval regression gate

**Файлы:** `scripts/export_graph_to_wiki.py` (новый), `tests/regression/test_wiki_export_regression.py` (новый)

CLI утилита для запуска pipeline и regression-gate, блокирующий merge если quality metrics ухудшились.

### CLI API

```python
# scripts/export_graph_to_wiki.py

import argparse
import asyncio
import sys


def parse_args() -> argparse.Namespace:
    """Commands:
      export-all         Export all entities to wiki
      export-entity ID   Export single entity
      sync-incremental   Start incremental sync daemon (long-running)
      index-search       Index wiki pages in HybridSearchService
      verify             Verify wiki pages match graph state

    Options:
      --output-dir PATH
      --batch-size N (default: 50)
      --dry-run
      --verbose
    """


async def cmd_export_all(args) -> int:
    """Exit codes: 0 success, 1 partial failure, 2 total failure."""


async def cmd_verify(args) -> int:
    """Checks:
      1. Every entity in GraphStore → has wiki page
      2. Every wiki page → has entity in GraphStore
      3. frontmatter matches entity metadata
      4. wiki-links match entity relations

    Returns: 0 consistent, 1 inconsistencies found.
    """


def main() -> int:
    args = parse_args()
    return asyncio.run(cmd_dispatch(args))


if __name__ == "__main__":
    sys.exit(main())
```

### Eval regression gate

```python
# tests/regression/test_wiki_export_regression.py

import pytest
from pathlib import Path

# Baseline metrics (before Phase 4):
BASELINE_CHUNK_RAG_PRECISION = 0.72  # from existing eval
BASELINE_GRAPHRAG_PRECISION = 0.81   # from existing eval

REGRESSION_TOLERANCE = 0.05  # 5% drop = fail


@pytest.mark.regression
async def test_wiki_export_precision_no_regression(eval_dataset):
    """Post-export GraphRAG precision must be >= baseline - tolerance."""
    # Run existing GraphRAG eval suite after Phase 4 implementation
    post_export = await run_graphrag_eval(eval_dataset)

    assert post_export["precision"] >= BASELINE_GRAPHRAG_PRECISION - REGRESSION_TOLERANCE, (
        f"Regression detected: {post_export['precision']:.3f} vs baseline {BASELINE_GRAPHRAG_PRECISION:.3f}"
    )


@pytest.mark.regression
async def test_wiki_search_precision_improves_over_chunk(eval_dataset):
    """Target: wiki-enhanced retrieval >= baseline chunk RAG + 10%."""
    wiki_metrics = await run_wiki_hybrid_eval(eval_dataset)

    improvement = wiki_metrics["precision"] - BASELINE_CHUNK_RAG_PRECISION
    assert improvement >= 0.10, f"Improvement {improvement:.3f} < target 0.10"
```

### Сценарий 1: Regression gate блокирует ухудшение

**Given** existing GraphRAG baseline precision = 0.81 на 10 тестовых PDF
**When** Phase 4 реализация завершена, запускается `pytest tests/regression/`
**And** post-export precision = 0.74
**Then** `test_wiki_export_precision_no_regression` fails (0.74 < 0.81 - 0.05 = 0.76)
**And** CI блокирует merge

### Сценарий 2: Improvement target met

**Given** baseline chunk RAG precision = 0.72
**When** wiki-enhanced pipeline eval запускается
**And** post-export precision = 0.83 (+0.11)
**Then** `test_wiki_search_precision_improves_over_chunk` passes
**And** regression gate зелёный

### Граничные условия

- Eval dataset отсутствует → skip с warning, не fail (allows early merge)
- Precision baseline не установлен → initial run записывает baseline, skip regression check
- Non-deterministic LLM results → 3-run average для stability
- CI timeout (>30 min на full eval) → parallelize или use sample dataset

### Ссылки

- [`tests/eval/`](../../../../tests/eval/) — existing eval infrastructure
- [`scripts/eval_bsl_search.py`](../../../../scripts/eval_bsl_search.py) — pattern reference

---

## Регрессия

Фаза 4 **НЕ ДОЛЖНА** ломать:

- [ ] Existing Phase 38 LightRAG tests — `tests/integration/test_graphrag.py` (если есть)
- [ ] Existing `LightRAGStrategy.search()` без `wiki_page_path` — обратная совместимость (default `None`)
- [ ] Existing `IncrementalGraphUpdater` behavior — только подписка, не модификация
- [ ] Existing `EntityEmbeddingBuilder` API — read-only доступ
- [ ] Existing eval metrics на `data/eval/` — должны сохраниться или улучшиться (regression gate)
- [ ] Existing `HybridSearchService` для других use-cases (BSL code search) — не трогать конфиг

## Новые тесты

```
tests/unit/pdf_framework/indexing/
  __init__.py
  test_wiki_exporter.py              — WikiExporter unit tests (mock graph_store)
  test_forward_sync.py               — ForwardSyncService с моками
  test_incremental_wiki_sync.py      — IncrementalWikiSync event handling
  test_reverse_sync.py               — ReverseSyncService watchdog mocks
  test_wiki_search_indexer.py        — WikiSearchIndexer с mock HybridSearchService

tests/integration/
  test_wiki_export_e2e.py            — End-to-end: GraphStore → wiki files → search
  test_lightrag_wiki_path.py         — LightRAGStrategy.search() с wiki_page_path
  test_reverse_sync_roundtrip.py     — Edit wiki → graph update → re-export

tests/regression/
  test_wiki_export_regression.py     — eval gate: precision >= baseline
```

**Coverage target:** `wiki_exporter.py` ≥85%, CLI ≥80%, regression tests обязательны для merge.

**Go/no-go decision (из roadmap v1.3.4 Фазы 4):** если wiki export приводит к precision drop >5% или incremental sync не обеспечивает 80% savings → fallback на `nano-graphrag` inline (~1100 LoC).

---

## Incremental Requirements (Phase 3.10)

### EventBus Integration

`IncrementalGraphUpdater` publishes events to `EventBus` after each `update()` call:

| Event Type | Trigger | Payload |
|------------|---------|---------|
| `graph.entity_created` | New entity added | `{entity_id, entity_name, entity_type}` |
| `graph.entity_updated` | Entity merged | `{entity_id, entity_name, entity_type}` |
| `graph.relation_added` | New relation added | `{source_id, target_id, affected_entity_ids}` |

Source: `src/pdf_framework/graph_store/incremental.py:IncrementalGraphUpdater._publish_update_events()`

### IncrementalWikiSync Subscription

`IncrementalWikiSync` subscribes to `graph.*` pattern via EventBus on `start()`:

- Subscribes in `start()`, unsubscribes in `stop()`
- Background `_listen_loop()` task reads events from subscription queue
- Converts EventBus `Event` → `GraphChangeEvent` → calls `handle_event()`
- Event bus: `src/memory/infrastructure/event_bus.py`

### Retry Backoff Policy

Exponential backoff with delays `[1s, 5s, 30s]`:

```python
_BACKOFF_DELAYS = [1.0, 5.0, 30.0]
```

Max retries: 3 (configurable). After exhaustion, event goes to DLQ.

### Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `wiki_sync_events_total` | counter | Total events processed |
| `wiki_sync_failures_total` | counter | Events that exhausted retries |
| `wiki_sync_dlq_size` | gauge | Current dead letter queue size |

Source: `src/memory/infrastructure/metrics.py:MetricsCollector`

### Tests

Integration tests in `tests/unit/pdf_framework/indexing/test_incremental_wiki_sync.py`:

- `test_single_entity_update_triggers_single_reexport` — 1 entity update → 1 wiki page
- `test_merged_entity_publishes_updated_event` — merge → `graph.entity_updated`
- `test_no_event_bus_means_no_publishing` — graceful no-op without bus
- `test_backoff_delays_exponential` — verify `[1.0, 5.0, 30.0]`
- `test_metrics_incremented_on_event` — counters update correctly
