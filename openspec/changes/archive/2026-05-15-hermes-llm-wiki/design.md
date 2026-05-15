# Design: Hermes Agent / LLM Wiki

## Архитектурная диаграмма: 5-слойная модель памяти

```
                        READ PATH (unified_search + memory-first-hook v3)
                                        ▲
┌───────────────────────────────────────┴────────────────────────────────────┐
│  L4: Индексы (derived, rebuildable)                                        │
│  ├─ Qdrant wiki_pages_v1      — embeddings wiki-страниц (NEW)              │
│  ├─ LightRAG entity graph     — уже существует (Phase 38)                  │
│  ├─ Qdrant learned_patterns   — уже существует                             │
│  ├─ Qdrant skill_library      — уже существует (75 skills)                 │
│  └─ Qdrant experience_bank    — уже существует                             │
│     ▲ auto-reindex on L3 write                                             │
├─────┴──────────────────────────────────────────────────────────────────────┤
│  L3: Wiki (canonical, version-controlled) ◄── NEW + миграция существующих  │
│  ├─ docs/wiki/                — NEW (entity/concept/procedure/patterns)    │
│  ├─ docs/architecture/        — миграция: добавить frontmatter + links     │
│  ├─ docs/roadmap/             — уже существует, добавить frontmatter       │
│  ├─ .claude/skills/*/cache/   — уже существует как прото-wiki              │
│  └─ docs/wiki/SCHEMA.md       — NEW правила ведения                        │
│     ▲ промоция: wiki_promoter (L2→L3)                                      │
├─────┴──────────────────────────────────────────────────────────────────────┤
│  L2: Semantic patterns (confidence-weighted)                               │
│  └─ Qdrant learned_patterns + skill_learning JSONL — существует            │
│     ▲ capture: skill-learning MCP                                          │
├─────┴──────────────────────────────────────────────────────────────────────┤
│  L1: Episodic                                                              │
│  └─ SQLite memory_ai.db — существует (session-memory-save.py)              │
├────────────────────────────────────────────────────────────────────────────┤
│  L0: Raw (immutable, ephemeral-ok)                                         │
│  └─ conversation logs, PDFs, git history                                   │
└────────────────────────────────────────────────────────────────────────────┘
```

## Затронутые модули

### `src/memory/orchestrator/` — расширение существующего (не переписывание)

| Файл | Текущее состояние | Изменения | Новые классы/методы |
|------|-------------------|-----------|---------------------|
| `unified_id.py` | 240 LoC, `MemoryType` + `SourceServer` enum | Расширение enum | `MemoryType.WIKI`, `MemoryType.GRAPH`, `SourceServer.OBSIDIAN_VAULT`, `SourceServer.LIGHTRAG` |
| `link_registry.py` | 798 LoC, SQLite backend, SQL CHECK constraint | **Требует миграцию БД**: `ALTER TABLE links` расширение CHECK | `LinkType.PROMOTED_TO`, `SUPERSEDED_BY`, `MIRRORS`, `GRAPH_NODE` |
| `memcube.py` | 229 LoC, `MemoryCube.to_ai_memory_row/to_vector_memory_payload/to_skill_learning_record` | Добавить методы | `MemoryCube.to_wiki_page() -> str`, `from_wiki_page(md: str) -> MemoryCube`, `ContentType.WIKI` |
| `unified_search.py` | 500 LoC, `UnifiedSearchEngine` + `BaseSearchAdapter(ABC)` + `register_adapter()` | Создать адаптеры | `adapters/wiki_adapter.py` (`WikiSearchAdapter(BaseSearchAdapter)`), `adapters/graph_adapter.py` (`GraphSearchAdapter(BaseSearchAdapter)`) |
| `memory_router.py` | 583 LoC, 3-фазная классификация | Расширить targets | `ContentClassifier._phase3_select_targets` добавляет target `"wiki"` |
| `memory_orchestrator.py` | 2400+ LoC, 33 MCP tools | Регистрация новых adapters + `_save_to_target` для wiki | (использует существующий `register_adapter()`) |

### `src/memory/librarian/` — **новый модуль** (minimal, ~100 LoC)

```python
# src/memory/librarian/__init__.py
# src/memory/librarian/wiki_promoter.py

class WikiPromoter:
    """Thin wrapper над существующими компонентами для L2→L3 промоции.

    Uses:
        - vector_memory client (read learned_patterns)
        - memory_orchestrator.unified_search (duplicate detection)
        - conflict_resolver (ConflictResolver from infrastructure)
        - link_registry (create promoted_to / superseded_by links)
        - memcube.MemoryCube.to_wiki_page() (markdown rendering)
        - event_bus (publish wiki.draft.created / wiki.promoted)
    """

    async def scan_and_promote(
        self,
        confidence_threshold: float = 0.8,
        usage_threshold: int = 5,
    ) -> PromotionResult:
        # 1. Query learned_patterns где confidence >= threshold AND usage_count >= threshold
        # 2. For each candidate: unified_search для дедупликации
        # 3. If cosine >= 0.85 with existing wiki → ConflictResolver.resolve()
        # 4. If new → MemoryCube.to_wiki_page() → Write в docs/wiki/drafts/<slug>.md
        # 5. create_link(pattern, wiki, type=PROMOTED_TO)
        # 6. event_bus.publish("wiki.promoted", ...)
```

### `src/pdf_framework/indexing/wiki_exporter.py` — **новый** (300-500 LoC)

Цель: экспортировать existing LightRAG entity graph в markdown wiki-страницы.

```python
class WikiExporter:
    """Export entity graph from graph_store to markdown wiki pages.

    Uses:
        - GraphStore (existing NetworkX/Neo4j)
        - ChangeDetector (existing Phase 6.5)
        - IncrementalGraphUpdater (existing Phase 6.5)
        - Summarizer (existing community summaries)
        - MemoryCube.to_wiki_page() (from Phase 0)
    """

    async def export_entity(self, entity_id: str) -> Path:
        # 1. Read entity from graph_store
        # 2. Read related entities via graph traversal
        # 3. Build MemoryCube(content_type=WIKI, payload={...})
        # 4. Write docs/wiki/entities/<entity-id>.md
        # 5. Add [[wiki-link]] to related entities
        # 6. Trigger reindex via docs-change-tracker

    async def incremental_sync(self) -> SyncResult:
        # Subscribe to IncrementalGraphUpdater events
        # Only re-export affected entities (80-95% CPU savings)
```

### `src/pdf_framework/agents/` — миграция на DSPy (NOT new files)

```python
# src/pdf_framework/prompts/signatures.py (NEW)
import dspy

class GraderSignature(dspy.Signature):
    """Grade document relevance to query."""
    query: str = dspy.InputField()
    document: str = dspy.InputField()
    relevance: Literal["relevant", "partial", "irrelevant"] = dspy.OutputField()

class HallucinationCheckSignature(dspy.Signature):
    """Check if answer is grounded in context."""
    answer: str = dspy.InputField()
    context: str = dspy.InputField()
    grounded: bool = dspy.OutputField()
    reasoning: str = dspy.OutputField()

class RewriterSignature(dspy.Signature):
    """Rewrite query using conversation history."""
    query: str = dspy.InputField()
    history: str = dspy.InputField()
    rewritten: str = dspy.OutputField()
```

Migration в `agents/{grader,rewriter,hallucination_check}.py` — заменить f-string на `dspy.Predict(Signature)` / `dspy.ChainOfThought(Signature)`.

### `.claude/hooks/` — расширения

| Hook | Текущий LoC | Изменения |
|------|-------------|-----------|
| `memory-first-hook.py` | 504 | Добавить Layer 0 (obsidian-mcp wiki search) + перераспределение RRF весов (L1=0.30, L2=0.35, L3=0.15, L4=0.20) |
| `docs-change-tracker.py` | 28KB | Расширить watcher на `docs/wiki/*.md` + kb-lint + wiki-links validation |
| `docs-change-enforcer.py` | 20KB | Добавить Stop-check для `docs/wiki/drafts/` pending review |

### `.mcp.json` — добавление сервера

```json
{
  "obsidian-mcp": {
    "command": "python",
    "args": ["-m", "mcp_obsidian"],
    "env": {
      "OBSIDIAN_API_KEY": "...",
      "OBSIDIAN_HOST": "127.0.0.1",
      "OBSIDIAN_PORT": "27123",
      "OBSIDIAN_VAULT_PATH": "D:/1С-Framework"
    }
  }
}
```

### `.obsidian/` — новый vault config (JSON файлы)

```
.obsidian/
  app.json              — base settings
  workspace.json        — layout (gitignored)
  community-plugins.json — empty (optional plugins)
  templates/            — wiki templates (entity, concept, procedure)
```

### `docs/wiki/` — новая директория

```
docs/wiki/
  _index.md             — wiki map
  SCHEMA.md             — правила ведения
  log.md                — хронология L2→L3 промоций
  entities/             — structured entity pages
  concepts/             — concept pages
  procedures/           — how-to guides
  patterns/             — architectural patterns (split from PATTERNS.md)
  drafts/               — auto-generated drafts (до human review)
```

## Существующие компоненты, которые переиспользуются

### Из `src/memory/infrastructure/` (68KB)

| Компонент | Файл | Как используется |
|-----------|------|------------------|
| `EventBus` | `event_bus.py` (10KB) | `publish("wiki.promoted", ...)` события для wiki промоций |
| `EventStore` | `event_store.py` (12KB) | Persistence + replay истории промоций |
| `ConflictResolver` | `conflict_resolver.py` (10KB) | Резолюция конфликтов wiki vs L2 pattern (стратегия SOURCE_PRIORITY) |
| `CircuitBreaker` | `circuit_breaker.py` | Resilience для Obsidian MCP calls |
| `Retry` | `retry.py` | Retry для флаки Qdrant operations |

### Из `src/memory/orchestrator/search/`

| Компонент | Файл | Как используется |
|-----------|------|------------------|
| `BM25Index` | `hybrid_search.py` (12KB) | Индексация wiki-страниц для BM25 поиска |
| `HybridSearchService` | `hybrid_search.py` | RRF fusion BM25 + dense для wiki_pages_v1 |

### Из `src/pdf_framework/graph_store/` (Phase 38 + 6.5)

| Компонент | Файл | Как используется |
|-----------|------|------------------|
| `EntityEmbeddingBuilder` | `entity_embeddings.py` (18KB) | Существующий entity/relation embeddings builder |
| `IncrementalGraphUpdater` | `incremental.py` (9KB) | Инкрементальное обновление (80-95% экономии) |
| `GraphChangeDetector` | `change_detector.py` (7KB) | Диффинг графа перед rewrite |
| `CommunitySummarizer` | `summarizer.py` | Community summaries для wiki pages |

### Из `src/api/auth/` и `src/bsl/mcp_server/auth/` (Phase 12.3)

Не используется напрямую в Hermes change (OAuth scope — отдельный change). Но референсно: **existing Phase 12.3 OAuth 2.1** является образцом для любых MCP интеграций, требующих auth.

## Dependencies graph фаз

```
Ф0 (Memory Alignment) ──┬─→ Ф1 (Obsidian Vault)
                        ├─→ Ф2 (DSPy Deepening)
                        ├─→ Ф3 (Auto-Librarian) ← зависит также от Ф1
                        ├─→ Ф4 (PDF → Wiki) ← зависит также от Ф1, Ф2
                        └─→ Ф5 (Sandbox) ← зависит также от Ф2
```

Ф0 — блокер для всех остальных (расширение enum, migration, adapters, MemoryCube.to_wiki_page).
Ф6 (OAuth generalization) — независим, может идти параллельно с любой фазой.

## Migration strategy

### SQLite LinkRegistry migration

```sql
-- migrations/001_extend_link_types.sql
BEGIN;

-- Step 1: Save current data
CREATE TABLE links_backup AS SELECT * FROM links;

-- Step 2: Drop old CHECK constraint
-- SQLite doesn't support ALTER TABLE DROP CONSTRAINT — recreate table
CREATE TABLE links_new (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    link_type TEXT NOT NULL,
    strength REAL DEFAULT 0.8,
    created_at TEXT NOT NULL,
    metadata TEXT,
    CHECK (link_type IN (
        'based_on', 'supports', 'contradicts',
        'extends', 'derives_from', 'session_context',
        'promoted_to', 'superseded_by', 'mirrors', 'graph_node'  -- NEW
    ))
);

-- Step 3: Copy data
INSERT INTO links_new SELECT * FROM links;

-- Step 4: Swap tables
DROP TABLE links;
ALTER TABLE links_new RENAME TO links;

-- Step 5: Recreate indexes
CREATE INDEX idx_links_source ON links(source_id);
CREATE INDEX idx_links_target ON links(target_id);
CREATE INDEX idx_links_type ON links(link_type);

COMMIT;
```

**Rollback script:**
```sql
-- migrations/001_rollback.sql
BEGIN;
DELETE FROM links WHERE link_type IN ('promoted_to', 'superseded_by', 'mirrors', 'graph_node');
-- Recreate table with old CHECK constraint
-- (full rollback logic)
COMMIT;
```

**Dry-run:** `python scripts/migrate_link_registry.py --dry-run` — выводит diff без применения.

## Testing strategy

### Regression protection
- **НЕ ломать** 26 тестов `tests/integration/test_memory_unified.py`
- **НЕ ломать** 288 тестов `tests/unit/api/test_auth.py`
- **НЕ ломать** existing graph_store тесты

### New tests
- `tests/integration/test_memory_layers_v13.py` — полный цикл L0→L4
- `tests/unit/memory/test_memcube_wiki.py` — `to_wiki_page()` / `from_wiki_page()`
- `tests/unit/memory/test_wiki_adapter.py` — `WikiSearchAdapter`
- `tests/unit/memory/test_wiki_promoter.py` — `scan_and_promote()` с моками
- `tests/integration/test_link_registry_migration.py` — dry-run + apply + rollback
- `tests/unit/pdf_framework/test_wiki_exporter.py` — entity → markdown

### Eval
- `tests/eval/hermes_retrieval_precision.py` — сравнение baseline chunk RAG vs wiki pages pipeline на 10 PDF

## Риски и митигация

| Риск | Вероятность | Impact | Митигация |
|------|-------------|--------|-----------|
| SQLite migration ломает существующие данные | Low | High | Backup + dry-run + rollback script |
| Obsidian MCP overhead замедляет memory-first-hook | Medium | Medium | Timeout 2s per layer, graceful degradation |
| L2→L3 promotion создаёт мусор | Medium | Low | Drafts в gitignored до approved |
| DSPy миграция ломает существующие eval | Low | Medium | Параллельный запуск старых и новых промптов для сравнения |
| LightRAG Phase 38 несовместим с wiki export | Low | Medium | Spike до начала Фазы 4, fallback на nano-graphrag |
| Phase 12.3 OAuth extraction ломает BSL MCP | Low | High | Backward-compat wrapper, 288 тестов как guard |

## Открытые вопросы

1. **Obsidian free vs Sync:** использовать бесплатный локальный с git-sync, или Sync $96/год?
2. **Inline wiki-links vs frontmatter refs:** `[[name]]` в теле или `related: [...]` в YAML?
3. **Wiki в git vs отдельный vault-repo:** прозрачность vs чистота основного repo?
4. **Wiki pages как chunks или entities:** гранулярность индексации?
5. **Auto-librarian автономность:** auto-merge дубликатов или только уведомления?
6. **DSPy migration scope:** все 3 агента одновременно или поэтапно?
