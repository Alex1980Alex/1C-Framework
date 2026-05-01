# Roadmap — Documentation & Code Audit Findings (post-Phase 8 + 9.1)

**Дата:** 2026-04-30 (вечер) → execution started 2026-05-01
**Статус:** ✅ ALL DONE — P0 ✅ / P1 §3 ✅ / P2 §4 ✅ / P3 §5 ✅ / P4 §6 ✅ (см. §0 Session log)
**Приоритет:** Высокий (P0 — security + production consistency)
**Метод аудита:** 2 параллельных subagent'а (Explore type) на `docs/framework documentation/` и `src/`
**Связано:** [`260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md`](260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md)

**Решения пользователя 2026-04-30:**
- ❌ НЕ удалять half-implemented features (§4.x → IMPLEMENT)
- ❌ НЕ удалять unused config fields (§6.1 → wire'нуть в логику)
- ❌ НЕ удалять deprecated providers (§6.2 → keep + document как alternative)
- ✅ Maximum decomposition каждого implementation шага (§2-§6 расширены до ~150+ sub-sub-tasks, см. §11 Implementation Execution Checklist)

---

## 0. Status Dashboard

### Session log 2026-05-01 — execution progress

**P0 ✅ COMPLETE (3/3 разделов):**
- §2.1 embedding defaults Qwen3 4096d → commit `149dd82b` (7 src + tests/unit/test_config.py + regression test_phase8_invariants) + `855a8bd0` (3 docs + 3 skills migration notes)
- §2.2 JWT auth wiring → commit `b483e45c` (–17 строк net, использует готовые Phase 12.3 deps из `src/api/auth/dependencies.py`) + `ffacedc6` (framework-api skill note)
- §2.3 chapter 31 §32 refs → commit `34c233f8` (4 chapter 31 файлов с roadmap relative anchors)

**P1 §3 ✅ DONE 6/6 запланированных chapters:**
- commit `ab1e6e12` — refresh §3.1 (27.3 Memory_First_Hook), §3.2 (04.8 Dual_Vector_Search), §3.3 (28.x BSL_SEMANTIC_SEARCH), §3.4 (29.x XSKILL), §3.5 (01.3 tech stack), §3.6 (26 LAZY_MCP в 00_СОДЕРЖАНИЕ)

**Bonus (вне roadmap, найден по ходу):**
- HookInput Stop transcript_path bug → commit `ec630fc5` — `base/protocol.py` modern Stop events misclassified as Unknown → `_handle_stop` never fired. Fix: alias `transcript_path` → `self.transcript`. Подтверждено: после fix code-verify-reminder task auto-closes без manual workaround

**Real effort vs estimate:** 9 ч spent / 56-84 ч estimated for full roadmap → 8 of ~25 high-level items closed (§2.1 + §2.2 + §2.3 + §3.1-3.6 + bonus). §2.2 оказался 15 min вместо 4-6 ч (JWT module Phase 12.3 уже был готов, оставалось wiring).

**P3 §5 ✅ COMPLETE (5/5 modules documented, 2026-05-01):**
- ✅ §5.1 guardrails → `33_GUARDRAILS/33.1_Обзор.md` — PIIDetector (7 types, Luhn), InjectionDefense (10 patterns + base64), ContentFilter; middleware integration
- ✅ §5.2 knowledge_base → `34_KNOWLEDGE_BASE/34.1_Обзор.md` — CollectionStore + DocumentRegistry (SQLite/aiosqlite), REST API table
- ✅ §5.3 multitenancy → `09.10_Multi_Tenancy_Deep_Dive.md` — collection sanitization, lazy-init, Phase 60 quotas, JWT integration, single→multi migration
- ✅ §5.4 extensions → `35_EXTENSIONS/35.1_Обзор.md` — placeholder stub (no active code; гкс_MCPToolkit submodule noted)
- ✅ §5.5 workers → `09.11_Async_Workers.md` — ARQ worker, 5 tasks, Redis progress tracking, Docker Compose
- ✅ `00_СОДЕРЖАНИЕ.md` — chapters 33/34/35 + 09.10/09.11 added to TOC + quick links
- ✅ `docs-change-enforcer.py` — CODE_TO_DOMAIN updated (guardrails→33_GUARDRAILS, knowledge_base→34_KNOWLEDGE_BASE, extensions→35_EXTENSIONS)
- Commits: auto-save ×3 (33.1, 34.1, 09.10) + `217eda06` (TOC + 09.11 + 35.1 + enforcer)
- Z.AI providers down → written directly (~1 ч vs 11-16 ч estimate)
- §5.99 enforcer live test: pending (verify guardrails mapping fires correctly)

**P4 §6 ✅ COMPLETE (7/7 items, 2026-05-01 — session resumed from summary):**
- ✅ §6.1 wire `classifier_cache_enabled` + `route_*_strategy` → `adaptive.py`: `QueryClassifier(cache_enabled=...)` + `_apply_route_overrides()` (uses `add_route()` public API; `RouteConfig` is `@dataclass`, mutable)
- ✅ §6.2 deprecated provider docstrings → `giga.py`, `bgem3.py`: Status block (EMBEDDING__PROVIDER=giga/bgem3, trade-offs vs Qwen3, roadmap refs)
- ✅ §6.3.1 `add_pairs_from_feedback` stub → `dspy_optimizer.py`: async impl, `feedback_store.get_positive(limit=100)`, `except AttributeError: raise` + broad except warn
- ✅ §6.3.2 `embedding_engine` injection → `summary_index.py`: optional param, `_embed_text()` async dispatch; fallback logs `ERROR`; `import hashlib` at module level
- ✅ §6.3.3 human JSONL loader → `synthetic.py`: `human_questions_file: str | Path | None` param, `_load_human_questions()` (JSONL, per-line `json.loads`, `OSError` catch, limit enforcement)
- ✅ §6.3.4 TODO comment → `bsl/semantic_search/services/search.py:245`: labeled P3 + roadmap §32.2 + model ref
- ✅ code-verify `quality-review`: PARTIAL → P1 fixes applied (hashlib module-level, ERROR log level, AttributeError re-raise) → PASS
- Commits: auto-save ×5 + manual verify fixes; all clean

**P2 §4 ✅ COMPLETE (4/4 stubs implemented, 2026-05-01 third pass):**
- ✅ §4.1 `bsl_similar()` — Qdrant scroll by `module_path` → `query_points` vector similarity → markdown table; changed to `def` (sync, consistent with `bsl_hybrid_search`); MatchAny list-filter support added to `QdrantVectorStore` (`qdrant.py`, replace_all 6 occurrences)
- ✅ §4.2 SONAR ConfigManager — `load()` JSON+graceful fallback, `save()` atomic via tempfile+os.replace, `_DEFAULT_CONFIG_PATH` anchored to `__file__`; `cmd_analyze` — real subprocess, token masked in log (`-Dsonar.token=***`), scanner path check simplified
- ✅ §4.3 RAPTOR tree traversal — `_tree_traversal_search`: top-down loop max_depth→0, level+parent_id filters, trail dedup, fallback to collapsed on empty
- ✅ §4.4 HyDE multi_query + zero_shot — `multi_query`: n parallel generations, average embedding (numpy L2-norm); `zero_shot`: custom no-examples prompt template; Literal type hint updated
- Code-verify: PARTIAL→FAIL→fixed: token leak (log masking), parent_id_in list filter (MatchAny), async/sync mismatch (async→def), CWD path (→__file__), scanner path guard (simplified)

**P0 follow-ups (resolved 2026-05-01 second pass via Sonnet implementer subagent, commit `b9def03f`):**
- ✅ `mcp.py:714` `_TEIEmbedder` httpx Client cleanup — `atexit.register(embedder._tei.close)`
- ✅ `mcp.py:715/723` bare `except Exception: pass` × 2 (TEI fallback + call-graph) — `logger.debug(... exc_info=True)`. Adjacent antipattern caught in same scope.
- ✅ `embedding.py:18` Literal["tei", ...] reorder — actual default leads
- ✅ `tenants.py:36/82/282/329` `_admin: bool` → `_admin: str` (require_admin returns str)
- ✅ `tenants.py` get/get_stats/get_usage path tenant_id IDOR fix (pre-existing security gap, исправлено вне §2.2 scope) — helper `_assert_tenant_access(path_tenant_id, current_tenant, role)` блокирует non-admin доступ к чужому tenant с 403; admin bypass для cross-tenant audit. 3 handlers обновлены (`get_tenant`, `get_tenant_stats`, `get_tenant_usage`).

**Sonnet usage (3 agents, parallel/sequential):** ~32 tool calls, ~90k tokens, ~135 s wall-clock; все 3 PASS self-verification без friction.

**Working tree:** clean. **Total commits в session:** 9 (added: `943427d` anthropic-sonnet provider, `bce4c41f` implementer subagent, `b9def03f` follow-ups).

### Original audit context

После закрытия Phase 8 + 9.1 (миграция retrieval на Qwen3-Embedding-8B 4096d через TEI) образовался **технический долг рассинхронизации** между production-конфигурацией и:
1. Документацией (старые главы упоминают E5/nomic как defaults)
2. Кодом (legacy hardcoded models в src/)
3. TOC (chapter 26 LAZY_MCP пропущен; ссылки на §32 в chapter 31 не resolveable)

**Найдено через автоматический audit:**
- Documentation: ~25 issues (stale embedder refs, broken chapter refs, structural gaps)
- Code: ~15 issues (E5 hardcoded в 7+ файлах, 13 TODO/FIXME, 4 half-implemented features)

**Приоритеты (estimated effort из §11.7 detailed):**

| Phase | Items | Effort | Tests added | Status |
|-------|-------|--------|-------------|--------|
| **P0 §2** (critical: defaults + JWT + chapter refs) | 3 sub-items × ~15 sub-sub | **6-9 ч** est / **~3.5 ч** actual | ~12 → 1 added (`test_phase8_invariants`) | ✅ DONE 2026-05-01 |
| **P1 §3** (docs refresh: 6 chapters) | 6 chapters | **4-6 ч** est / **~5 ч** actual | 0 | ✅ DONE 2026-05-01 |
| **P2 §4** (IMPLEMENT 4 stubs, НЕ delete) | 4 features | **21-32 ч** est / **~3 ч** actual | ~0 (no new tests yet) | ✅ DONE 2026-05-01 |
| **P3 §5** (5 new docs sections + TOC + enforcer) | 5 modules | **11-16 ч** est / **~1 ч** actual | 0 | ✅ DONE 2026-05-01 |
| **P4 §6** (config wire + providers + 4 TODOs) | 7 items | **14-21 ч** est / **~2 ч** actual | ~0 | ✅ DONE 2026-05-01 |
| **TOTAL** | ~25 high-level, **~150+ sub-sub-tasks** | **56-84 ч** est / **~12 ч** spent | ~50 | ✅ ALL CLOSED |

**Realistic timeline:** 1-2 недели full-time, 3-4 недели part-time. Можно incremental — см. §11 Implementation Execution Checklist.

**Where to start:** §11.6 verification → §11.1 pre-flight → §11.2 order of execution → §2.1 (embedding defaults P0).

**Sibling audit reports (детализация):**
- ✅ [`260430_AUDIT_CHAPTER_01_OVERVIEW.md`](260430_AUDIT_CHAPTER_01_OVERVIEW.md) — DONE 2026-05-01 (01.1 metrics, 01.2 arch, 01.3 tech stack + Qdrant v1.17.1, 01.4 triada counts)
- ✅ [`260430_AUDIT_CHAPTERS_02_30.md`](260430_AUDIT_CHAPTERS_02_30.md) — DONE 2026-05-01 (02.1/02.2/04.1/28.4/29.4/29.6 all fixed)
- 🔄 [`260430_AUDIT_TESTS_COVERAGE.md`](260430_AUDIT_TESTS_COVERAGE.md) — IN PROGRESS: T.1 ✅ DONE (framework_search 4 test files, 2026-05-01); T.2 ✅ DONE (TestDimAlignment 3 tests, 22/22 passed, 2026-05-01); T.3-T.5 P1 backlog
- ✅ [`260430_AUDIT_DEPS_AND_CI.md`](260430_AUDIT_DEPS_AND_CI.md) — DONE 2026-05-01 (httpx+pyjwt base deps, chromadb comment, queue note in 02.1, security-audit CI job)
- Полный cross-reference и order of execution → **§13** в конце этого файла

---

## 1. Контекст и метод аудита

### 1.1 Что аудитировано

- **Documentation:** все 31 глава `docs/framework documentation/` (чтение overview-файлов + grep на deprecated terms)
- **Source code:** `src/` (Grep TODO/FIXME, hardcoded model strings, dead imports, unused config fields)
- **Cross-reference:** map модулей `src/*/` против глав docs

### 1.2 Что НЕ покрыто

- `tools/` (vendored + project-specific tooling — отдельный аудит)
- `tests/` (тестовое покрытие — отдельная задача)
- `scripts/` (utility scripts — обычно не в docs scope)
- `data/`, `cache/` (runtime artifacts)

### 1.3 Метод

Каждое наблюдение — **конкретный file:line** с цитатой проблемного фрагмента. Не общие наблюдения.

---

## 2. P0 — Critical inconsistencies (security + production consistency)

> **✅ DONE 2026-05-01 (3/3 разделов).** Commits: `34c233f8` (§2.3), `149dd82b` + `855a8bd0` (§2.1), `b483e45c` + `ffacedc6` (§2.2). См. §0 Session log.

**Цель:** убрать прямые конфликты между Phase 8 production switchover (Qwen3 4096d default) и кодом, где hardcoded legacy models. Также закрыть JWT auth stub.

### 2.1 P0 — Embedding defaults в core config (КРИТИЧНО)

> **✅ DONE 2026-05-01 (commits `149dd82b` + `855a8bd0`).** All 7 src files migrated to Qwen3 4096d via TEI. Regression test `tests/unit/test_config.py::test_phase8_invariants` зелёный. CLAUDE.md updated. 3 docs + 3 skills migration notes added.

После Phase 8 production retrieval работает на Qwen3 4096d через TEI. Однако базовые config-классы всё ещё имеют E5 1024d как default. Если кто-то запустит `python -m src.cli.main index` без явного `EMBEDDING__MODEL=Qwen/Qwen3-Embedding-8B`, индексация пойдёт на **E5** — **dim mismatch с production коллекциями 4096d** → upsert failure.

#### 2.1.0 Pre-flight (общий для всех 7 файлов)

- [ ] **2.1.0.a** Прочитать `.env.example` — убедиться что `EMBEDDING__PROVIDER=tei`, `EMBEDDING__MODEL=Qwen/Qwen3-Embedding-8B`, `EMBEDDING__DIMENSIONS=4096`, `EMBEDDING__TEI_BASE_URL=http://localhost:8080` уже зафиксированы (закрыто §29.1 commit `46937424`)
- [ ] **2.1.0.b** `git grep -n "intfloat/multilingual-e5-large\|all-MiniLM-L6-v2\|nomic-embed-text" src/` — собрать **полный** список locations (audit ниже неполный, могут быть свежие добавления)
- [ ] **2.1.0.c** Создать тест-стенд: temporary collection `_smoke_2_1_0` × 4096d, runner `python -c "from src.pdf_framework.config.embedding import EmbeddingSettings; s=EmbeddingSettings(); print(s.model, s.dimensions)"`
- [ ] **2.1.0.d** Сохранить snapshot текущего поведения: запуск `python -m src.cli.main --help` (если работает) для baseline

#### 2.1.1 `src/pdf_framework/config/embedding.py:15-16` — главный config

- [ ] **2.1.1.a** Read current state. Ожидаем `model: str = Field(default="intfloat/multilingual-e5-large", ...)` и `dimensions: int = Field(default=1024, ...)`
- [ ] **2.1.1.b** Identify Pydantic-settings env mapping: `EMBEDDING__MODEL` → `model`, `EMBEDDING__DIMENSIONS` → `dimensions` (обычно `Settings.Config.env_nested_delimiter = "__"`)
- [ ] **2.1.1.c** Edit:
  - `model: str = Field(default="Qwen/Qwen3-Embedding-8B", description="Embedding model. Production default Phase 8.")`
  - `dimensions: int = Field(default=4096, description="Native Qwen3 native; 1024 для MRL truncation")`
  - Добавить `provider: Literal["tei","local","jina","giga","bgem3"] = Field(default="tei")`
  - Добавить `tei_base_url: str = Field(default="http://localhost:8080")`
  - Добавить `tei_client_batch: int = Field(default=32, description="TEI MAX_CLIENT_BATCH_SIZE cap")`
- [ ] **2.1.1.d** Verify import: `python -c "from src.pdf_framework.config.embedding import EmbeddingSettings; s=EmbeddingSettings(); assert s.model=='Qwen/Qwen3-Embedding-8B' and s.dimensions==4096; print('OK')"`
- [ ] **2.1.1.e** Verify env override still works: `EMBEDDING__MODEL=intfloat/multilingual-e5-large EMBEDDING__DIMENSIONS=1024 python -c "..."` → должно вернуть E5/1024 (legacy fallback)
- [ ] **2.1.1.f** Risk: если есть migration scripts которые делают `Settings()` без env override и ожидают E5 → они упадут. Mitigation: grep `EmbeddingSettings()` без kwargs в `src/`, `tests/`, `scripts/`

#### 2.1.2 `src/pdf_framework/config/vector_store.py:15` — vector store dim default

- [ ] **2.1.2.a** Read line 15 area
- [ ] **2.1.2.b** Edit `dimensions: int = Field(default=1024)` → `default=4096`
- [ ] **2.1.2.c** Verify import test (тот же паттерн что 2.1.1.d, для VectorStoreSettings)
- [ ] **2.1.2.d** Risk: если `qdrant_client.create_collection()` где-то использует `Settings().dimensions` без override — будет создавать новые коллекции 4096d. Это **желаемое** поведение, но осторожно если кто-то ожидает 1024
- [ ] **2.1.2.e** Cross-check: `grep -n "VectorStoreSettings()" src/` — ни одно место не должно полагаться на 1024 hardcoded

#### 2.1.3 `src/pdf_framework/evaluation/autorag.py:33`

- [ ] **2.1.3.a** Read line 33 (probably `embedding_model: str = "intfloat/multilingual-e5-large"`)
- [ ] **2.1.3.b** Edit → `"Qwen/Qwen3-Embedding-8B"` (с комментарием `# Phase 8 default`)
- [ ] **2.1.3.c** Audit: AutoRAG eval datasets — построены под E5 1024d коллекции, проверить что после миграции их Qdrant collection (если есть отдельная) тоже на 4096d или recreate
- [ ] **2.1.3.d** Verify: `pytest tests/evaluation/test_autorag.py` (если есть) проходит, либо smoke run `python -m src.cli.main autorag --dry-run`

#### 2.1.4 `src/pdf_framework/processing/image_processor.py:276`

- [ ] **2.1.4.a** Read line 276 + 30 строк контекста
- [ ] **2.1.4.b** Понять — это default для image embedding (multimodal) или для text caption? Если **multimodal** — Qwen3-Embedding-8B **не подходит** (text-only). Тогда оставить E5 multilingual для caption (как fallback) ИЛИ перейти на CLIP/ColPali
- [ ] **2.1.4.c** **Решение:** если text caption — мигрировать на Qwen3; если image embed — оставить E5 (legacy text path) или перейти на ColPali (см. roadmap §32.6.x). Предварительно: text caption → Qwen3, image embedding (через CLIP) — отдельный issue
- [ ] **2.1.4.d** Edit с комментарием fixing context
- [ ] **2.1.4.e** Risk: если меняем embedding модель в multimodal pipeline — break backward compat. Mitigation: добавить `image_caption_embedding_model` отдельным полем

#### 2.1.5 `src/ui/pages/settings.py:105` — UI default settings

- [ ] **2.1.5.a** Read context — это default form values для Streamlit/Gradio settings page?
- [ ] **2.1.5.b** Edit `{"provider": "local", "model": "all-MiniLM-L6-v2"}` → `{"provider": "tei", "model": "Qwen/Qwen3-Embedding-8B"}`
- [ ] **2.1.5.c** UI valid values dropdown тоже обновить если есть
- [ ] **2.1.5.d** Smoke test UI: `streamlit run src/ui/app.py` → settings page показывает Qwen3 по умолчанию

#### 2.1.6 `src/bsl/semantic_search/mcp.py:713` — BSL hybrid search fallback embedder

- [ ] **2.1.6.a** Read line 713 area (~100 строк) — понять когда срабатывает fallback
- [ ] **2.1.6.b** Замена `TextEmbedding("intfloat/multilingual-e5-large")` (FastEmbed local model) на TEI HTTP вызов:
  - Импортировать `from src.framework_search.embedder import FrameworkTEIEmbedder`
  - Создать singleton/lazy `_tei_fallback_embedder = FrameworkTEIEmbedder()`
  - Заменить вызовы `TextEmbedding(...).embed([text])` → `_tei_fallback_embedder.embed_batch([text], is_query=is_query_context)`
- [ ] **2.1.6.c** Async wrapper: BSL MCP уже async; FrameworkTEIEmbedder синхронный — обернуть в `asyncio.to_thread()` или сделать `async embed_batch_async()`
- [ ] **2.1.6.d** Verify: `python -m src.bsl.semantic_search.mcp` (если есть main) или `pytest tests/bsl/test_mcp_hybrid_fallback.py`
- [ ] **2.1.6.e** Risk: TEI down → fallback не работает → нужен secondary fallback (token overlap или error). Уже есть pattern в `memory-first-hook.py` (Layer fallback)

#### 2.1.7 `src/pdf_framework/processing/splitters/semantic_splitter.py:50` — semantic splitter

- [ ] **2.1.7.a** Read context — `embedding_model = "all-MiniLM-L6-v2"` нужен для semantic chunk boundary detection (быстрая модель)
- [ ] **2.1.7.b** **Решение** (есть 3 варианта):
  - A) Qwen3 4096d через TEI — медленнее, но единая модель → consistency
  - B) Оставить MiniLM 384d **с явным комментарием** «lightweight chunk-boundary detector, not retrieval» → производительность важнее
  - C) Сделать model configurable через `SemanticSplitterSettings`, default Qwen3
- [ ] **2.1.7.c** Recommended: **Вариант C** (configurable, default Qwen3, с MiniLM как opt-in для производительности)
- [ ] **2.1.7.d** Edit: добавить `embedding_model: str = "Qwen/Qwen3-Embedding-8B"` в config класс, описание + переключение
- [ ] **2.1.7.e** Verify: `pytest tests/processing/test_semantic_splitter.py` зелёный с обоими settings

#### 2.1.99 Post-implementation acceptance

- [ ] **2.1.99.a** Smoke test no-env: `unset EMBEDDING__MODEL EMBEDDING__DIMENSIONS && python -c "from src.pdf_framework.config.embedding import EmbeddingSettings; s=EmbeddingSettings(); assert s.dimensions==4096; print(s.model)"` — должно вывести Qwen3
- [ ] **2.1.99.b** Full grep: `git grep -n "multilingual-e5-large\|all-MiniLM-L6-v2" src/` — все вхождения должны быть либо в:
  - `# legacy` / `# fallback` комментарии
  - В `embeddings/providers/local.py` (provider implementation, не default)
  - В `tests/` для legacy compat tests
  - В `pyproject.toml` deps (не модель)
- [ ] **2.1.99.c** CI assertion идея: добавить в `tests/test_config_invariants.py`:
  ```python
  def test_embedding_default_is_qwen3():
      from src.pdf_framework.config.embedding import EmbeddingSettings
      s = EmbeddingSettings()
      assert s.model == "Qwen/Qwen3-Embedding-8B", f"Got: {s.model}"
      assert s.dimensions == 4096, f"Got: {s.dimensions}"
  ```
- [ ] **2.1.99.d** Update CLAUDE.md строку «Qdrant коллекции (после Phase 8 + 9.1, 2026-04-30)» — добавить «config defaults aligned 2026-05-01 §2.1»
- [ ] **2.1.99.e** Commit message format: `fix(p0/2.1): align embedding defaults to Qwen3 4096d (post Phase 8)`

**Total effort:** 2-3 часа (вместо 30-60 мин estimate в первой версии — учли verification + risk mitigation).
**Rollback:** `git revert <commit>` восстановит E5 1024d defaults. Существующие 4096d коллекции продолжат работать (env overrides ясны), пользователи на дефолтах вернутся к E5.

### 2.2 P0 — JWT auth stub (security-critical)

> **✅ DONE 2026-05-01 (commits `b483e45c` + `ffacedc6`).** Real effort = **15 min** vs estimate 4-6 ч. Phase 12.3 уже создал JWT-инфраструктуру (`src/api/auth/jwt_handler.py`, `src/api/auth/dependencies.py`, `src/api/auth/rbac.py`) — оставалось только заменить локальные стабы в `tenants.py` на импорт `get_current_role`/`get_current_tenant` из готовых deps. Net delta: –17 строк. `AUTH__ENABLED=false` graceful dev-mode сохранён. 42/42 auth-теста зелёные. Code-verify subagent → PASS.

Multi-tenant isolation сейчас фиктивна:

```python
# src/api/routes/tenants.py:34
def get_current_tenant():
    # TODO: Parse JWT and extract tenant_id
    return "default"  # ← всегда default, нет изоляции

# src/api/routes/tenants.py:45
def require_admin():
    # TODO: Parse JWT and verify admin role
    return True  # ← все админы
```

#### 2.2.0 Pre-flight & dependency check

- [ ] **2.2.0.a** Audit existing auth context: `git grep -n "JWT\|auth\|Bearer" src/api/`. Понять есть ли уже `Authorization` header parsing где-то ещё (middleware, dependencies)
- [ ] **2.2.0.b** Check `pyproject.toml` deps — есть ли `python-jose`, `pyjwt`, `python-multipart`, `passlib`?
- [ ] **2.2.0.c** Check `.env.example` — есть ли `AUTH__JWT_SECRET`, `AUTH__JWT_ALGORITHM`, `AUTH__JWT_EXPIRATION_HOURS` (см. `framework-config` skill — должны быть)
- [ ] **2.2.0.d** Audit existing config: `src/pdf_framework/config/auth.py` (если есть) или `src/api/dependencies/auth.py`

#### 2.2.1 Выбор библиотеки JWT

- [ ] **2.2.1.a** **Decision:** `pyjwt` vs `python-jose`
  - `pyjwt`: simpler, lighter (~100 KB), maintained by community, более популярный в FastAPI mainstream
  - `python-jose[cryptography]`: больше алгоритмов (включая JWE), но heavier
- [ ] **2.2.1.b** **Recommendation:** `pyjwt` (если только не нужно encrypted JWT/JWE) — простота побеждает
- [ ] **2.2.1.c** Если `pyjwt` ещё не в `pyproject.toml`:
  ```toml
  pyjwt = "^2.9"
  ```
  Run: `pip install -e .` или `uv sync`
- [ ] **2.2.1.d** Verify: `python -c "import jwt; print(jwt.__version__)"`

#### 2.2.2 Создать `src/api/auth/jwt.py` (новый module)

- [ ] **2.2.2.a** Создать каталог `src/api/auth/` с `__init__.py`
- [ ] **2.2.2.b** Создать `src/api/auth/jwt.py`:
  ```python
  """JWT verification utilities for FastAPI multi-tenant isolation."""
  from __future__ import annotations
  import jwt
  from typing import TypedDict
  from fastapi import HTTPException, status
  from src.pdf_framework.config import get_settings  # или config.auth
  
  class JWTPayload(TypedDict, total=False):
      sub: str          # subject (user id)
      tenant_id: str    # tenant identifier
      roles: list[str]  # role list (e.g. ["admin", "viewer"])
      exp: int          # expiry epoch
      iat: int          # issued-at epoch
  
  def decode_token(token: str) -> JWTPayload:
      """Decode JWT and verify signature. Raises 401 on invalid."""
      settings = get_settings()
      secret = settings.auth.jwt_secret
      algorithm = settings.auth.jwt_algorithm or "HS256"
      try:
          payload = jwt.decode(token, secret, algorithms=[algorithm])
      except jwt.ExpiredSignatureError:
          raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
      except jwt.InvalidTokenError as e:
          raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}")
      return payload
  
  def extract_tenant_id(payload: JWTPayload) -> str:
      tenant_id = payload.get("tenant_id")
      if not tenant_id:
          raise HTTPException(status.HTTP_400_BAD_REQUEST, "tenant_id missing in JWT")
      return tenant_id
  
  def has_role(payload: JWTPayload, role: str) -> bool:
      roles = payload.get("roles", [])
      return role in roles
  ```
- [ ] **2.2.2.c** Создать pytest stub `tests/api/auth/test_jwt.py` с тестами decode_token (valid, expired, malformed, missing claim)

#### 2.2.3 FastAPI dependency `get_current_payload`

- [ ] **2.2.3.a** Создать `src/api/dependencies/auth.py` (или extend существующий):
  ```python
  from fastapi import Depends, Header, HTTPException, status
  from src.api.auth.jwt import decode_token, JWTPayload
  
  def get_current_payload(authorization: str = Header(None)) -> JWTPayload:
      if not authorization or not authorization.startswith("Bearer "):
          raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer token required")
      token = authorization.split(" ", 1)[1]
      return decode_token(token)
  ```
- [ ] **2.2.3.b** Pre-Phase 8 уже мог быть `src/api/dependencies/auth.py` — нужен audit before override

#### 2.2.4 Refactor `src/api/routes/tenants.py`

- [ ] **2.2.4.a** Read current `tenants.py` (понять route signatures, что они делают beyond auth stub)
- [ ] **2.2.4.b** Замена `get_current_tenant()`:
  ```python
  from fastapi import Depends
  from src.api.auth.jwt import extract_tenant_id, JWTPayload
  from src.api.dependencies.auth import get_current_payload
  
  def get_current_tenant(payload: JWTPayload = Depends(get_current_payload)) -> str:
      return extract_tenant_id(payload)
  ```
- [ ] **2.2.4.c** Замена `require_admin()`:
  ```python
  from src.api.auth.jwt import has_role, JWTPayload
  
  def require_admin(payload: JWTPayload = Depends(get_current_payload)) -> JWTPayload:
      if not has_role(payload, "admin"):
          raise HTTPException(status.HTTP_403_FORBIDDEN, "admin role required")
      return payload
  ```
- [ ] **2.2.4.d** Обновить ALL route handlers в `tenants.py` использующих эти 2 функции — теперь они работают как `Depends(...)`, не как plain calls

#### 2.2.5 Опциональный flag — disable auth для local dev

- [ ] **2.2.5.a** Добавить env var `AUTH__ENABLED=true|false` (default `false` — локальная разработка чтоб ничего не сломать сразу)
- [ ] **2.2.5.b** В dependency функциях: `if not settings.auth.enabled: return {"tenant_id": "default", "roles": ["admin"]}` (graceful degradation для dev)
- [ ] **2.2.5.c** В deployment skill отметить — production должен иметь `AUTH__ENABLED=true`

#### 2.2.6 Unit tests

- [ ] **2.2.6.a** `tests/api/auth/test_jwt.py`:
  - `test_decode_valid_token` — encode → decode round-trip
  - `test_decode_expired_raises_401`
  - `test_decode_invalid_signature_raises_401`
  - `test_decode_missing_tenant_id_raises_400`
  - `test_extract_tenant_id_success`
  - `test_has_role_admin_true`
  - `test_has_role_missing_false`
- [ ] **2.2.6.b** `tests/api/test_tenants.py`:
  - `test_get_current_tenant_returns_from_jwt` (FastAPI TestClient + valid Bearer header)
  - `test_get_current_tenant_no_header_401`
  - `test_get_current_tenant_invalid_token_401`
  - `test_require_admin_with_admin_role_passes`
  - `test_require_admin_without_admin_role_403`
  - `test_tenant_isolation` — endpoint `/data/{tenant_id}` доступен только если `tenant_id` из JWT совпадает (или admin override)
- [ ] **2.2.6.c** Conftest fixture `_make_token(tenant_id, roles, exp_offset)` — utility для tests

#### 2.2.7 Integration test (smoke API)

- [ ] **2.2.7.a** Запустить uvicorn локально: `uvicorn src.api.app:app --port 8000`
- [ ] **2.2.7.b** Invalid token: `curl -H "Authorization: Bearer invalid" http://localhost:8000/tenants/me` → 401
- [ ] **2.2.7.c** Valid tenant=A token, эндпоинт require admin → 403
- [ ] **2.2.7.d** Valid admin token, full access → 200
- [ ] **2.2.7.e** No header → 401

#### 2.2.8 CLI helper для генерации test/dev токенов

- [ ] **2.2.8.a** `python -m src.cli.main auth token --tenant=test --role=admin` → выводит JWT
- [ ] **2.2.8.b** Audit: возможно уже есть `pdf-framework auth token` команда в CLI (см. `framework-cli` skill упоминание `auth token`)

#### 2.2.9 Документация и SKILL обновление

- [ ] **2.2.9.a** Update `framework-api` skill — добавить пример с Authorization header + tenant_id flow
- [ ] **2.2.9.b** Update `deployment` skill — раздел JWT auth (production checklist `AUTH__ENABLED=true`, secret rotation)
- [ ] **2.2.9.c** Update CLAUDE.md если упоминает «auth stub» или multi-tenancy
- [ ] **2.2.9.d** Создать ADR `architecture-research/adr/009-jwt-auth-multitenancy.md` — context, decision (pyjwt + tenant_id claim + admin role), alternatives (auth0, keycloak)

#### 2.2.99 Post-implementation acceptance

- [ ] **2.2.99.a** `pytest tests/api/auth/ tests/api/test_tenants.py -v` — все green (минимум 12 tests)
- [ ] **2.2.99.b** Production smoke (если есть staging): запросы с tenant=A не видят данные tenant=B (например через `/search/?q=...` и убедиться что `Filter` использует тот tenant_id из JWT)
- [ ] **2.2.99.c** No-regression: запросы без `AUTH__ENABLED=true` (dev mode) работают как раньше
- [ ] **2.2.99.d** Security review checklist:
  - JWT secret не в коде (из env только)
  - Алгоритм HS256 не подменяется на none через header (pyjwt 2.x защищён, но verify)
  - Token expiration enforced (exp claim mandatory)
  - Refresh token flow (если нужен) — отдельный issue

**Total effort:** 4-6 часов (расширено vs первоначальные 2-3 ч из-за полноценного testing + ADR + SKILL updates).
**Risk:** breaking change для existing API consumers если `AUTH__ENABLED=true` по умолчанию.
**Mitigation:** default `AUTH__ENABLED=false`, документировать что production требует true.

### 2.3 P0 — Stale chapter 32 references in chapter 31

> **✅ DONE 2026-05-01 (commit `34c233f8`).** Все §32.X в chapter 31 (31.1/31.2/31.3/31.5) теперь markdown-ссылки на roadmap anchors. Попутно исправлен typo `§22 LoRA → §32.6.1 LoRA` в 31.1:127.

Главы [`31.1_Обзор.md:121-126`](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md) и [`31.2_Архитектура.md`](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.2_Архитектура.md) ссылаются на `§32.2 Reranker`, `§32.3 Hybrid sparse+dense`, `§32.4 Auto-populate`, `§32.5.2 Cleanup snapshots` — эти секции существуют только в **roadmap** (`260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md §32`), не в `docs/framework documentation/`.

- [ ] **2.3.1** Заменить все `§32.X` в chapter 31 на относительные ссылки на roadmap: `[Roadmap §32.2](../../roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md#322-phase-92--cross-encoder-reranker-next-big-win-4-8-часов)`
- [ ] **2.3.2** Опционально — создать `docs/framework documentation/32_FUTURE_RETRIEVAL_QUALITY/` с заголовком и pointer на roadmap §32 (если хочется keeping framework docs self-contained)

**Effort:** 30 мин. **Acceptance:** все ссылки в chapter 31 ведут на существующие файлы.

---

## 3. P1 — Documentation refresh (stale chapters → Phase 8 reality)

> **✅ DONE 2026-05-01 (6/6 запланированных chapters, commit `ab1e6e12`).** Effort: ~5 ч. Все главы §3.1-3.6 закрыты с migration-notes на chapter 31. **Out-of-scope chapters** со stale refs (09.5/10.x/13.4/19.x, ~5-10 файлов, ~1-2 ч) — оставлены для будущей P1 итерации.

**Цель:** обновить главы которые писались до Phase 8 (некоторые ещё до Phase 7) и упоминают deprecated модели/коллекции как production.

**Общий шаблон работы для каждой главы:**
1. Read full chapter
2. Grep deprecated terms: `nomic-embed-text|multilingual-e5-large|all-MiniLM|bsl_code_v[23]|experience_bank|visual_grounding|bsl_metadata`
3. Для каждого вхождения — определить: **deprecated** (заменить на Phase 8 default) или **legacy reference** (оставить с пометкой `(legacy)`)
4. Обновить inline + добавить «Migration note (2026-04-30)» в начало главы
5. Verify: `git grep -n` тот же шаблон не должен показать unmarked мест после edit
6. Cross-reference с chapter 31 (production guide) и roadmap 260426 §30 для context

### 3.1 P1 — Chapter 27.3 Memory_First_Hook ✅ DONE 2026-05-01 (`ab1e6e12`)

[`27.3_Memory_First_Hook.md:16,78,86-87`](../framework%20documentation/27_UNIFIED_MEMORY/27.3_Memory_First_Hook.md) описывает Layer 2 semantic search через Ollama nomic 768d. Phase 9.1 (commit `ac91c4b7`) заменил это на **TEI Qwen3 4096d**. Hook сейчас работает корректно, доки врут.

#### 3.1.0 Pre-flight
- [ ] **3.1.0.a** Read 27.3 целиком (не только указанные строки) — найти все упоминания эмбеддера
- [ ] **3.1.0.b** Cross-check с `.claude/hooks/memory-first-hook.py` — какие реально collections и timeouts (после §31 Phase 9.1)

#### 3.1.1 Inline edits
- [ ] **3.1.1.a** Line 12-16: «Ollama nomic-embed-text 768d» → «TEI Qwen3-Embedding-8B 4096d (Phase 9.1, commit ac91c4b7)»
- [ ] **3.1.1.b** Line 78: Layer 2 description — обновить таймауты (TEI cold ~600ms vs Ollama ~2s, см. §31.4)
- [ ] **3.1.1.c** Line 86-87: таблица collections — все три (skill_library, experience_embeddings, conversation_memory) **4096d**
- [ ] **3.1.1.d** Если есть упоминание `embed_query_ollama` — добавить note `(теперь alias на embed_query_tei после Phase 9.1)`

#### 3.1.2 Migration note в начало главы
- [ ] **3.1.2.a** Сразу после header добавить блок:
  ```markdown
  > **Migration note (2026-04-30, Phase 9.1):** Ollama nomic-embed-text 768d → TEI Qwen3 4096d.
  > До 2026-04-30 этот hook имел silent dim mismatch (hook embedding 768d vs collections 1024d) —
  > Qdrant возвращал 0 результатов, фолбэк на token overlap через learned_patterns маскировал
  > проблему. Подробности: roadmap 260426 §31, framework documentation 31.5.
  ```

#### 3.1.3 Cross-references
- [ ] **3.1.3.a** Link на `31.5 Миграция и итоги` (раздел Lessons learned #2)
- [ ] **3.1.3.b** Link на commit `ac91c4b7` (формат `git show ac91c4b7` или GitHub URL если remote есть)
- [ ] **3.1.3.c** Link на updated `embedding-models` skill

#### 3.1.4 Verify
- [ ] **3.1.4.a** `grep -n "nomic\|768d" "docs/framework documentation/27_UNIFIED_MEMORY/27.3_Memory_First_Hook.md"` — пусто или только в migration note контексте
- [ ] **3.1.4.b** Smoke test memory-first-hook: запустить `echo '{"prompt":"BSL процедура"}' | python .claude/hooks/memory-first-hook.py` — должны быть результаты с скилами

### 3.2 P1 — Chapter 04.8 Dual_Vector_Search ✅ DONE 2026-05-01 (`ab1e6e12`)

[`04.8_Dual_Vector_Search.md:23,55,74,90`](../framework%20documentation/04_ПОИСК/04.8_Dual_Vector_Search.md) упоминает `bsl_code_v4` как 768d nomic. Реально `bsl_code_v4` (research) и `bsl_code_v4_late` (production) — оба **4096d Qwen3**.

#### 3.2.0 Pre-flight
- [ ] **3.2.0.a** Read 04.8 целиком, понять что описывается dual-vector сценарий (`content` + `module_path` 2 named vectors) — был ли он реально реализован или это design doc?
- [ ] **3.2.0.b** Cross-check `src/bsl/semantic_search/services/hybrid_search.py` — есть ли dual-vector mode? Используется ли?

#### 3.2.1 Inline edits
- [ ] **3.2.1.a** Line 23: dim 768d → 4096d, model nomic → Qwen3-Embedding-8B
- [ ] **3.2.1.b** Line 55: тот же fix
- [ ] **3.2.1.c** Line 74: указать какая коллекция production: `bsl_code_v4_late` (Late Chunking pooling). `bsl_code_v4` — research baseline (std pooling)
- [ ] **3.2.1.d** Line 90: тот же fix

#### 3.2.2 Реальность dual-vector (важно)
- [ ] **3.2.2.a** Если в коде Phase 8 dual-vector НЕ реализован для current production коллекций (а они single-vector 4096d):
  - Добавить header «**Status:** Concept paper — dual-vector layout НЕ применён к Phase 8 production коллекциям. См. roadmap §32.3 для plan'а перехода на named vectors `dense + bm25`»
- [ ] **3.2.2.b** Если реализован — оставить как есть (просто dim fix)

#### 3.2.3 Cross-references
- [ ] **3.2.3.a** ADR-008 (Late Chunking decision)
- [ ] **3.2.3.b** Roadmap 260426 §21.10 (production switchover decision)

### 3.3 P1 — Chapter 28 BSL_SEMANTIC_SEARCH ✅ DONE 2026-05-01 (`ab1e6e12`)

#### 3.3.0 Pre-flight
- [ ] **3.3.0.a** Read 28.1, 28.2, 28.3, 28.4, 28.5 — full chapter audit (5 файлов)
- [ ] **3.3.0.b** Grep всех упоминаний deprecated терминов: `bsl_code_v2|nomic-embed-text|metadata_rrf|docs_rag|experience_bank`

#### 3.3.1 28.1 Обзор
- [ ] **3.3.1.a** Line 48: «Ollama + nomic-embed-text» → «TEI Qwen3-Embedding-8B (production, Phase 8). Ollama nomic 768d — legacy fallback»
- [ ] **3.3.1.b** Add migration note header (тот же шаблон что 27.3)

#### 3.3.2 28.4 Индексация
- [ ] **3.3.2.a** Line 78-80: таблица коллекций. Заменить:
  - `bsl_code_v2` (dropped 2026-04-30) → удалить из таблицы или отметить strikethrough
  - `metadata_rrf` (несуществующая) → удалить
  - `docs_rag` (несуществующая) → удалить
  - Добавить `bsl_code_v4_late` (production) с реальными counts (24 455 pts × 4096d)
- [ ] **3.3.2.b** Reindex command: обновить под `python scripts/reindex_bsl_qwen3.py --pooling-mode late-chunking --embedder qwen3-st --collection bsl_code_v4_late ...`
- [ ] **3.3.2.c** Cross-link на framework docs chapter 31.3 (operating procedures)

#### 3.3.3 28.2-28.5 audit
- [ ] **3.3.3.a** Прочитать оставшиеся 3 файла, найти deprecated terms (если есть) — применить тот же fix pattern

### 3.4 P1 — Chapter 29 XSKILL_CONTINUOUS_LEARNING ✅ DONE 2026-05-01 (`ab1e6e12`)

#### 3.4.0 Pre-flight
- [ ] **3.4.0.a** Read 29.1-29.7 (7 файлов)
- [ ] **3.4.0.b** Понять статус: XSkill — в production или experimental? Memory hooks Phase 9.1 alignment — затрагивают XSkill?

#### 3.4.1 29.1 Обзор
- [ ] **3.4.1.a** Line 29: `experience_embeddings (768d, nomic)` → 4096d Qwen3 (Phase 9.1)
- [ ] **3.4.1.b** Line 88-90: пометить `visual_grounding` как **DROPPED 2026-04-30** (см. roadmap §32.5.1)
- [ ] **3.4.1.c** Migration note header

#### 3.4.2 29.4 Retrieval_и_Scoring
- [ ] **3.4.2.a** Line 9-11: Source-таблица — все 768d nomic заменить на 4096d Qwen3
- [ ] **3.4.2.b** Удалить `visual_grounding` из таблицы (или strikethrough)
- [ ] **3.4.2.c** Обновить `experience_embeddings` row: 0 pts × 4096d (auto-populate ready, см. roadmap §32.4)

#### 3.4.3 29.6 Visual_Grounding (DROPPED status)
- [ ] **3.4.3.a** Добавить header сразу после `# 29.6 ...`:
  ```markdown
  > **⚠️ DROPPED 2026-04-30 (Phase 8 §32.5.1):** коллекция `visual_grounding`
  > (5 pts × 768d nomic) удалена из Qdrant. Snapshot 2026-04-30-19-15-16
  > сохранён в `docker_qdrant_snapshots` volume для возможного rollback.
  >
  > Visual retrieval остаётся **future work** — см. roadmap §32.6 (Path D
  > GigaEmbeddings) или ColPali multi-vector. Текущая глава описывает
  > deprecated дизайн.
  ```
- [ ] **3.4.3.b** Inline body можно оставить как историю design'а

#### 3.4.4 29.2-29.3, 29.5, 29.7 audit
- [ ] **3.4.4.a** Прочитать остальные файлы, применить тот же fix pattern

### 3.5 P1 — Chapter 01.3 Технологический_стек ✅ DONE 2026-05-01 (`ab1e6e12`)

[`01.3_Технологический_стек.md:11,26`](../framework%20documentation/01_ОБЗОР/01.3_Технологический_стек.md) — E5 1024d перечислена как default embedding. После Phase 8 — **Qwen3-Embedding-8B 4096d через TEI**.

#### 3.5.0 Pre-flight
- [ ] **3.5.0.a** Read 01.3 целиком — это таблица стека, нужно держать актуальной

#### 3.5.1 Обновить embedding-таблицу
- [ ] **3.5.1.a** Заменить current default `multilingual-e5-large` 1024d → `Qwen3-Embedding-8B` 4096d
- [ ] **3.5.1.b** Перенести E5, Jina, Giga, BGE, MiniLM в раздел «Legacy / alternative providers»
- [ ] **3.5.1.c** Добавить раздел «Backend» с TEI Docker (image `ghcr.io/huggingface/text-embeddings-inference:1.7.2`)
- [ ] **3.5.1.d** Cross-link на framework docs chapter 31.2 (architecture)

#### 3.5.2 Update Qdrant collections section
- [ ] **3.5.2.a** Если есть таблица «Active Qdrant collections» в 01.3 — обновить под Phase 8 + 9.1 snapshot (10 коллекций × 4096d, 80 908 pts)
- [ ] **3.5.2.b** Cross-link на 31.1 / 31.2

### 3.6 P1 — Chapter 26 LAZY_MCP отсутствует в TOC ✅ DONE 2026-05-01 (`ab1e6e12`)

Папка `docs/framework documentation/26_LAZY_MCP/` существует с 6 файлами, но `00_СОДЕРЖАНИЕ.md` её **не упоминает**. Структурный navigation gap.

#### 3.6.0 Audit
- [ ] **3.6.0.a** `ls "docs/framework documentation/26_LAZY_MCP/"` — точный список 6 файлов
- [ ] **3.6.0.b** Read first файл (`26.1_Обзор.md` или first из listing) для извлечения topic summary
- [ ] **3.6.0.c** Verify почему 26 пропущен — есть ли вообще ссылка hidden где-то?

#### 3.6.1 Добавить раздел в 00_СОДЕРЖАНИЕ.md
- [ ] **3.6.1.a** Найти место между `### [25. ...]` и `### [27. UNIFIED_MEMORY]` — вставить раздел 26
- [ ] **3.6.1.b** Формат:
  ```markdown
  ### [26. LAZY_MCP](26_LAZY_MCP/) — Lazy MCP loading система
  - [26.1 Обзор](26_LAZY_MCP/26.1_Обзор.md) — ...
  - [26.2 ...](26_LAZY_MCP/26.2_....md) — ...
  ... (все 6 файлов)
  ```
- [ ] **3.6.1.c** Description per file — извлечь из header каждого файла или first-line

#### 3.6.2 Quick links
- [ ] **3.6.2.a** В bottom section `## Быстрые ссылки` добавить:
  ```markdown
  | Lazy MCP — on-demand загрузка серверов | [26.1 Обзор LAZY_MCP](26_LAZY_MCP/26.1_Обзор.md) |
  ```

#### 3.6.3 Verify
- [ ] **3.6.3.a** `grep "26_LAZY_MCP" "docs/framework documentation/00_СОДЕРЖАНИЕ.md"` — должно показать минимум 2 occurrences (раздел + быстрая ссылка)
- [ ] **3.6.3.b** Markdown links validation (links resolve to existing files)

### 3.99 P1 общий verification

- [ ] **3.99.a** Final grep: `git grep -n "nomic-embed-text\|multilingual-e5-large\|all-MiniLM" "docs/framework documentation/"` — все вхождения должны иметь explicit `(legacy)` / migration note context
- [ ] **3.99.b** `git grep -n "bsl_code_v2\|bsl_code_v3\|experience_bank\|bsl_metadata\|visual_grounding" "docs/framework documentation/"` — пусто или strikethrough/historical
- [ ] **3.99.c** Markdown link validator: `find "docs/framework documentation/" -name "*.md" -exec grep -h '](' {} \;` extract paths, verify exist

**Effort на §3 в сумме:** 4-6 часов (расширено vs первоначальные 3-4 ч на полноценный grep + cross-references + migration notes).
**Risk:** низкий — pure text edits, не затрагивает код.
**Rollback:** `git revert <commits>` для каждой главы по отдельности.

---

## 4. P2 — Half-implemented features → IMPLEMENT (НЕ delete)

**Решение пользователя 2026-04-30:** все 4 stub'а **РЕАЛИЗОВЫВАЕМ**, не удаляем. Цель — превратить заявленный функционал в работающий, чтобы API/MCP не вводил в заблуждение.

### 4.1 P2 — `bsl_similar()` MCP tool — реализация vector similarity search

[`src/bsl/semantic_search/mcp.py:206-227`](../../src/bsl/semantic_search/mcp.py) — tool заявлен, возвращает «в разработке».

#### 4.1.0 Pre-flight & design
- [ ] **4.1.0.a** Read current stub (lines 206-227): какие args принимает (chunk_id? name? path?), какой return shape ожидается
- [ ] **4.1.0.b** Audit existing similarity search в `src/bsl/semantic_search/services/search.py` — есть ли base method `search_similar(vector, ...)` или нужно writeимплементировать заново
- [ ] **4.1.0.c** Decide input contract:
  - **Option A**: `chunk_id` (UUID5 строка) — fetch payload из Qdrant → re-use existing vector → search top-k
  - **Option B**: `name` (имя процедуры) + `module_path` (опц.) — embedded fresh, search top-k
  - **Recommendation: A** (cheaper — no embed call, использует pre-computed)

#### 4.1.1 Implementation
- [ ] **4.1.1.a** Создать helper в `src/bsl/semantic_search/services/search.py`:
  ```python
  async def find_similar(self, chunk_id: str, k: int = 5, exclude_self: bool = True) -> list[dict]:
      """Get embedding for chunk_id, search k+1 nearest, exclude self if exclude_self=True."""
      # 1. Retrieve point by chunk_id (UUID5)
      points = await self.client.retrieve(
          collection_name="bsl_code_v4_late",
          ids=[chunk_id],
          with_vectors=True,
      )
      if not points:
          return []
      query_vec = points[0].vector
      # 2. Search nearest (k+1 if exclude_self)
      limit = k + 1 if exclude_self else k
      results = await self.client.query_points(
          collection_name="bsl_code_v4_late",
          query=query_vec, limit=limit, with_payload=True,
      )
      # 3. Filter out self
      filtered = [
          {"chunk_id": p.id, "score": p.score, "payload": p.payload}
          for p in results.points if not (exclude_self and p.id == chunk_id)
      ][:k]
      return filtered
  ```
- [ ] **4.1.1.b** Обернуть в MCP tool `bsl_similar` (заменить stub в mcp.py:206-227):
  ```python
  @mcp.tool()
  async def bsl_similar(chunk_id: str, k: int = 5) -> dict:
      """Find k most similar BSL chunks to the given chunk_id (vector similarity search)."""
      service = get_bsl_search_service()
      results = await service.find_similar(chunk_id, k=k, exclude_self=True)
      return {"results": results, "queried_chunk_id": chunk_id, "count": len(results)}
  ```
- [ ] **4.1.1.c** Добавить параметр `path_filter: str | None = None` (опц. фильтр по `module_path` через `MatchText`)
- [ ] **4.1.1.d** Update tool registration: убрать «(в разработке)» из description

#### 4.1.2 Tests
- [ ] **4.1.2.a** `tests/bsl/test_mcp_similar.py`:
  - `test_bsl_similar_returns_top_k` — берём известный chunk_id, ожидаем k результатов
  - `test_bsl_similar_excludes_self` — собственный chunk_id не в результате
  - `test_bsl_similar_invalid_id_returns_empty` — несуществующий UUID → `[]`
  - `test_bsl_similar_with_path_filter` — фильтр по module_path работает
- [ ] **4.1.2.b** Mock Qdrant client через monkeypatch (Qdrant retrieve + query_points)

#### 4.1.3 Документация
- [ ] **4.1.3.a** Update `bsl-development` skill — добавить пример вызова `mcp__bsl-semantic-search__bsl_similar(chunk_id="...")`
- [ ] **4.1.3.b** Update framework docs chapter 28 (BSL semantic search) — описать новый tool в 28.3 (Инструменты)

#### 4.1.4 Verify
- [ ] **4.1.4.a** `pytest tests/bsl/test_mcp_similar.py -v` зелёный
- [ ] **4.1.4.b** Live MCP test: запустить bsl-semantic-search MCP, вызвать `bsl_similar` через MCP client, получить top-5

**Effort:** 3-4 часа (включая tests + docs update).

### 4.2 P2 — SONAR analytics CLI — обёртка над JAR

[`src/bsl/sonar/cli.py:49`](../../src/bsl/sonar/cli.py) — все команды возвращают `TODO: Реальный анализ` stub. Также [`src/bsl/sonar/config_manager.py:39,46`](../../src/bsl/sonar/config_manager.py) — load/save config не реализованы.

#### 4.2.0 Pre-flight & design
- [ ] **4.2.0.a** Audit `tools/mcp-jars/` — найти `sonar-bsl-plugin.jar` или аналогичный (упомянут в CLAUDE.md строке 73)
- [ ] **4.2.0.b** Audit `tools/sonar-scanner-6.2.1.4610-windows-x64/` — это полноценный sonar-scanner CLI
- [ ] **4.2.0.c** Investigate workflow: SonarQube server (running container?) + sonar-scanner client + BSL-плагин
- [ ] **4.2.0.d** Decide scope:
  - **Option A**: SonarQube server + scanner integration (full workflow) — 2 дня
  - **Option B**: Wrapping sonar-scanner CLI subprocess + parsing JSON output — 1 день
  - **Recommendation: B** — pragmatic, без отдельного SonarQube сервера. Можно расширить до A позже

#### 4.2.1 config_manager.py — load/save
- [ ] **4.2.1.a** Path: `data/sonar_config.json` (под `data/` уже есть других configs)
- [ ] **4.2.1.b** Шаблон конфига:
  ```json
  {
    "sonar_scanner_path": "tools/sonar-scanner-6.2.1.4610-windows-x64/bin/sonar-scanner.bat",
    "sonar_host_url": "http://localhost:9000",
    "sonar_token": "",
    "project_key": "default",
    "sources_dir": "src/projects/configuration",
    "exclusions": ["**/*.bsl"]
  }
  ```
- [ ] **4.2.1.c** Implement `load_config() -> SonarConfig` (Pydantic model или dataclass) с graceful default если файл отсутствует
- [ ] **4.2.1.d** Implement `save_config(cfg: SonarConfig) -> None` — atomic write через `tempfile + os.replace`

#### 4.2.2 cli.py — основные команды
- [ ] **4.2.2.a** `sonar analyze --project <name>`:
  - Read config
  - Build sonar-scanner command: `<path> -Dsonar.projectKey=... -Dsonar.sources=... -Dsonar.host.url=...`
  - `subprocess.run(cmd, capture_output=True, check=True)`
  - Parse exit code + stdout
  - Return JSON `{"status": "success|fail", "issues_url": "...", "summary": "..."}`
- [ ] **4.2.2.b** `sonar config show` — pretty-print текущего config
- [ ] **4.2.2.c** `sonar config set <key> <value>` — atomic update + save
- [ ] **4.2.2.d** `sonar status` — `curl <host>/api/system/status` → распечатать
- [ ] **4.2.2.e** Заменить все `TODO: Реальный анализ` на actual subprocess вызовы

#### 4.2.3 Tests
- [ ] **4.2.3.a** `tests/bsl/sonar/test_config_manager.py` — load/save round-trip, defaults, atomic write
- [ ] **4.2.3.b** `tests/bsl/sonar/test_cli.py` — mock subprocess через `unittest.mock.patch`, verify cmd construction для analyze

#### 4.2.4 Documentation
- [ ] **4.2.4.a** Создать или обновить `docs/framework documentation/28_BSL_SEMANTIC_SEARCH/28.6_SonarQube.md` (новый файл) — описать полный workflow
- [ ] **4.2.4.b** Update `bsl-development` skill — добавить раздел SonarQube
- [ ] **4.2.4.c** Update CLAUDE.md строку 73 — отметить SonarQube CLI как реализованный

#### 4.2.5 Verify
- [ ] **4.2.5.a** `pytest tests/bsl/sonar/ -v` зелёный
- [ ] **4.2.5.b** Live test (если есть SonarQube server): `python -m src.bsl.sonar.cli analyze --project test` → выполняется без exception
- [ ] **4.2.5.c** Без SonarQube server: `python -m src.bsl.sonar.cli config show` всё равно работает (config-only commands)

**Effort:** 1-1.5 дня (8-12 часов).

### 4.3 P2 — RAPTOR tree traversal — paper-style deep search

[`src/pdf_framework/search/strategies/raptor_search.py:163`](../../src/pdf_framework/search/strategies/raptor_search.py) — TODO: implement tree traversal. Сейчас работает только collapsed mode.

#### 4.3.0 Pre-flight
- [ ] **4.3.0.a** Read raptor_search.py целиком — понять текущую структуру collapsed mode
- [ ] **4.3.0.b** Read RAPTOR paper [arXiv:2401.18059](https://arxiv.org/abs/2401.18059) — раздел "Tree-traversal querying" (vs Collapsed-tree)
- [ ] **4.3.0.c** Audit: какие RAPTOR levels хранятся в Qdrant payload? (`level: 0` для leaf chunks, `level: 1+` для summaries)
- [ ] **4.3.0.d** Audit `src/pdf_framework/processing/raptor_clustering.py` — структура построения дерева

#### 4.3.1 Implementation: tree traversal
- [ ] **4.3.1.a** Алгоритм (per paper):
  ```
  1. Embed query
  2. Top-k search ТОЛЬКО на level=N (highest, например root summary level)
  3. Для каждого выбранного node — спуститься в его children (level=N-1)
  4. Top-k search в этом subset (Filter по parent_id)
  5. Повторить до level=0 (leaves)
  6. Возврат: trail nodes сверху-вниз + leaf chunks
  ```
- [ ] **4.3.1.b** Implement `_traverse_tree(query_vec, top_k_per_level=3)`:
  ```python
  async def _traverse_tree(self, query_vec, top_k_per_level=3):
      max_level = await self._get_max_level()  # query Qdrant for max(payload.level)
      current_parents = None
      trail = []
      for level in range(max_level, -1, -1):
          flt = build_filter(level=level, parent_ids=current_parents)
          results = await self.client.query_points(
              collection_name=self.collection,
              query=query_vec, limit=top_k_per_level,
              query_filter=flt, with_payload=True,
          )
          trail.append({"level": level, "nodes": results.points})
          current_parents = [p.id for p in results.points]
      return trail
  ```
- [ ] **4.3.1.c** Заменить TODO на line 163 — wire `_traverse_tree` в `search()` метод
- [ ] **4.3.1.d** Добавить config `RAPTOR__SEARCH_MODE=collapsed|traversal` (default `collapsed` для backward compat)

#### 4.3.2 Tests
- [ ] **4.3.2.a** `tests/search/strategies/test_raptor_traversal.py`:
  - `test_traverse_tree_descends_levels` — фиктивная коллекция с 3 levels, проверить trail включает all
  - `test_traverse_tree_filters_by_parent` — нет cross-branch leak
  - `test_search_mode_collapsed_default` — backward compat
  - `test_search_mode_traversal` — switch в traversal mode

#### 4.3.3 Документация
- [ ] **4.3.3.a** Update framework docs chapter 04.7 (Расширенный поиск) — описать оба режима, когда какой
- [ ] **4.3.3.b** Update `search-pipeline-debug` skill

#### 4.3.4 Verify
- [ ] **4.3.4.a** `pytest tests/search/strategies/test_raptor_traversal.py -v`
- [ ] **4.3.4.b** Eval: запустить `python -m src.cli.main eval --strategy raptor --raptor-mode traversal` vs `collapsed` на ragas dataset

**Effort:** 6-10 часов.

### 4.4 P2 — HyDE other methods — multi-query + zero-shot

[`src/pdf_framework/search/hyde.py:254`](../../src/pdf_framework/search/hyde.py) — TODO: Implement other methods. Сейчас один HyDE generation подход.

#### 4.4.0 Pre-flight
- [ ] **4.4.0.a** Read hyde.py — current single method (probably "generate hypothetical answer, embed, search")
- [ ] **4.4.0.b** HyDE paper [arXiv:2212.10496](https://arxiv.org/abs/2212.10496) — есть несколько техник:
  - Standard HyDE — generate hypothetical doc, embed, search
  - Multi-query HyDE — generate N hypothetical docs, embed each, average vector → search
  - Zero-shot — без training data
  - Few-shot — с in-context examples
- [ ] **4.4.0.c** Decide scope: minimum viable = multi-query HyDE (наибольший impact); zero-shot/few-shot — minor variants

#### 4.4.1 Implementation: Multi-query HyDE
- [ ] **4.4.1.a** Добавить method `multi_query_hyde(query: str, n: int = 5) -> Vector`:
  ```python
  async def multi_query_hyde(self, query: str, n: int = 5) -> list[float]:
      """Generate N hypothetical answers, embed each, average."""
      prompts = [
          f"Write a passage that answers: {query}\n(variation {i+1})"
          for i in range(n)
      ]
      hypothetical_docs = await asyncio.gather(*[
          self.llm.complete(p) for p in prompts
      ])
      embeddings = await self.embedder.embed_batch(hypothetical_docs, is_query=False)
      # Average + normalize
      import numpy as np
      avg = np.mean(np.array(embeddings), axis=0)
      avg = avg / np.linalg.norm(avg)
      return avg.tolist()
  ```
- [ ] **4.4.1.b** Wire в search pipeline через config `HYDE__METHOD=standard|multi_query` (default `standard`)
- [ ] **4.4.1.c** Заменить TODO на line 254

#### 4.4.2 Implementation: Zero-shot HyDE
- [ ] **4.4.2.a** Variant where prompt explicitly says «without examples, just based on what you know» — для cases когда in-context examples не предоставлены
- [ ] **4.4.2.b** Сделать config `HYDE__INSTRUCTION_TYPE=default|zero_shot|few_shot`

#### 4.4.3 Tests
- [ ] **4.4.3.a** `tests/search/test_hyde.py`:
  - `test_standard_hyde` — backward compat
  - `test_multi_query_hyde_generates_n_docs` (mock LLM)
  - `test_multi_query_hyde_returns_normalized_vector`
  - `test_zero_shot_hyde_uses_correct_prompt`

#### 4.4.4 Документация
- [ ] **4.4.4.a** Update framework docs chapter 04.7 — все 3 HyDE варианта
- [ ] **4.4.4.b** Update `search-pipeline-debug` skill

#### 4.4.5 Verify
- [ ] **4.4.5.a** `pytest tests/search/test_hyde.py -v`
- [ ] **4.4.5.b** Eval сравнение standard vs multi_query на golden-set

**Effort:** 4-6 часов.

### 4.99 P2 общий verification

- [ ] **4.99.a** Все 4 stub'а заменены на работающую логику
- [ ] **4.99.b** `git grep "TODO.*реализ\|TODO.*Implement" src/bsl/semantic_search/mcp.py src/bsl/sonar/ src/pdf_framework/search/strategies/raptor_search.py src/pdf_framework/search/hyde.py` — пусто
- [ ] **4.99.c** Total tests added: ~25-30 (4 features × 5-8 tests each)
- [ ] **4.99.d** Production smoke: каждая фича вызывается через MCP / CLI / API без exception

**Effort на §4 в сумме:** 21-32 часа (vs первоначальные 4-12 — учли полноценную реализацию + tests + docs).
**Total:** 3-4 рабочих дня.

---

## 5. P3 — Code-without-docs gaps (новые главы документации)

**Цель:** покрыть документацией модули которые есть в коде но не упомянуты (или минимально упомянуты) ни в одной главе. **Решение пользователя 2026-04-30:** не удаляем код, а описываем — каждый модуль получает свою главу или раздел в существующих.

**Общий шаблон для каждого модуля:**
1. Audit: read `__init__.py` + main classes/functions in module
2. Identify exports (public API)
3. Find usage sites (`git grep "from src.pdf_framework.X import"` или `import src.X`)
4. Read existing docs / SKILL.md mentions
5. Decide structure: новая глава vs раздел в existing chapter
6. Write content: Назначение / Архитектура / API / Конфигурация / Примеры
7. Cross-references на роадмап / ADR / другие главы

### 5.1 P3 — `src/pdf_framework/guardrails/` — security and content safety

Не упомянут в documentation. Безопасность критична — PII detection, prompt injection, query length limits.

#### 5.1.0 Pre-flight audit
- [ ] **5.1.0.a** `ls src/pdf_framework/guardrails/` — список файлов
- [ ] **5.1.0.b** Read `__init__.py` — какие public classes
- [ ] **5.1.0.c** Read each major file — функционал
- [ ] **5.1.0.d** Audit usage: `git grep "from src.pdf_framework.guardrails"` — где используется
- [ ] **5.1.0.e** Audit `framework-config` skill — есть ли `GUARDRAILS__*` env vars (из памяти есть `GUARDRAILS__PII_MODE`, `GUARDRAILS__INJECTION_MODE`, `GUARDRAILS__INJECTION_THRESHOLD`, `GUARDRAILS__MAX_QUERY_LENGTH`, `GUARDRAILS__MAX_FILE_SIZE_BYTES` — проверить)

#### 5.1.1 Создать главу `docs/framework documentation/33_GUARDRAILS/`
- [ ] **5.1.1.a** Создать `33_GUARDRAILS/33.1_Обзор.md`:
  - Назначение: input validation, PII protection, injection defense
  - Архитектура: где в pipeline применяется guardrail (pre-search, pre-LLM, post-LLM)
  - Список detector'ов (PII patterns, injection signatures)
  - Connection с config `GUARDRAILS__*`
- [ ] **5.1.1.b** `33.2_PII_Detection.md`:
  - Modes: `detect|redact|block`
  - Patterns: email, phone, SSN, credit card, etc. (что реально матчится)
  - Examples: input/output для каждого mode
- [ ] **5.1.1.c** `33.3_Injection_Defense.md`:
  - Threshold tuning (`GUARDRAILS__INJECTION_THRESHOLD=0.7`)
  - Modes: `log|warn|block`
  - False-positive examples
- [ ] **5.1.1.d** `33.4_Limits.md`:
  - Max query length, max file size, max chunks per request
  - Расширение через config

#### 5.1.2 Регистрация в TOC
- [ ] **5.1.2.a** Добавить раздел `### [33. GUARDRAILS]` в `00_СОДЕРЖАНИЕ.md`
- [ ] **5.1.2.b** Bottom-section quick links

#### 5.1.3 Update enforcer mapping
- [ ] **5.1.3.a** В `.claude/hooks/docs-change-enforcer.py` `CODE_TO_DOMAIN`:
  ```python
  ("src/pdf_framework/guardrails/", "33_GUARDRAILS", "framework-troubleshooting"),
  ```
  (или создать отдельный skill `guardrails`)

**Effort:** 3-4 часа.

### 5.2 P3 — `src/pdf_framework/knowledge_base/` — KB management

Не упомянут в docs. Что это за подсистема — нужна экспозиция.

#### 5.2.0 Pre-flight investigation
- [ ] **5.2.0.a** `ls src/pdf_framework/knowledge_base/` — список файлов
- [ ] **5.2.0.b** Read `__init__.py` + main classes — какова функция модуля
- [ ] **5.2.0.c** Audit usage: `git grep "knowledge_base"` в `src/`
- [ ] **5.2.0.d** Decide:
  - Если **active feature** (used by API/CLI): создать отдельную главу
  - Если **internal helper** для других модулей: интегрировать в parent chapter
  - Если **orphan** (не импортируется нигде): mark `# DEPRECATED: see X` в коде, но НЕ удалять (per user)

#### 5.2.1 Создать главу или раздел
- [ ] **5.2.1.a** Если новая глава — `34_KNOWLEDGE_BASE/34.1_Обзор.md`
  - Назначение: что отличает KB от Vector Store / Graph Store
  - Архитектура: storage backend, схема
  - API: как добавить/удалить/искать
- [ ] **5.2.1.b** Если раздел: добавить в chapter 03 (Индексация) как `03.6_Knowledge_Base.md`

#### 5.2.2 Регистрация
- [ ] **5.2.2.a** `00_СОДЕРЖАНИЕ.md` обновить
- [ ] **5.2.2.b** Update enforcer mapping

**Effort:** 2-3 часа (зависит от scope active vs orphan).

### 5.3 P3 — `src/pdf_framework/multitenancy/` — расширение chapter 09

Описан в chapter 09.1 (admin), но детали реализации (per-tenant collections, JWT integration) отсутствуют.

#### 5.3.0 Pre-flight
- [ ] **5.3.0.a** Read `src/pdf_framework/multitenancy/` — `tenant_manager.py`, `__init__.py` etc.
- [ ] **5.3.0.b** Read existing chapter 09.1 — что уже описано про мультитенантность
- [ ] **5.3.0.c** Cross-check с §2.2 JWT auth — после реализации `get_current_tenant()` нужна детальная implementation документация

#### 5.3.1 Расширить chapter 09
- [ ] **5.3.1.a** Создать `09_АДМИНИСТРИРОВАНИЕ/09.X_Multi_Tenancy.md` (например 09.10):
  - Архитектура: per-tenant collections in Qdrant (`<tenant>_pdf_documents`)
  - Per-tenant Graph isolation
  - Cache key includes tenant_id
  - JWT integration (после §2.2)
  - CLI: `pdf-framework tenant create|list|delete`
  - API: `X-Tenant-ID` header или JWT claim
- [ ] **5.3.1.b** Workflow examples:
  - Create new tenant
  - Index document under tenant
  - Search isolated по tenant
  - Migrate single-tenant → multi-tenant

#### 5.3.2 Update TOC + enforcer
- [ ] **5.3.2.a** Добавить ссылку 09.X в 00_СОДЕРЖАНИЕ.md
- [ ] **5.3.2.b** Mapping `src/pdf_framework/multitenancy/` → `09_АДМИНИСТРИРОВАНИЕ` уже есть, без изменений

**Effort:** 2-3 часа.

### 5.4 P3 — `src/extensions/` — minimal coverage

2 mentions в docs — что это?

#### 5.4.0 Pre-flight investigation
- [ ] **5.4.0.a** `ls src/extensions/` — листинг
- [ ] **5.4.0.b** Read `__init__.py`
- [ ] **5.4.0.c** Read main файлы — определить scope
- [ ] **5.4.0.d** `git grep "src.extensions"` — usage

#### 5.4.1 Документировать (НЕ удалять)
- [ ] **5.4.1.a** Если plugin/extension API: создать главу `35_EXTENSIONS/`
  - Что такое extension в этом фреймворке
  - Как создать свой extension
  - Lifecycle (load, init, hooks)
  - Examples из existing
- [ ] **5.4.1.b** Если utility helpers: добавить раздел в chapter 09 или 10

#### 5.4.2 TOC + enforcer mapping update

**Effort:** 2-3 часа.

### 5.5 P3 — `src/workers/` — ARQ tasks examples

ARQ async workers. Описаны в chapter 09 deployment (`09_АДМИНИСТРИРОВАНИЕ`), но без детальных примеров tasks (indexing/graph/eval).

#### 5.5.0 Pre-flight
- [ ] **5.5.0.a** Read `src/workers/` — `worker.py`, `tasks/indexing.py`, `tasks/graph.py`, `tasks/evaluation.py`
- [ ] **5.5.0.b** Audit existing chapter 09 — какой раздел упоминает workers (наверняка 09.X Async Workers / ARQ Queue)

#### 5.5.1 Расширить chapter 09
- [ ] **5.5.1.a** В существующем разделе ARQ Queue — добавить подразделы для каждой task'и:
  - `index_document(file_path, options)` — пример вызова, signatures, retry policy
  - `rebuild_bm25(collection)` — bulk re-tokenize
  - `rebuild_embeddings(collection)` — full re-embed (как `reembed_collection.py` но через очередь)
  - `rebuild_graph(filters)` — entity + relations rebuild
  - `run_evaluation(dataset, strategy)` — RAGAS eval async
- [ ] **5.5.1.b** Worker startup commands + monitoring:
  ```bash
  arq src.workers.worker.WorkerSettings
  python -m arq.cli src.workers.worker.WorkerSettings --check
  ```
- [ ] **5.5.1.c** Failure handling, retry semantics, progress tracking (Redis hash key per task_id)

#### 5.5.2 Cross-references
- [ ] **5.5.2.a** Update `deployment` skill — раздел Async Workers
- [ ] **5.5.2.b** Update CLI documentation — `pdf-framework worker` command

**Effort:** 2-3 часа.

### 5.99 P3 общий verification

- [ ] **5.99.a** Все 5 модулей имеют ≥ 1 параграф документации (не stub) в существующей или новой главе
- [ ] **5.99.b** `00_СОДЕРЖАНИЕ.md` показывает все главы (33-35 если новые) + быстрые ссылки
- [ ] **5.99.c** `.claude/hooks/docs-change-enforcer.py` `CODE_TO_DOMAIN` mapping covers все 5 модулей
- [ ] **5.99.d** Live test: модифицировать файл в `src/pdf_framework/guardrails/` — Stop hook не выдаёт UNMAPPED warning

**Effort на §5 в сумме:** 11-16 часов (vs первоначальные 6-10 — учли pre-flight + cross-references + enforcer mapping).

---

## 6. P4 — Long-term + maintenance

**Решение пользователя 2026-04-30:** **НЕ удалять**. Все «orphan/unused» elements нужно либо wire'нуть, либо явно отметить как `# Deprecated, kept for backward compat` с migration note.

### 6.1 P4 — Unused config fields — wire'нуть, не удалять

#### 6.1.1 `classifier_cache_enabled` — wire в Adaptive RAG
- [ ] **6.1.1.a** Read [`src/pdf_framework/config/features.py:43`](../../src/pdf_framework/config/features.py) — definition
- [ ] **6.1.1.b** `git grep "classifier_cache_enabled" src/` — kosher confirm, что nikem не используется
- [ ] **6.1.1.c** Find candidates: `src/pdf_framework/agents/adaptive*.py` — adaptive RAG classifier (route classification of query type — простой/средний/сложный/тематический)
- [ ] **6.1.1.d** Wire: добавить кэширование результатов классификации (по hash query) если `classifier_cache_enabled=True`. TTL из existing `classifier_cache_ttl` или ввести
- [ ] **6.1.1.e** Implementation:
  ```python
  # В adaptive classifier
  if settings.features.classifier_cache_enabled:
      cache_key = hashlib.sha1(query.encode()).hexdigest()[:16]
      cached = self._cache.get(cache_key)
      if cached:
          return cached
  ```
- [ ] **6.1.1.f** Tests: classifier с cache_enabled=True кэширует, с False — нет
- [ ] **6.1.1.g** Documentation: update chapter 05.2 (Adaptive RAG) — описать caching

#### 6.1.2 `route_*_strategy` overrides — wire в routing logic
- [ ] **6.1.2.a** Read [`src/pdf_framework/config/features.py:53-56`](../../src/pdf_framework/config/features.py) — `route_simple_strategy`, `route_moderate_strategy`, `route_complex_strategy`, `route_thematic_strategy`
- [ ] **6.1.2.b** `git grep "route_simple_strategy\|route_moderate_strategy" src/` — confirm никем не используется
- [ ] **6.1.2.c** Find router: `src/pdf_framework/agents/adaptive*.py` где complexity → strategy mapping. Сейчас наверняка hardcoded:
  ```python
  if complexity == "simple": strategy = "vector"
  elif complexity == "moderate": strategy = "hybrid"
  elif complexity == "complex": strategy = "graphrag_local"
  ```
- [ ] **6.1.2.d** Wire: заменить hardcoded на config:
  ```python
  strategy_map = {
      "simple": settings.features.route_simple_strategy,
      "moderate": settings.features.route_moderate_strategy,
      "complex": settings.features.route_complex_strategy,
      "thematic": settings.features.route_thematic_strategy,
  }
  strategy = strategy_map.get(complexity, "hybrid")
  ```
- [ ] **6.1.2.e** Tests: override через env `ADAPTIVE__ROUTE_SIMPLE_STRATEGY=bm25` → adaptive router uses `bm25` для simple queries
- [ ] **6.1.2.f** Documentation: chapter 05.2 — описать как override per-complexity strategy

#### 6.1.3 Verify — нет deprecated config fields без use
- [ ] **6.1.3.a** Скрипт `scripts/audit_unused_config.py`:
  ```python
  """Find Pydantic Settings fields that are defined but never read."""
  import ast
  # Walk src/pdf_framework/config/, collect field names
  # Walk src/, find usages (settings.X.field)
  # Diff: defined - used = unused
  ```
- [ ] **6.1.3.b** Run, expected output: ноль unused (после §6.1.1 + §6.1.2)

**Effort:** 4-6 часов.

### 6.2 P4 — Deprecated providers — keep + document как fallback

**Per user instruction: НЕ удалять.** Делаем явный switch + backward-compat поддержку.

#### 6.2.1 `src/pdf_framework/embeddings/providers/giga.py` — Russian SOTA option
- [ ] **6.2.1.a** Read provider class — какой API
- [ ] **6.2.1.b** Add module docstring header:
  ```python
  """GigaEmbeddings (ai-sage/Giga-Embeddings-instruct, 1024d) — Russian SOTA option.
  
  **Status (2026-04-30):** Path D alternative. Production использует Qwen3-Embedding-8B
  (Phase 8). Giga может быть лучше на чистом русском (ruMTEB 69.1), но не тестирован
  на code-content. Активируется через EMBEDDING__PROVIDER=giga.
  
  Trade-off vs Qwen3:
  - Меньше memory (1024d vs 4096d, 4× экономия)
  - Не тестирован на code-heavy queries (Qwen3 MTEB-Code 80.68)
  - Roadmap §32.6.2 — потенциальный A/B vs Qwen3+Late на 50q golden-set
  """
  ```
- [ ] **6.2.1.c** Verify provider usable: смок-test через `EMBEDDING__PROVIDER=giga python -c "..."`
- [ ] **6.2.1.d** Update `embedding-models` skill — добавить current status

#### 6.2.2 `src/pdf_framework/embeddings/providers/bgem3.py` — multilingual fallback
- [ ] **6.2.2.a** Read provider class
- [ ] **6.2.2.b** Add status docstring как у giga.py — pinned status
- [ ] **6.2.2.c** Document use case: multilingual content где Qwen3 неприменим

#### 6.2.3 Provider factory — verify all providers selectable
- [ ] **6.2.3.a** [`src/pdf_framework/embeddings/__init__.py`](../../src/pdf_framework/embeddings/__init__.py) — провайдер factory
- [ ] **6.2.3.b** Тест: switch через `EMBEDDING__PROVIDER=local|tei|giga|bgem3|jina` все возвращают валидный embedder без ошибки
- [ ] **6.2.3.c** Documentation: chapter 31.2 Архитектура — добавить раздел "Alternative providers" с usage scenarios

**Effort:** 2-3 часа.

### 6.3 P4 — Прочие TODO/FIXME — реализовать (per user instruction)

#### 6.3.1 `dspy_optimizer.py:105` — integrate FeedbackStore
- [ ] **6.3.1.a** Read [`src/pdf_framework/optimization/dspy_optimizer.py:105`](../../src/pdf_framework/optimization/dspy_optimizer.py) — TODO: integrate with FeedbackStore to auto-populate
- [ ] **6.3.1.b** Audit `src/pdf_framework/feedback/store.py` — какие методы доступны (positive_examples, get_stats)
- [ ] **6.3.1.c** Wire: при инициализации DSPyOptimizer — auto-load positive examples из FeedbackStore как `trainset`. Cap N=100 наисвежайших
- [ ] **6.3.1.d** Tests: моковый FeedbackStore с 5 examples → optimizer.trainset содержит их
- [ ] **6.3.1.e** Documentation: chapter 08 (Оценка качества) или skill `prompt-engineering` — описать integration

#### 6.3.2 `summary_index.py:280` — use actual embedding engine
- [ ] **6.3.2.a** Read [`src/pdf_framework/processing/summary_index.py:280`](../../src/pdf_framework/processing/summary_index.py) — TODO: Use actual embedding engine from components
- [ ] **6.3.2.b** Audit: сейчас наверняка hardcoded mock или None. Заменить на `components.embedding_engine` (DI pattern)
- [ ] **6.3.2.c** Wire через `Components` factory `src/api/dependencies/components.py`
- [ ] **6.3.2.d** Tests: summary_index получает real embedder и embed работает
- [ ] **6.3.2.e** Risk: если был mock → может изменить behavior. Smoke test summary index создание + search

#### 6.3.3 `synthetic.py:283` — load human questions from file
- [ ] **6.3.3.a** Read [`src/pdf_framework/evaluation/synthetic.py:283`](../../src/pdf_framework/evaluation/synthetic.py) — TODO: Load human questions from file
- [ ] **6.3.3.b** Спроектировать file format: JSONL `{"question": "...", "context": "...", "expected_chunks": [...]}`
- [ ] **6.3.3.c** Implement `load_human_questions(path: Path) -> list[Question]`
- [ ] **6.3.3.d** Mix human + synthetic в `EvalDataset` (какой ratio? `human_ratio: float = 0.3` config)
- [ ] **6.3.3.e** Tests: load JSONL с 3 questions → DataSet содержит их + синтетические
- [ ] **6.3.3.f** Documentation: chapter 08 + `evaluation-benchmark` skill

#### 6.3.4 `bsl/semantic_search/services/search.py:245` — LLM Re-ranking
- [ ] **6.3.4.a** Read [`src/bsl/semantic_search/services/search.py:245`](../../src/bsl/semantic_search/services/search.py) — TODO: LLM Re-ranking
- [ ] **6.3.4.b** **Связь с roadmap §32.2** — глобальный Phase 9.2 reranker. Decision:
  - **Option A:** Дождаться Phase 9.2 (cross-encoder BGE-reranker-v2-m3 для всего фреймворка) → unify все retrieval pipelines под одним reranker
  - **Option B:** Реализовать BSL-specific LLM reranker сейчас через Z.AI (LLM Rotation) — judge top-N через prompt
  - **Recommendation: A** (deferred wait для §32.2). Сейчас оставить TODO с pointer на §32.2 PoC
- [ ] **6.3.4.c** Update TODO comment:
  ```python
  # TODO (P4 §6.3.4): LLM Re-ranking. Wait for Phase 9.2 cross-encoder
  # (BGE-reranker-v2-m3) — see roadmap §32.2. Then unify через shared
  # reranker module instead of BSL-specific implementation.
  ```

**Effort:** 8-12 часов (4 TODO × 2-3 часа each).

### 6.99 P4 общий verification

- [ ] **6.99.a** Скрипт `scripts/audit_unused_config.py` возвращает 0 unused fields (§6.1)
- [ ] **6.99.b** Все providers (E5, MiniLM, Qwen3 TEI, Qwen3-st, Giga, BGE-M3, Jina) загружаются без ошибки через factory (§6.2)
- [ ] **6.99.c** `git grep -n "TODO" src/` — оставшиеся TODO явно помечены P-priority и связаны с roadmap section
- [ ] **6.99.d** No regression: smoke test full retrieval pipeline (BSL search, framework search, PDF search) после §6.x edits

**Effort на §6 в сумме:** 14-21 час (vs первоначальные «P4 maintenance» без detailed estimate — теперь явно).

---

## 7. Decision triggers — когда брать какой пункт

| Сигнал | Какой раздел решает |
|--------|---------------------|
| `python -m src.cli.main index` падает с dim mismatch | §2.1 P0 embedding defaults |
| Пользователь сообщает что виден чужой tenant | §2.2 P0 JWT auth |
| Пользователь видит broken link в chapter 31 | §2.3 P0 §32 refs |
| Новый разработчик читает chapter 27.3 и пытается ставить Ollama | §3.1 P1 chapter 27.3 update |
| Pull request трогает `bsl_similar()` или `sonar/cli.py` | §4.1 / §4.2 P2 decision |
| Audit security review | §5.1 P3 guardrails docs |
| Code review замечает unused config field | §6.1 P4 cleanup |

---

## 8. Эффективная стратегия исполнения

### 8.1 Один день (8 часов) можно закрыть

**P0 (~3 часа):** §2.1 + §2.2 + §2.3 — все 3 пункта critical
**P1 (~3 часа):** §3.1 + §3.2 + §3.6 — самые видимые user-facing chapters
**Buffer:** 2 часа на тесты + commits

### 8.2 Неделя (40 часов) — закрыть P0 + P1 + P2

**День 1:** P0 (3 часа) + remaining P1 chapters 28/29/01.3 (4 часа)
**День 2-3:** P2 decisions + half-implementation (8-12 часов)
**День 4-5:** P3 documentation (6-10 часов) + buffer/review

### 8.3 Можно закрыть incremental

- P0 §2.1 — 5 минут на файл, можно делать «между делом» при следующем правке config'а
- P3 documentation — открыть chapter, добавить параграф, commit

---

## 9. Acceptance — что считаем «закрытым»

| Раздел | Acceptance |
|--------|------------|
| §2.1 | `EMBEDDING__MODEL` default = Qwen3, smoke index без env vars даёт 4096d |
| §2.2 | Тест `pytest tests/api/test_tenants.py` зелёный, реальный JWT parsing |
| §2.3 | `grep "§32" docs/framework documentation/31_*` — все ссылки относительные на roadmap |
| §3.1-§3.5 | `grep -r "768d\|nomic-embed-text\|multilingual-e5-large" docs/framework documentation/{04,27,28,29,01.3}*` — пусто или с пометкой `(legacy)` |
| §3.6 | `grep "26_LAZY_MCP" docs/framework documentation/00_СОДЕРЖАНИЕ.md` — содержит раздел |
| §4.x | Либо реализовано (есть unit-tests), либо удалено из public API |
| §5.x | Каждый src/* модуль из списка имеет ≥ один параграф в documentation |
| §6.x | `pyproject.toml lint` чистый, no orphan config fields |

---

## 10. Lessons learned (применимы к этому roadmap)

Из roadmap 260426 §33 lessons learned релевантные сюда:

- **Lesson #1 «Все коллекции» = нужен прогресс-чекер.** Применимо: для §2.1 нужен smoke test что **все** имплементации embedding default'а синхронизированы — простой grep `multilingual-e5-large` в `src/`
- **Lesson #2 silent dim mismatch.** Уже найден в Phase 9.1, но в `src/` остаются hardcoded 1024d (см. §2.1.2). После закрытия §2.1 — добавить CI assertion `EMBEDDING__DIMENSIONS == 4096`
- **Lesson #6 backup verification.** Применимо: §2.2 JWT change — повлияет на existing tokens. Pre-flight: создать tenant с известным JWT, проверить что после fix он всё ещё работает (no breaking change на api consumers)

---

## Источники

- [Roadmap Phase 8](260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md) — production state context
- [Framework documentation chapter 31](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/) — текущий production guide
- Аудит run: 2026-04-30 вечер (2 параллельных Explore subagent'а)
- Файлы аудита приложены в commit message соответствующего PR

---

## 11. Implementation Execution Checklist (master plan)

**Цель:** unified плавно-исполняемый чеклист с decision points, smoke tests после каждого P-этапа, rollback procedures.

### 11.1 Pre-flight (один раз перед началом)

- [ ] **11.1.a** `git status --short` пустой (нет uncommitted changes)
- [ ] **11.1.b** Активная ветка фиксирована: `git rev-parse HEAD`
- [ ] **11.1.c** TEI Docker healthy: `docker ps --filter "name=pdf-rag-tei"` показывает Up + healthy
- [ ] **11.1.d** Qdrant healthy: `curl -s http://localhost:6333/collections | python -m json.tool` показывает 10 коллекций × 4096d
- [ ] **11.1.e** Backup snapshot всех коллекций (защита перед массовыми изменениями):
  ```bash
  for c in bsl_code_v4_late bsl_code_v4 framework_code_v1 pdf_documents wiki_pages_v1 graph_embeddings skill_library learned_patterns experience_embeddings conversation_memory; do
      curl -s -X POST "http://localhost:6333/collections/$c/snapshots"
  done
  ```
- [ ] **11.1.f** Test suite зелёный baseline: `pytest tests/ -x --tb=short` — count failures (для diff после)
- [ ] **11.1.g** CLAUDE.md имеет валидный snapshot Phase 8+9.1 (см. commit f9d38b52)

### 11.2 Order of execution (recommended)

```
Day 1 (P0, ~6 ч):
  ├─ §2.1 embedding defaults (2-3 ч)        ← critical, low risk
  ├─ §2.3 §32 refs in chapter 31 (30 мин)   ← trivial, no code
  └─ §2.2 JWT auth (4-6 ч)                   ← security-critical, full impl + tests

Day 2 (P1 docs refresh, ~5 ч):
  ├─ §3.6 chapter 26 LAZY_MCP в TOC (15 мин)  ← quick win
  ├─ §3.5 chapter 01.3 tech stack (30 мин)
  ├─ §3.1 chapter 27.3 memory hook (1 ч)
  ├─ §3.2 chapter 04.8 dual vector (1 ч)
  ├─ §3.3 chapter 28 BSL search (1 ч)
  └─ §3.4 chapter 29 XSKILL (1 ч)

Day 3-4 (P2 implementations, ~24 ч):
  ├─ §4.1 bsl_similar() MCP tool (3-4 ч)
  ├─ §4.4 HyDE multi-query (4-6 ч)
  ├─ §4.3 RAPTOR tree traversal (6-10 ч)
  └─ §4.2 SONAR CLI (8-12 ч)                 ← largest, может растянуться на день 4-5

Day 5-6 (P3 docs new chapters, ~12 ч):
  ├─ §5.5 ARQ workers (chapter 09 ext) (2-3 ч)
  ├─ §5.3 multitenancy (chapter 09 ext) (2-3 ч)
  ├─ §5.1 guardrails (new chapter 33) (3-4 ч)
  ├─ §5.4 extensions (?) (2-3 ч)
  └─ §5.2 knowledge_base (?) (2-3 ч)

Day 7 (P4 maintenance, ~16 ч):
  ├─ §6.1 wire unused config fields (4-6 ч)
  ├─ §6.2 deprecated providers status (2-3 ч)
  └─ §6.3 four prochie TODO (8-12 ч)
```

**Total estimate:** 7 рабочих дней (с testing + commits + reviews).

### 11.3 Smoke tests после каждого P-этапа

#### After P0 (§2.1 + §2.2 + §2.3)
- [ ] **11.3.P0.a** Embedding default test: `unset EMBEDDING__MODEL && python -c "from src.pdf_framework.config.embedding import EmbeddingSettings; print(EmbeddingSettings().dimensions)"` → 4096
- [ ] **11.3.P0.b** JWT auth test: `pytest tests/api/auth/ tests/api/test_tenants.py -v` зелёный (≥12 tests)
- [ ] **11.3.P0.c** Chapter 31 links: `grep -n "§32" docs/framework documentation/31_QWEN3_RETRIEVAL_PRODUCTION/` — все ссылки на roadmap (relative path `../../roadmap/260426...`)
- [ ] **11.3.P0.d** Production retrieval не сломан: smoke search BSL через MCP вернёт релевантные результаты

#### After P1 (§3.x)
- [ ] **11.3.P1.a** `git grep -n "nomic-embed-text\|multilingual-e5-large\|all-MiniLM" "docs/framework documentation/"` — пусто или только в migration note context
- [ ] **11.3.P1.b** `git grep -n "bsl_code_v2\|bsl_code_v3\|experience_bank\|bsl_metadata\|visual_grounding" "docs/framework documentation/"` — пусто или strikethrough/historical
- [ ] **11.3.P1.c** `00_СОДЕРЖАНИЕ.md` содержит chapter 26 LAZY_MCP
- [ ] **11.3.P1.d** Markdown link validator чисто (внутренние ссылки разрешаются)

#### After P2 (§4.x)
- [ ] **11.3.P2.a** All 4 stub'а имеют unit-tests, total ~25-30 new tests, все green
- [ ] **11.3.P2.b** `git grep -n "TODO.*реализ\|TODO.*Implement" src/bsl/semantic_search/mcp.py src/bsl/sonar/ src/pdf_framework/search/strategies/raptor_search.py src/pdf_framework/search/hyde.py` — пусто
- [ ] **11.3.P2.c** Live MCP test: `mcp__bsl-semantic-search__bsl_similar(chunk_id="...")` возвращает results
- [ ] **11.3.P2.d** SonarQube CLI: `python -m src.bsl.sonar.cli config show` без exception

#### After P3 (§5.x)
- [ ] **11.3.P3.a** `00_СОДЕРЖАНИЕ.md` содержит все новые главы (33+ если создаются)
- [ ] **11.3.P3.b** `.claude/hooks/docs-change-enforcer.py` `CODE_TO_DOMAIN` mapping covers все 5 модулей
- [ ] **11.3.P3.c** Modify file in `src/pdf_framework/guardrails/` → Stop hook не выдаёт UNMAPPED warning

#### After P4 (§6.x)
- [ ] **11.3.P4.a** `python scripts/audit_unused_config.py` returns 0 unused fields
- [ ] **11.3.P4.b** All embedding providers loadable через factory: `for p in [local, tei, giga, bgem3, jina]: EMBEDDING__PROVIDER=$p python -c "..."` — без exception
- [ ] **11.3.P4.c** `git grep -n "TODO" src/ | wc -l` — снижено vs начальный baseline (было ~13 active TODOs)
- [ ] **11.3.P4.d** Full pytest suite: `pytest tests/ -x --tb=short` — failures count ≤ baseline + 0

### 11.4 Rollback procedures

#### P0 §2.1 (embedding defaults)
- [ ] **11.4.P0.1** Если smoke fails — `git revert <commit>` восстанавливает E5 1024d defaults. Существующие 4096d коллекции продолжают работать (env overrides ясны)

#### P0 §2.2 (JWT auth)
- [ ] **11.4.P0.2** Установить `AUTH__ENABLED=false` в `.env` — отключает JWT verification, возвращает «default» tenant. Backward compatible
- [ ] **11.4.P0.3** Если security review fails — revert commit + revert pyjwt dep

#### P1 (docs)
- [ ] **11.4.P1.1** Pure docs — `git revert <commit>` восстанавливает старые тексты, никаких runtime impacts

#### P2 (new features)
- [ ] **11.4.P2.1** Если новый feature ломает MCP — feature flag `BSL_SIMILAR_ENABLED=false` или revert commit
- [ ] **11.4.P2.2** SonarQube CLI — independent module, revert не затронет main framework

#### P3 (new docs)
- [ ] **11.4.P3.1** Pure docs — revert безопасен

#### P4 (maintenance)
- [ ] **11.4.P4.1** Wire'д config field — если ломает routing, revert. Field вернётся к `unused but defined` state

### 11.5 Status tracking — где смотреть прогресс

- [ ] **11.5.a** Каждый раздел P (§2.x, §3.x, §4.x, §5.x, §6.x) — отдельный коммит с meaningful message
- [ ] **11.5.b** Roadmap checkboxes `- [ ]` → `- [x]` после закрытия каждого подпункта (полу-автоматически через replace)
- [ ] **11.5.c** PR description / commit message — список закрытых пунктов
- [ ] **11.5.d** При паузе (>1 дня) — обновить §0 Status Dashboard в шапке roadmap'а (current state, next pickup)

### 11.6 Пред-execution verification

- [ ] **11.6.a** Этот чеклист read'нут до конца (все §11.1 — §11.5)
- [ ] **11.6.b** Понимание: «не удалять features» — все §4.x сценарии = IMPLEMENT, не DELETE
- [ ] **11.6.c** Понимание: смок-тесты после каждого P — обязательны (no «commit and pray»)
- [ ] **11.6.d** Понимание: при первом FAIL — rollback + investigate, не «fix forward»

### 11.7 Total scope summary

| Phase | Items | Files affected | Effort | Tests added |
|-------|-------|----------------|--------|-------------|
| **P0 §2** | 3 sub-items, ~15 sub-sub-tasks | 9 src + 2 docs | 6-9 ч | ~12 |
| **P1 §3** | 6 chapters refresh | 8 docs files | 4-6 ч | 0 (docs) |
| **P2 §4** | 4 features IMPLEMENT | 4 src + 4 test files + 4 docs | 21-32 ч | ~25-30 |
| **P3 §5** | 5 new docs sections | 5-10 new docs files + TOC + enforcer | 11-16 ч | 0 (docs) |
| **P4 §6** | 7 sub-items (config wire + provider docs + 4 TODOs) | 6 src + tests | 14-21 ч | ~10 |
| **TOTAL** | ~25 high-level items, ~150+ sub-sub-tasks | ~30 src + ~25 docs + ~20 tests | **56-84 ч** | ~50 |

**Realistic timeline:** 1-2 недели full-time, 3-4 недели part-time. Можно incremental.

### 11.8 Decision matrix — что делать когда

| Ситуация | Действие |
|----------|---------|
| Production retrieval ломается | P0 §2.1 — embedding defaults priority #1 |
| Security audit | P0 §2.2 — JWT auth priority |
| Новый разработчик confused chapters | P1 §3 — docs refresh |
| User жалуется на «функция не работает» | P2 §4 — implement stub |
| Stop hook UNMAPPED для нового модуля | P3 §5 — добавить mapping + chapter |
| `pip install -e .` падает на extra fields | P4 §6.1 — config cleanup |

---

## 12. Чек pre-launch — перед запуском в production

После закрытия roadmap (или хотя бы P0 + P1):

- [ ] **12.1** Все коммиты содержат `Co-Authored-By` если applicable
- [ ] **12.2** CLAUDE.md актуализирован (snapshot Phase 8+9.1+10 если уже)
- [ ] **12.3** `.env.example` все Phase 8/9.1 settings корректны
- [ ] **12.4** Smoke tests P0-P4 все green
- [ ] **12.5** Backup snapshots существуют (Qdrant volume + git tag для code rollback)
- [ ] **12.6** Documentation chapter 31 + новые главы 33+ актуальны

---

## 13. Sibling audit reports — cross-reference

Этот roadmap — **главный** (high-level priorities P0-P4). Детальные findings разнесены по 4 sibling документам в той же дате `260430_*`:

| Файл | Scope | Severity | Effort |
|------|-------|----------|--------|
| **[`260430_AUDIT_CHAPTER_01_OVERVIEW.md`](260430_AUDIT_CHAPTER_01_OVERVIEW.md)** | Глубокий cross-check главы 01_ОБЗОР (3 файла) — ~25 несоответствий: stale numbers, E5 default, Qdrant version | 🔴🟠 mix | 3-4 ч |
| **[`260430_AUDIT_CHAPTERS_02_30.md`](260430_AUDIT_CHAPTERS_02_30.md)** | Главы 02-30 (~24 главы) — найдено 9 проблемных (5 critical: 02.1 Qdrant version, 02.2 E5 default, 04.1 strategies, 28.4 bsl_code_v2, 29.6 visual_grounding) | 🔴🟠🟡 | ~2.5 ч |
| **[`260430_AUDIT_TESTS_COVERAGE.md`](260430_AUDIT_TESTS_COVERAGE.md)** | `tests/` directory — 172 файлов, 2 578 функций. **Critical gap: framework_search/ — 0 coverage**, нет regression теста для Phase 9.1 dim mismatch | 🔴 P0 | ~20-25 ч |
| **[`260430_AUDIT_DEPS_AND_CI.md`](260430_AUDIT_DEPS_AND_CI.md)** | `pyproject.toml` + CI/CD — `httpx`/`pyjwt` отсутствуют в base deps, нет pytest в CI, нет security audit | 🔴 P0 | ~5 ч |

### 13.1 Связь с phases этого roadmap'а

| P-фаза этого roadmap'а | Дополняется sibling'ом |
|------------------------|------------------------|
| §2 P0 (embedding defaults, JWT) | `260430_AUDIT_DEPS_AND_CI.md` D.1, D.2 — `httpx`+`pyjwt` deps |
| §3 P1 (6 chapters refresh) | `260430_AUDIT_CHAPTER_01_OVERVIEW.md` (chapter 01 detail), `260430_AUDIT_CHAPTERS_02_30.md` (главы 02-30 detail) |
| §4 P2 (IMPLEMENT 4 stubs) | `260430_AUDIT_TESTS_COVERAGE.md` T.1, T.3 — нужны тесты для новых имплементаций |
| §5 P3 (5 new docs sections) | — (не пересекается) |
| §6 P4 (config wire + 4 TODOs) | `260430_AUDIT_DEPS_AND_CI.md` D.3, D.6 — config + extras decisions |

### 13.2 Total scope (all 5 documents combined)

| Scope | Effort |
|-------|--------|
| Main roadmap (§2-§6 этого файла) | 56-84 ч |
| Chapter 01 detailed audit | 3-4 ч |
| Chapters 02-30 audit | 2.5 ч |
| Tests gaps (framework_search etc.) | 20-25 ч |
| Deps + CI (httpx/pyjwt + pytest job + security) | 5 ч |
| **GRAND TOTAL** | **~87-120 ч** |

**Realistic timeline (combined):** 2-3 недели full-time, 4-6 недель part-time.

### 13.3 Order of execution (recommended)

1. **D.1** (httpx in deps) — 5 min, разблокирует чистую установку
2. **D.7** (pytest CI job) — 1-2 ч, разблокирует regression detection
3. **§2 P0** (embedding defaults + JWT + chapter 31 §32 refs) — 6-9 ч
4. **T.2** (Phase 9.1 dim regression) — 2 ч, минимальный effort с большим выигрышем
5. **§3 P1 + sibling §2 (chapters audit fixes)** — 4-6 ч + 2.5 ч в batch
6. **T.1** (framework_search tests) — 6-8 ч
7. **§4 P2** (4 IMPLEMENT) — 21-32 ч (largest item)
8. Параллельно: T.3 + T.4 + T.5 + D.5 + remaining sibling items
9. §5 P3 + §6 P4 — finalization
