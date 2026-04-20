# Tasks: Hermes Agent / LLM Wiki

## Порядок выполнения

```
Ф0 (блокер) → Ф1 || Ф2 → Ф3 → Ф4 → Ф5 → Ф6 (параллельно)
```

## Сводный статус (обновлено 2026-04-20)

| Фаза | Название | Статус | Дата |
|------|----------|--------|------|
| Ф0 | Memory Layer Alignment | ✅ COMPLETE | 2026-04-19 |
| Ф1 | Obsidian Vault Integration | ✅ COMPLETE | 2026-04-20 |
| Ф2 | DSPy Deepening + Wiki Schema | ✅ CORE COMPLETE (eval → Phase 2.1) | 2026-04-20 |
| Ф3 | Auto-Librarian | ✅ CORE COMPLETE (incremental graph ← Ф4) | 2026-04-20 |
| Ф4 | PDF → Wiki Export | ✅ CORE COMPLETE (audit + eval require real PDF run) | 2026-04-20 |
| Ф5 | Sandbox для агентов | 🔲 TODO | — |
| Ф6 | OAuth 2.1 Generalization | 🔲 TODO | — |

**Следующий шаг:** Фаза 6 (OAuth 2.1 Generalization, P2) либо параллельно Фаза 5 (Sandbox, P3). См. секцию «Следующая фаза» в роадмапе.

## Фаза 0: Memory Layer Alignment (P0, блокер) — ✅ COMPLETE (2026-04-19)

**Specs:** `memory-layer-alignment` (REQ-1..REQ-5)
**Files:** `src/memory/orchestrator/*.py`, `migrations/001_extend_link_types.sql`
**Статус:** 274 tests pass (47 new + 227 existing), 0 regressions.

### 0.1 UnifiedID расширение
- [x] Добавить `MemoryType.WIKI = "wiki"` и `MemoryType.GRAPH = "graph"` в `src/memory/orchestrator/unified_id.py:26-40`
- [x] Добавить `SourceServer.OBSIDIAN_VAULT = "obsidian-vault"` и `SourceServer.LIGHTRAG = "lightrag"` в `unified_id.py:43-70`
- [x] Обновить `parse_unified_id()` + тесты на legacy IDs (backward-compat)

### 0.2 LinkRegistry SQL миграция
- [x] Создать `migrations/001_extend_link_types.sql` с CREATE TABLE + COPY DATA + DROP OLD паттерном
- [x] Создать `migrations/001_rollback.sql` для отката
- [x] Создать `scripts/migrate_link_registry.py` с `--dry-run` и `--apply` флагами
- [x] Добавить `LinkType.PROMOTED_TO`, `SUPERSEDED_BY`, `MIRRORS`, `GRAPH_NODE` в `link_registry.py:22-43` + `description` для каждого
- [x] Обновить Python-level CHECK constraint в CREATE TABLE statement

### 0.3 MemoryCube расширение
- [x] Добавить `ContentType.WIKI = "wiki"` в `memcube.py:23`
- [x] Реализовать `MemoryCube.to_wiki_page() -> str` — сериализация в markdown с YAML frontmatter (unified_id, source, created_at, tags, links)
- [x] Реализовать `MemoryCube.from_wiki_page(md: str) -> MemoryCube` — обратный парсинг
- [x] Unit-тесты: roundtrip (cube → md → cube = оригинал)

### 0.4 UnifiedSearch adapters
- [x] Создать директорию `src/memory/orchestrator/adapters/`
- [x] `adapters/wiki_adapter.py` — `WikiSearchAdapter(BaseSearchAdapter)`, вызов obsidian-mcp через MCP клиент (stub до установки obsidian-mcp в Phase 1)
- [x] `adapters/graph_adapter.py` — `GraphSearchAdapter(BaseSearchAdapter)`, proxy к `entity_embeddings.py`
- [x] В `memory_orchestrator.py.__init__`: `self._search_engine.register_adapter(WikiSearchAdapter(...))` и `register_adapter(GraphSearchAdapter(...))`
- [x] НЕ трогать `UnifiedSearchEngine` core

### 0.5 MemoryRouter target
- [x] Расширить `ContentClassifier._phase3_select_targets` в `memory_router.py:443` — добавить target `"wiki"`
- [x] Добавить keywords для wiki в `_phase2_keyword_scoring:413`
- [x] Реализовать `memory_orchestrator._save_to_target("wiki", content, metadata)` — создаёт draft в `docs/wiki/drafts/<slug>.md` через `MemoryCube.to_wiki_page()`

### 0.6 memory-first-hook Layer 0
- [x] Добавить `WIKI_DIR = PROJECT_ROOT / "docs" / "wiki"` в `.claude/hooks/memory-first-hook.py`
- [x] Реализовать `search_wiki(query_tokens: set, limit: int)` — token-overlap поиск по drafts (семантический fallback через Qdrant `wiki_pages_v1` отложен до Phase 1)
- [x] Перераспределить RRF веса: L1=0.30, L2=0.35, L3=0.15, **L4 (wiki)=0.20**
- [x] Добавить обращение к `search_wiki()` в `execute():483` параллельно с `search_md()`

### 0.7 Тесты Фазы 0
- [x] Интеграционный тест `tests/integration/test_memory_layers_v13.py` — полный цикл
- [x] Запустить 26 существующих тестов `test_memory_unified.py` — **zero regression** (227 total in memory integration suite pass)
- [x] `test_link_registry_migration.py` — dry-run + apply + rollback
- [x] `test_memcube_wiki.py` — roundtrip тесты

**Трудоёмкость:** ~3-4 дня

---

## Фаза 1: Obsidian Vault Integration (P0, S) — ✅ COMPLETE (2026-04-20)

**Specs:** TBD (`obsidian-vault` spec)
**Files:** `.mcp.json`, `.obsidian/`, `docs/wiki/`, `docs/architecture/*.md`
**Статус:** 15/16 задач выполнено, 1 отклонена как «НЕ требуется» (custom frontmatter tools — стандартный `patch_content` работает).

- [x] Установить Obsidian desktop + плагин Local REST API (Obsidian 1.7.7 + REST API v3.6.1)
- [x] `pip install mcp-obsidian` — покрыто `uvx` в `.mcp.json` (lazy-install)
- [x] Добавить `obsidian-mcp` сервер в `.mcp.json` с env переменными (`OBSIDIAN_API_KEY`, `OBSIDIAN_HOST`, `OBSIDIAN_PORT`)
- [x] Создать `.obsidian/app.json`, `.obsidian/workspace.json`, `.obsidian/community-plugins.json` (+ appearance, graph, templates)
- [x] `.gitignore` для `.obsidian/workspace.json` (пользовательский state)
- [x] Создать структуру `docs/wiki/`: `_index.md`, `SCHEMA.md`, `log.md`, `entities/`, `concepts/`, `procedures/`, `patterns/`, `drafts/`, `templates/`, `assets/`
- [x] Миграция `docs/architecture/*.md` (8 файлов) — frontmatter добавлен (59 wiki-links суммарно)
- [x] Split `docs/architecture/PATTERNS.md` (15+13 паттернов) → 28 файлов в `docs/wiki/patterns/` (commit 08ee1291)
- [x] Добавить `[[wiki-link]]` между связанными страницами
- [x] Создать `.claude/skills/obsidian-vault/SKILL.md`
- [x] Тест: graph view — 604 .md в vault scope (≫30 порог), 9 узлов с явными wiki-links verified via REST API

**Трудоёмкость:** ~2-3 дня

**Напоминание:** `obsidian-mcp` пока `disabled:true` в некоторых окружениях — требуется установка **Obsidian Desktop + Local REST API plugin** пользователем и рестарт Claude Code для активации `mcp__obsidian-mcp__*` tools.

---

## Фаза 2: DSPy Deepening + Wiki Schema (P1, S) — ✅ CORE COMPLETE (2026-04-20)

**Specs:** `dspy-signatures`
**Files:** `src/pdf_framework/prompts/signatures.py`, `src/pdf_framework/agents/*.py`, `docs/wiki/SCHEMA.md`
**Статус:** 8/9 задач выполнено. Формальный RAGAS eval-benchmark вынесен в Phase 2.1.

- [x] Аудит: проверить нулевое использование `import dspy` в `src/pdf_framework/agents/`
- [x] Создать `src/pdf_framework/prompts/signatures.py` с `GraderSignature`, `HallucinationCheckSignature`, `RewriterSignature`
- [x] Мигрировать `agents/grader.py` на `dspy.Predict(GraderSignature)` — Ralph Wiggum self-correction сохранена (3-level scoring)
- [x] Мигрировать `agents/rewriter.py` на `dspy.ChainOfThought(RewriterSignature)`
- [x] Мигрировать `agents/hallucination_check.py` на `dspy.Predict(HallucinationCheckSignature)` — типизированный `grounded: bool`
- [ ] Eval-сравнение: метрики до/после DSPy (RAGAS) — **TODO Phase 2.1** (unit-тесты 115 pass подтверждают отсутствие code-level регрессий)
- [x] Создать `docs/wiki/SCHEMA.md` — правила ведения (5-слойная модель, frontmatter, cross-references, L2→L3 promotion)
- [x] Создать `docs/wiki/log.md` — начальная запись хронологии (+ session-memory-save.py append on Stop)

**Трудоёмкость:** ~2-3 дня

**Известные ограничения:**
- `dspy-ai` не установлен в `.venv` — Phase 2 работает через fallback chain `cheap_llm → DSPy → LangChain`, DSPy-путь молча пропускается. Для измеримого DSPy eval в Phase 2.1 нужно `pip install dspy-ai`.

---

## Фаза 3: Auto-Librarian (P1, S) — ✅ CORE COMPLETE (2026-04-20)

**Specs:** `wiki-librarian`
**Files:** `.claude/hooks/docs-change-tracker.py` (extend), `src/memory/librarian/wiki_promoter.py` (new)
**Статус:** 9/10 задач выполнено. Incremental graph integration зависит от Phase 4 wiki_exporter.

- [x] `pip install kb-lint` + `npm i -D markdownlint-cli2`
- [x] Настроить `.kb-lint.toml` и `.markdownlint.jsonc`
- [x] **Расширить** `docs-change-tracker.py`: добавить wiki-validation (kb-lint на `docs/wiki/*.md`, проверка `[[wiki-link]]` targets)
- [x] Создать `src/memory/librarian/__init__.py` + `src/memory/librarian/wiki_promoter.py` (~120 LoC):
  - Scan `learned_patterns` Qdrant с фильтром `confidence >= 0.8 AND usage_count >= 5`
  - Для каждого: `unified_search()` дедуп-проверка
  - Если дубликат (cosine >= 0.85) → `ConflictResolver.resolve(strategy=SOURCE_PRIORITY)` → `create_link(type=SUPERSEDED_BY)`
  - Если новый → `MemoryCube(content_type=WIKI).to_wiki_page()` + write в `docs/wiki/drafts/<slug>.md`
  - `create_link(pattern → wiki_draft, type=PROMOTED_TO)`
  - `event_bus.publish("wiki.promoted", {...})`
- [x] **Расширить** `docs-change-enforcer.py`: Stop-check для pending drafts в `docs/wiki/drafts/`
- [ ] Интеграция с Phase 6.5 `IncrementalGraphUpdater` events — реэкспорт только affected entities _(TODO — заблокировано Phase 4 wiki_exporter hookup)_
- [x] Добавить `kb-lint` + `markdownlint-cli2` в `.pre-commit-config.yaml`
- [x] Интеграционный тест: 15 тестов `test_wiki_promoter.py` pass
- [x] Smoke-тест: 47 существующих Phase 0 тестов + 15 новых = 62 pass, 0 регрессий

**Трудоёмкость:** ~2-3 дня

---

## Фаза 4: PDF → Wiki Export (P2, M) — ✅ CORE COMPLETE (2026-04-20)

**Specs:** `wiki-export-pipeline`
**Files:** `src/pdf_framework/indexing/wiki_exporter.py` (new, 692 LoC), `scripts/export_graph_to_wiki.py` (new, 218 LoC)
**Статус:** 9/11 задач выполнено + skill. Verified by code-verify. Остаются Phase 38 audit + eval regression (требуют реального прогона на PDF).

- [ ] Аудит существующего Phase 38: запустить pipeline на 3 тестовых PDF, зафиксировать baseline качества entity extraction _(TODO — требует реального PDF прогона)_
- [x] Spike: проверить совместимость `GraphStore.get_neighbors()` с wiki export паттерном
- [x] Создать templates: `docs/wiki/templates/entity.md`, `concept.md`, `procedure.md` с frontmatter placeholder-ами
- [x] Реализовать `src/pdf_framework/indexing/wiki_exporter.py` (692 LoC):
  - `WikiExporter.export_entity(entity_id)` — graph node → MemoryCube → markdown
  - `ForwardSyncService` — graph→wiki sync
  - `IncrementalWikiSync` — event-driven + DLQ
  - `ReverseSyncService` — watchdog для wiki→graph
  - `WikiSearchIndexer` — delegates to HybridSearchService
- [x] Создать `scripts/export_graph_to_wiki.py` CLI (218 LoC, 5 subcmds: `export`, `incremental`, `reverse-sync`, `index`, `status`)
- [x] Reverse sync (wiki → graph): при Write в `docs/wiki/entities/<id>.md` → parse + update graph через `ReverseSyncService` (watchdog)
- [x] Индексация wiki через существующий `src/memory/orchestrator/search/hybrid_search.py` — `WikiSearchIndexer` делегирует, не пишет свой BM25
- [x] Обновить `src/pdf_framework/search/strategies/graphrag_light.py`: `wiki_page_paths` в `SearchResponse.metadata` ([graphrag_light.py:219](../../src/pdf_framework/search/strategies/graphrag_light.py#L219))
- [ ] Eval-регрессия: existing GraphRAG eval suite должен показать те же метрики или лучше _(TODO — требует реального прогона)_
- [x] Создать `.claude/skills/wiki-pipeline/SKILL.md`
- [x] Go/no-go решение: LightRAG Phase 38 адаптер работает через markdown export (fallback на nano-graphrag не потребовался)

**Acceptance criteria (блокируются audit/eval):**
- [ ] ≥3 wiki pages per PDF
- [ ] Schema validation ≥95%
- [ ] Precision ≥80%
- [ ] `wiki_pages_v1` коллекция populated
- [ ] Retrieval improvement ≥10% vs GraphRAG baseline

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
