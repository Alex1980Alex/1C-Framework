# Tasks: Hermes Agent / LLM Wiki

## Порядок выполнения

```
Ф0 (блокер) → Ф1 || Ф2 → Ф3 → Ф4 → Ф5 → Ф6 (параллельно)
```

## Фаза 0: Memory Layer Alignment (P0, блокер)

**Specs:** `memory-layer-alignment` (REQ-1..REQ-5)
**Files:** `src/memory/orchestrator/*.py`, `migrations/001_extend_link_types.sql`

### 0.1 UnifiedID расширение
- [ ] Добавить `MemoryType.WIKI = "wiki"` и `MemoryType.GRAPH = "graph"` в `src/memory/orchestrator/unified_id.py:26-40`
- [ ] Добавить `SourceServer.OBSIDIAN_VAULT = "obsidian-vault"` и `SourceServer.LIGHTRAG = "lightrag"` в `unified_id.py:43-70`
- [ ] Обновить `parse_unified_id()` + тесты на legacy IDs (backward-compat)

### 0.2 LinkRegistry SQL миграция
- [ ] Создать `migrations/001_extend_link_types.sql` с CREATE TABLE + COPY DATA + DROP OLD паттерном
- [ ] Создать `migrations/001_rollback.sql` для отката
- [ ] Создать `scripts/migrate_link_registry.py` с `--dry-run` и `--apply` флагами
- [ ] Добавить `LinkType.PROMOTED_TO`, `SUPERSEDED_BY`, `MIRRORS`, `GRAPH_NODE` в `link_registry.py:22-43` + `description` для каждого
- [ ] Обновить Python-level CHECK constraint в CREATE TABLE statement

### 0.3 MemoryCube расширение
- [ ] Добавить `ContentType.WIKI = "wiki"` в `memcube.py:23`
- [ ] Реализовать `MemoryCube.to_wiki_page() -> str` — сериализация в markdown с YAML frontmatter (unified_id, source, created_at, tags, links)
- [ ] Реализовать `MemoryCube.from_wiki_page(md: str) -> MemoryCube` — обратный парсинг
- [ ] Unit-тесты: roundtrip (cube → md → cube = оригинал)

### 0.4 UnifiedSearch adapters
- [ ] Создать директорию `src/memory/orchestrator/adapters/`
- [ ] `adapters/wiki_adapter.py` — `WikiSearchAdapter(BaseSearchAdapter)`, вызов obsidian-mcp через MCP клиент
- [ ] `adapters/graph_adapter.py` — `GraphSearchAdapter(BaseSearchAdapter)`, proxy к `entity_embeddings.py`
- [ ] В `memory_orchestrator.py.__init__`: `self._search_engine.register_adapter(WikiSearchAdapter(...))` и `register_adapter(GraphSearchAdapter(...))`
- [ ] НЕ трогать `UnifiedSearchEngine` core

### 0.5 MemoryRouter target
- [ ] Расширить `ContentClassifier._phase3_select_targets` в `memory_router.py:443` — добавить target `"wiki"`
- [ ] Добавить keywords для wiki в `_phase2_keyword_scoring:413`
- [ ] Реализовать `memory_orchestrator._save_to_target("wiki", content, metadata)` — создаёт draft в `docs/wiki/drafts/<slug>.md` через `MemoryCube.to_wiki_page()`

### 0.6 memory-first-hook Layer 0
- [ ] Добавить `WIKI_DIR = PROJECT_ROOT / "docs" / "wiki"` в `.claude/hooks/memory-first-hook.py`
- [ ] Реализовать `search_wiki(query_tokens: set, limit: int)` — семантический поиск через Qdrant `wiki_pages_v1`
- [ ] Перераспределить RRF веса: L1=0.30, L2=0.35, L3=0.15, **L4 (wiki)=0.20**
- [ ] Добавить обращение к `search_wiki()` в `execute():483` параллельно с `search_md()`

### 0.7 Тесты Фазы 0
- [ ] Интеграционный тест `tests/integration/test_memory_layers_v13.py` — полный цикл
- [ ] Запустить 26 существующих тестов `test_memory_unified.py` — **zero regression**
- [ ] `test_link_registry_migration.py` — dry-run + apply + rollback
- [ ] `test_memcube_wiki.py` — roundtrip тесты

**Трудоёмкость:** ~3-4 дня

---

## Фаза 1: Obsidian Vault Integration (P0, S)

**Specs:** TBD (`obsidian-vault` spec)
**Files:** `.mcp.json`, `.obsidian/`, `docs/wiki/`, `docs/architecture/*.md`

- [ ] Установить Obsidian desktop + плагин Local REST API
- [ ] `pip install mcp-obsidian` (или из git для editable)
- [ ] Добавить `obsidian-mcp` сервер в `.mcp.json` с env переменными
- [ ] Создать `.obsidian/app.json`, `.obsidian/workspace.json`, `.obsidian/community-plugins.json`
- [ ] `.gitignore` для `.obsidian/workspace.json` (пользовательский state)
- [ ] Создать структуру `docs/wiki/`: `_index.md`, `SCHEMA.md`, `log.md`, `entities/`, `concepts/`, `procedures/`, `patterns/`, `drafts/`
- [ ] Миграция `docs/architecture/*.md` (8 файлов) — добавить YAML frontmatter (`status`, `tags`, `related`) без изменения контента
- [ ] Split `docs/architecture/PATTERNS.md` (15+13 паттернов) на отдельные `docs/wiki/patterns/<name>.md` с cross-references
- [ ] Добавить `[[wiki-link]]` между связанными страницами
- [ ] Создать `.claude/skills/obsidian-vault/SKILL.md`
- [ ] Тест: graph view отображает ≥30 узлов, wiki-links кликабельны

**Трудоёмкость:** ~2-3 дня

---

## Фаза 2: DSPy Deepening + Wiki Schema (P1, S)

**Specs:** `dspy-signatures`
**Files:** `src/pdf_framework/prompts/signatures.py`, `src/pdf_framework/agents/*.py`, `docs/wiki/SCHEMA.md`

- [ ] Аудит: проверить нулевое использование `import dspy` в `src/pdf_framework/agents/`
- [ ] Создать `src/pdf_framework/prompts/signatures.py` с `GraderSignature`, `HallucinationCheckSignature`, `RewriterSignature`
- [ ] Мигрировать `agents/grader.py` на `dspy.Predict(GraderSignature)` — сохранить Ralph Wiggum self-correction через DSPy `Suggest`
- [ ] Мигрировать `agents/rewriter.py` на `dspy.ChainOfThought(RewriterSignature)`
- [ ] Мигрировать `agents/hallucination_check.py` на `dspy.Predict(HallucinationCheckSignature)` — типизированный `grounded: bool`
- [ ] Eval-сравнение: метрики до/после DSPy на существующем eval наборе. Rollback если regression >5%
- [ ] Создать `docs/wiki/SCHEMA.md` — правила ведения (5-слойная модель, frontmatter, cross-references)
- [ ] Создать `docs/wiki/log.md` — начальная запись хронологии

**Трудоёмкость:** ~2-3 дня

---

## Фаза 3: Auto-Librarian (P1, S)

**Specs:** `wiki-librarian`
**Files:** `.claude/hooks/docs-change-tracker.py` (extend), `src/memory/librarian/wiki_promoter.py` (new)

- [ ] `pip install kb-lint` + `npm i -D markdownlint-cli2`
- [ ] Настроить `.kb-lint.toml` и `.markdownlint.jsonc`
- [ ] **Расширить** `docs-change-tracker.py`: добавить wiki-validation (kb-lint на `docs/wiki/*.md`, проверка `[[wiki-link]]` targets)
- [ ] Создать `src/memory/librarian/__init__.py` + `src/memory/librarian/wiki_promoter.py` (~80-100 LoC):
  - Scan `learned_patterns` Qdrant с фильтром `confidence >= 0.8 AND usage_count >= 5`
  - Для каждого: `unified_search()` дедуп-проверка
  - Если дубликат (cosine >= 0.85) → `ConflictResolver.resolve(strategy=SOURCE_PRIORITY)` → `create_link(type=SUPERSEDED_BY)`
  - Если новый → `MemoryCube(content_type=WIKI).to_wiki_page()` + write в `docs/wiki/drafts/<slug>.md`
  - `create_link(pattern → wiki_draft, type=PROMOTED_TO)`
  - `event_bus.publish("wiki.promoted", {...})`
- [ ] **Расширить** `docs-change-enforcer.py`: Stop-check для pending drafts в `docs/wiki/drafts/`
- [ ] Интеграция с Phase 6.5 `IncrementalGraphUpdater` events — реэкспорт только affected entities
- [ ] Добавить `kb-lint` + `markdownlint-cli2` в `.pre-commit-config.yaml`
- [ ] Интеграционный тест: 10 синтетических паттернов → 10 drafts без дубликатов
- [ ] Smoke-тест: существующие тесты `docs-change-tracker` проходят без регрессии

**Трудоёмкость:** ~2-3 дня

---

## Фаза 4: PDF → Wiki Export (P2, M)

**Specs:** `wiki-export-pipeline`
**Files:** `src/pdf_framework/indexing/wiki_exporter.py` (new), `scripts/export_graph_to_wiki.py` (new)

- [ ] Аудит существующего Phase 38: запустить pipeline на 3 тестовых PDF, зафиксировать baseline качества entity extraction
- [ ] Spike: проверить совместимость `GraphStore.get_neighbors()` с wiki export паттерном
- [ ] Создать templates: `docs/wiki/templates/entity.md`, `concept.md`, `procedure.md` с frontmatter placeholder-ами
- [ ] Реализовать `src/pdf_framework/indexing/wiki_exporter.py` (300 LoC):
  - `WikiExporter.export_entity(entity_id)` — graph node → MemoryCube → markdown
  - `WikiExporter.export_community(community_id)` — использует existing `summarizer.py`
  - `WikiExporter.incremental_sync()` — подписка на `IncrementalGraphUpdater` events
- [ ] Создать `scripts/export_graph_to_wiki.py` CLI: `--since <timestamp>`, `--output docs/wiki/entities/`, `--dry-run`
- [ ] Reverse sync (wiki → graph): при Write в `docs/wiki/entities/<id>.md` → parse + update graph через existing `change_detector.py`
- [ ] Индексация wiki через существующий `src/memory/orchestrator/search/hybrid_search.py` — добавить wiki коллекцию, не писать свой BM25
- [ ] Обновить `src/pdf_framework/search/strategies/graphrag_light.py`: добавить `wiki_page_path` в payload, возвращать в результатах
- [ ] Eval-регрессия: existing GraphRAG eval suite должен показать **те же метрики или лучше**
- [ ] Создать `.claude/skills/wiki-pipeline/SKILL.md`
- [ ] Go/no-go решение: если производительность LightRAG-адаптера не подходит → fallback на `nano-graphrag` (~1100 LoC inline)

**Трудоёмкость:** ~5-7 дней

---

## Фаза 5: Sandbox для агентов (P3, S)

**Specs:** `agent-sandbox`
**Files:** `src/pdf_framework/sandbox/` (new)

- [ ] Оценить LangSmith sandbox (уже в `.venv` как транзитивная зависимость) — zero-cost fallback
- [ ] Если LangSmith подходит — создать `src/pdf_framework/sandbox/langsmith_backend.py` (простая обёртка)
- [ ] Иначе: `pip install e2b-code-interpreter` + получить E2B API key
- [ ] Создать `src/pdf_framework/sandbox/e2b_backend.py` с интерфейсом `SandboxBackend`
- [ ] Реализовать методы: `execute(code)`, `install(package)`, `upload/download(files)`
- [ ] Создать `dry_run_backend.py` для локальной разработки без API key
- [ ] Интегрировать sandbox в research-скиллы (`architecture-research`, `tech-research`)
- [ ] Timeout 30s, лимит 50 сессий/день
- [ ] Создать `.claude/skills/sandbox-execution/SKILL.md`
- [ ] Логирование sandbox-сессий в `docs/wiki/log.md`

**Трудоёмкость:** ~2-3 дня

---

## Фаза 6: OAuth 2.1 Generalization (P2, M — параллельно)

**Specs:** `oauth-extraction`
**Files:** `src/shared/mcp_oauth/` (new), `src/bsl/mcp_server/auth/oauth2.py` (wrapper)

- [ ] Аудит существующего `src/bsl/mcp_server/auth/oauth2.py` (350 LoC), задокументировать API в `docs/wiki/auth/oauth2-service.md`
- [ ] Экстракция `OAuth2Service` из BSL MCP в `src/shared/mcp_oauth/service.py` — generic component
- [ ] `src/shared/mcp_oauth/store.py` — `OAuth2Store` с pluggable backends (in-memory, SQLite, Redis)
- [ ] Backward-compat: `src/bsl/mcp_server/auth/oauth2.py` становится thin wrapper over shared
- [ ] Подключить `OAuth2Service` к `pdf-vector-graph` MCP server (опционально, за feature flag `MCP_OAUTH_ENABLED`)
- [ ] Расширить `tests/unit/api/test_auth.py` на generic Service (≥10 новых тестов)
- [ ] 288 существующих тестов **НЕ должны сломаться**
- [ ] Security review: audit log через existing `memory_audit_log` tool
- [ ] Обновить `.mcp.json` с env переменными для OAuth
- [ ] Создать `docs/wiki/auth/oauth-setup.md`

**Трудоёмкость:** ~3-4 дня

---

## Verification (после каждой фазы)

- [ ] Syntax check: `python -m py_compile <changed files>`
- [ ] Type check: `mypy src/` (только затронутые модули)
- [ ] Unit tests: `pytest tests/unit/memory/ tests/unit/pdf_framework/`
- [ ] Integration: `pytest tests/integration/test_memory_layers_v13.py`
- [ ] Regression: `pytest tests/integration/test_memory_unified.py tests/unit/api/test_auth.py` — **zero regression**
- [ ] Manual: запустить `memory-first-hook` на тестовом запросе, проверить L0-L4 покрытие
- [ ] `python -m src.cli.main search "wiki" --strategy hybrid` — проверить что wiki_pages_v1 попадает в результаты

## Итоговая оценка

- **Общая трудоёмкость:** ~17-25 дней разработки
- **Нового кода:** ~1500-1800 LoC glue
- **Рефакторинг:** ~400 LoC (OAuth экстракция)
- **Запуск:** Фазы 0-3 — 7-10 дней (minimal viable wiki), Фазы 4-6 — остальное

## Критерии завершения change

- [ ] Все фазы 0-6 завершены
- [ ] Все verification steps прошли
- [ ] Regression tests зелёные (0 регрессий)
- [ ] Новые метрики:
  - Retrieval precision ≥ baseline (target +10%)
  - L2→L3 promotion rate ≥3/week в eval окружении
  - Broken wiki-links = 0
  - MPF/DSPy compliance = 100% (3 agents)
  - Memory layer coverage = 5 (L0-L4)
- [ ] Документация обновлена: `CLAUDE.md`, `AGENTS.md`, `memory-unified` skill, новые skills (`obsidian-vault`, `auto-librarian`, `wiki-pipeline`, `sandbox-execution`)
- [ ] Change готов к архивации через `/opsx:archive hermes-llm-wiki`
