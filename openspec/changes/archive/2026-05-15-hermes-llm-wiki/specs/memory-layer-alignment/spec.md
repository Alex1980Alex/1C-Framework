# Spec: memory-layer-alignment

**Change:** hermes-llm-wiki
**Phase:** 0 (блокер)
**Profile:** python-framework

## Контекст

Существующая memory-инфраструктура фреймворка включает:
- `src/memory/orchestrator/unified_id.py` — `MemoryType` enum (4 values), `SourceServer` enum (5 values)
- `src/memory/orchestrator/link_registry.py` — `LinkType` enum (6 values) + SQLite с CHECK constraint
- `src/memory/orchestrator/memcube.py` — `MemoryCube` с 3 serialization methods
- `src/memory/orchestrator/unified_search.py` — `BaseSearchAdapter(ABC)` + `UnifiedSearchEngine.register_adapter()` extension point
- `src/memory/orchestrator/memory_router.py` — `ContentClassifier` с 3-фазной классификацией
- `.claude/hooks/memory-first-hook.py` — 3-слойный RRF-federated search (504 LoC)

Фаза 0 расширяет эти компоненты под wiki-слой **без переписывания core**.

---

## ## ADDED REQ-1: MemoryType.WIKI и MemoryType.GRAPH

**Файл:** `src/memory/orchestrator/unified_id.py`

Добавить новые members в `MemoryType` enum:

```python
class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    LEARNING = "learning"
    DOCUMENTATION = "documentation"
    WIKI = "wiki"          # NEW — для canonical L3 wiki pages
    GRAPH = "graph"        # NEW — для LightRAG entity graph nodes
```

**Given** запрос содержит `memory_type=MemoryType.WIKI`
**When** вызывается `parse_unified_id("wiki:obsidian-vault:entities/qdrant-ops.md")`
**Then** возвращается `UnifiedID(memory_type=WIKI, source=OBSIDIAN_VAULT, identifier="entities/qdrant-ops.md")`

**Граничные условия:**
- Legacy IDs без новых типов продолжают парситься (backward compat)
- Unknown memory_type → `ValueError` с явным сообщением

---

## ## ADDED REQ-2: SourceServer.OBSIDIAN_VAULT и SourceServer.LIGHTRAG

**Файл:** `src/memory/orchestrator/unified_id.py`

Добавить новые members в `SourceServer` enum:

```python
class SourceServer(str, Enum):
    MEMORY_AI = "memory-ai"
    VECTOR_MEMORY = "vector-memory"
    SKILL_LEARNING = "skill-learning"
    PDF_DOCS = "pdf-docs"
    ORCHESTRATOR = "orchestrator"
    OBSIDIAN_VAULT = "obsidian-vault"   # NEW
    LIGHTRAG = "lightrag"               # NEW
```

**Given** существующий код использует `SourceServer.MEMORY_AI`
**When** добавлены новые values
**Then** existing код продолжает работать без изменений (append-only enum extension)

---

## ## MODIFIED REQ-3: LinkType enum + SQL migration

**Файл:** `src/memory/orchestrator/link_registry.py`
**Было:** 6 link types, SQL CHECK constraint фиксирует только эти 6
**Стало:** 10 link types (6 existing + 4 new), SQL миграция расширяет CHECK constraint

### Новые LinkType members

```python
class LinkType(str, Enum):
    BASED_ON = "based_on"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    DERIVES_FROM = "derives_from"
    SESSION_CONTEXT = "session_context"
    PROMOTED_TO = "promoted_to"         # NEW: L2 pattern → L3 wiki page
    SUPERSEDED_BY = "superseded_by"     # NEW: old entity replaced by new (dedup)
    MIRRORS = "mirrors"                 # NEW: L3 wiki ↔ L4 embedding (derived index)
    GRAPH_NODE = "graph_node"           # NEW: L3 wiki ↔ LightRAG entity node
```

### SQL Migration (критично)

**Текущий constraint** в `link_registry.py:219-222`:
```sql
CHECK (link_type IN (
    'based_on', 'supports', 'contradicts',
    'extends', 'derives_from', 'session_context'
))
```

**После миграции:**
```sql
CHECK (link_type IN (
    'based_on', 'supports', 'contradicts',
    'extends', 'derives_from', 'session_context',
    'promoted_to', 'superseded_by', 'mirrors', 'graph_node'
))
```

**SQLite не поддерживает `ALTER TABLE DROP CONSTRAINT`** — требуется CREATE NEW + COPY DATA + DROP OLD + RENAME паттерн (см. `migrations/001_extend_link_types.sql`).

**Given** существующая база `data/link_registry.db` с 6 link types
**When** запущен `python scripts/migrate_link_registry.py --apply`
**Then** CHECK constraint обновлён, existing links сохранены, новые 4 типа доступны

**Rollback:**
**Given** после миграции обнаружена проблема
**When** запущен `python scripts/migrate_link_registry.py --rollback`
**Then** БД возвращена к состоянию до миграции, связи с новыми типами (если были созданы) удалены

**Verification:**
- `--dry-run` выводит diff без изменений
- Unit test: создать link с type=`promoted_to` после миграции, read back — OK
- Unit test: создать link с type=`promoted_to` до миграции — `IntegrityError`

---

## ## MODIFIED REQ-4: MemoryCube.to_wiki_page() / from_wiki_page()

**Файл:** `src/memory/orchestrator/memcube.py`
**Было:** 3 serialization methods (`to_ai_memory_row`, `to_vector_memory_payload`, `to_skill_learning_record`)
**Стало:** добавлены `to_wiki_page()` и `from_wiki_page()` + `ContentType.WIKI`

### ContentType extension

```python
class ContentType(str, Enum):
    # ... existing types
    WIKI = "wiki"  # NEW
```

### to_wiki_page() signature

```python
def to_wiki_page(self) -> str:
    """Serialize to markdown with YAML frontmatter.

    Returns:
        Markdown string ready to write to docs/wiki/<path>.md

    Format:
        ---
        unified_id: <wiki:obsidian-vault:path>
        content_type: <WIKI>
        source: <source-id>
        created_at: <ISO timestamp>
        tags: [<tag1>, <tag2>]
        links: [<related-id1>, <related-id2>]
        ---

        # <title>

        <body content>
    """
```

### from_wiki_page() signature

```python
@classmethod
def from_wiki_page(cls, md: str) -> MemoryCube:
    """Parse markdown with YAML frontmatter back to MemoryCube.

    Raises:
        ValueError: If frontmatter missing or invalid
    """
```

**Given** `MemoryCube(content_type=WIKI, content="...", metadata={...})`
**When** вызывается `cube.to_wiki_page()`
**Then** возвращается markdown с валидным YAML frontmatter, включающим `unified_id`, `content_type: wiki`, `source`, `created_at`

**Given** markdown файл с валидным frontmatter
**When** вызывается `MemoryCube.from_wiki_page(md)`
**Then** возвращается MemoryCube идентичный исходному (roundtrip)

**Граничные условия:**
- Missing frontmatter → `ValueError("No YAML frontmatter found")`
- Invalid YAML → `ValueError` с позицией ошибки
- Empty body → разрешено, content пустой

---

## ## ADDED REQ-5: WikiSearchAdapter и GraphSearchAdapter

**Файлы:**
- `src/memory/orchestrator/adapters/__init__.py` (новый)
- `src/memory/orchestrator/adapters/wiki_adapter.py` (новый)
- `src/memory/orchestrator/adapters/graph_adapter.py` (новый)

Используют существующий `BaseSearchAdapter(ABC)` и `UnifiedSearchEngine.register_adapter()` — **без изменений в core**.

### WikiSearchAdapter

```python
class WikiSearchAdapter(BaseSearchAdapter):
    """Search adapter for Obsidian vault via mcp-obsidian MCP client."""

    def __init__(self, mcp_client: MCPClient, vault_path: Path):
        self._client = mcp_client
        self._vault = vault_path

    async def search(
        self, query: str, limit: int = 10, **kwargs
    ) -> list[SearchResultItem]:
        # Call obsidian-mcp search tool
        # Return SearchResultItem with unified_id=wiki:obsidian-vault:<path>

    @property
    def source_name(self) -> str:
        return SourceServer.OBSIDIAN_VAULT.value
```

### GraphSearchAdapter

```python
class GraphSearchAdapter(BaseSearchAdapter):
    """Search adapter for LightRAG entity graph (Phase 38)."""

    def __init__(self, entity_embeddings: EntityEmbeddingBuilder):
        self._entity_embeddings = entity_embeddings

    async def search(
        self, query: str, limit: int = 10, **kwargs
    ) -> list[SearchResultItem]:
        # Query existing graph_embeddings Qdrant collection
        # Return SearchResultItem with unified_id=graph:lightrag:<entity-id>
```

### Регистрация

В `memory_orchestrator.py.__init__`:
```python
if self._search_engine:
    self._search_engine.register_adapter(WikiSearchAdapter(...))
    self._search_engine.register_adapter(GraphSearchAdapter(...))
```

**Given** UnifiedSearchEngine инициализирован
**When** вызывается `engine.search(query="Qdrant operations")`
**Then** результаты включают entries из wiki (через `WikiSearchAdapter`) и graph (через `GraphSearchAdapter`), отсортированные через существующий `RRFMerger.fuse()`

**Given** wiki page имеет link `superseded_by` → old pattern
**When** результаты проходят через `Deduplicator` и `LinkEnricher`
**Then** old pattern исключается из выдачи (дедуп)

**Граничные условия:**
- obsidian-mcp недоступен → `WikiSearchAdapter` возвращает пустой список + log warning (graceful degradation)
- Нет graph_embeddings в Qdrant → `GraphSearchAdapter` возвращает пустой список
- Таймаут 2s на каждый adapter → управляется через existing `CircuitBreaker` from `infrastructure/`

---

## Регрессия

Фаза 0 **НЕ ДОЛЖНА** ломать:

- [ ] 26 существующих тестов `tests/integration/test_memory_unified.py`
- [ ] Все существующие MCP tools orchestrator (33 tools)
- [ ] Existing `LinkRegistry.create_link()` с legacy типами (`based_on`, `supports`, и т.д.)
- [ ] Existing `UnifiedSearchEngine.search()` без регистрации новых adapters
- [ ] Existing `MemoryCube.to_ai_memory_row()` / `to_vector_memory_payload()` / `to_skill_learning_record()`
- [ ] Existing behavior `memory-first-hook.py` для не-wiki запросов (Layer 1-3 должны работать как раньше)

## Новые тесты

- `tests/integration/test_memory_layers_v13.py` — полный цикл промоции L1→L2→L3
- `tests/unit/memory/test_memcube_wiki.py` — roundtrip `to_wiki_page()` ↔ `from_wiki_page()`
- `tests/unit/memory/test_wiki_adapter.py` — mock obsidian-mcp, проверка SearchResultItem format
- `tests/unit/memory/test_graph_adapter.py` — mock entity_embeddings, проверка результатов
- `tests/integration/test_link_registry_migration.py` — dry-run + apply + rollback на снапшоте БД
- `tests/unit/memory/test_unified_id_parse.py` — legacy IDs + new types backward compat
