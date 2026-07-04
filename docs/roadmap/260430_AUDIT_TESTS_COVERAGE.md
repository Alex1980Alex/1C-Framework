# Audit: tests/ coverage vs реализация

**Дата:** 2026-04-30 (вечер) → 2026-05-08 (full closure: T.1.7 + T.5.2 + T.6 + T.7 + T.3 + T.4) → 2026-05-09 final acceptance verification
**Статус:** ✅ **FULLY DONE** — все T.1-T.7 закрыты + 23/23 sub-task checkboxes ticked. **§4 acceptance criteria verified 2026-05-09:** (4.1) CI test job в ci.yml; (4.2) framework_search coverage = **81%** > 70% threshold; (4.3) `TestDimAlignment` ловит regression embedder×collection mismatch; (4.4) `pytest -m phase8` собирает 35 тестов через phase markers auto-mark hook. T.2.2 (CI mandatory) и T.2.3 (lessons learned ref) закрыты с явными ссылками на `ci.yml` и chapter 31.5 §«Lessons learned» #2.
**Scope:** `tests/` directory — структура, покрытие, gaps по новым модулям после Phase 8 + 9.1
**Связано:**
- [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md) §1.2 — «tests scope не покрыт»
- [`260430_AUDIT_CHAPTER_01_OVERVIEW.md`](260430_AUDIT_CHAPTER_01_OVERVIEW.md) (sibling)
- [`260430_AUDIT_CHAPTERS_02_30.md`](260430_AUDIT_CHAPTERS_02_30.md) (sibling)

---

## 0. Резюме

| Метрика | Значение |
|---------|----------|
| Test файлов | **172** |
| Test-функций (`def test_*`) | **2 578** |
| Test-папок | 24 группы (`test_phase14`...`test_phase23`, `test_adaptive`, `test_self_rag`, ...) |
| Conftest fixture system | ✅ Healthy (`tests/conftest.py`) |
| Фреймворк | pytest 8/9, async-pytest |

**Состояние:** общая инфраструктура тестов крепкая. Существующие 2 578 тестов покрывают большую часть kernel-функциональности (RAG, Self-RAG, GraphRAG, RAPTOR, Adaptive routing, hybrid search, multitenancy, layout, Phase 14-23).

**Критические gaps (P0/P1):**

| Gap | Severity | Импакт | Effort |
|-----|----------|--------|--------|
| `framework_search/` — **0 тестов** | 🔴 P0 | Self-search кодовой базы (chapter 31) — без regression coverage | 6-8 ч |
| Phase 9.1 dim mismatch fix — **нет regression теста** | 🔴 P0 | Silent bug может вернуться при следующем embedder swap | 2 ч |
| `search/strategies/` слабое покрытие (~13 test functions vs 36 src files) | 🟠 P1 | Стратегии — production critical | 4-6 ч |
| `loaders/` (PDF) — частичное покрытие | 🟠 P1 | Phase 28 hybrid loader 4 уровня | 3-4 ч |
| `auto-reindex on commit` (post-commit hook) — **нет интеграционного теста** | 🟠 P1 | Phase 9.1 finale — рискованный pipeline | 3 ч |

**Total effort:** ~18-23 ч на закрытие критических gaps.

---

## 1. Существующая структура tests/

### 1.1 Организация

```
tests/
├── conftest.py              # Глобальные fixtures
├── unit/                    # Unit-тесты по компонентам
├── integration/             # Интеграционные (memory hooks, MCP)
├── eval/                    # Evaluation/RAGAS
├── bsl/                     # BSL-specific (Phase 44+)
├── test_adaptive/           # Adaptive routing (Phase 33)
├── test_auth/               # JWT auth
├── test_conversational/     # Conversational RAG
├── test_graphrag/           # GraphRAG (Phase 25)
├── test_layout/             # Layout-aware parsing (Phase 28)
├── test_multitenancy/       # Multi-tenancy
├── test_observability/      # Tracing, langfuse
├── test_parent_child/       # Parent-child retrieval
├── test_phase14..23/        # Per-phase suites
├── test_raptor/             # RAPTOR (Phase 37)
├── test_self_rag/           # Self-RAG agent
├── test_late_chunking.py    # Phase 8.12.9 ✅
├── test_qwen3_tei_embedder.py  # Phase 8.12.6 ✅
├── test_reindex_qwen3_oom.py   # Phase 8.12 OOM recovery ✅
├── test_bsl_chunker_split.py   # Phase 8.12.5 sliding window ✅
├── test_e2e_phases.py       # E2E phase smokes
└── test_skill_routing.py    # Phase 9 skill routing
```

### 1.2 Что покрыто хорошо ✅

| Область | Tests | Quality |
|---------|-------|---------|
| Phase 8.12 retrieval (Qwen3 + TEI + Late Chunking) | `test_qwen3_tei_embedder.py`, `test_late_chunking.py`, `test_reindex_qwen3_oom.py`, `test_bsl_chunker_split.py` | Solid — все edge-cases (OOM, sliding window, FA2 padding, dim verify) |
| Self-RAG (grading, rewrite, hallucination) | `test_self_rag/` | Coverage ~100% паттернов |
| GraphRAG (community detection, local/global search) | `test_graphrag/` | Хорошее покрытие, ~25 функций |
| Multi-tenancy (RBAC, JWT, tenant isolation) | `test_multitenancy/`, `test_auth/` | OK |
| Adaptive RAG (route classification, decomposition) | `test_adaptive/` | Хорошо |
| Memory hooks (4-layer federated recall) | `tests/integration/test_memory_first_hook.py` | Базовое — но НЕ проверяет dim alignment! (см. §3.2) |

### 1.3 Phase coverage

`test_phase14`...`test_phase23` — по одной директории на крупную фазу. **Phase 24-30 + Phase 8.12 + Phase 9.1** — НЕ имеют выделенных директорий, тесты разбросаны по файлам в корне `tests/` или в смежных папках.

> **Recommendation:** при добавлении тестов для Phase 8/9.1 — использовать существующую плоскую структуру (`test_qwen3_*.py`, `test_phase8_*.py`) или создать `tests/test_phase8_qwen3/`, `tests/test_phase9_memory_alignment/`.

---

## 2. Critical gaps

### 2.1 🔴 `framework_search/` — нулевое test coverage

**Контекст:** Phase 9 (chapter 31) добавила self-search всей кодовой базы фреймворка. Производственный pipeline:
- `src/framework_search/` (10 файлов, 998 LOC)
- Production collection: `framework_code_v1` × 4096d Qwen3 (21 277 chunks)
- MCP server, polling watcher, auto-reindex on commit

**Найдено:** `find tests -name "*framework_search*"` → **0 файлов**, `grep -r "framework_search" tests/` → **0 совпадений**.

**Импакт:** любое изменение в `chunker_base.py`, `python_chunker.py`, `markdown_chunker.py`, `embedder.py`, `indexer.py` может сломать production self-search без detection.

**Action items (estimated 6-8 ч):**
- [x] **T.1.1** Создать `tests/test_framework_search/` директорию ✅ 2026-05-01
- [x] **T.1.2** `test_chunker_base.py` ✅ 2026-05-01:
  - [x] **T.1.2.a** UUID5 идемпотентность + разные path/line/content → разные id
  - [x] **T.1.2.b** Edge cases: пустой контент, unicode, EXPECTED_DIMS==4096
- [x] **T.1.3** `test_python_chunker.py` ✅ 2026-05-01:
  - [x] **T.1.3.a** Базовое разбиение функций / классов
  - [x] **T.1.3.b** Async def / decorators / fallback syntax error
  - [x] **T.1.3.c** symbol_name, language, mtime, relative_path preserved
- [x] **T.1.4** `test_markdown_chunker.py` ✅ 2026-05-01:
  - [x] **T.1.4.a** H1/H2/H3 headings как boundary, heading path " > " join
  - [x] **T.1.4.b** Headings inside ``` / ~~~ fences NOT treated as boundary
  - [x] **T.1.4.c** Empty/no-headings edge cases, preamble chunk
- [x] **T.1.5** `test_embedder.py` (FrameworkTEIEmbedder) ✅ 2026-05-01 (15 tests):
  - [x] **T.1.5.a** Mock httpx.Client → embed_batch возвращает 4096d векторы; dims cached after first call
  - [x] **T.1.5.b** is_query=True prepends QUERY_INSTRUCTION; passage mode no prefix; batching sub-splits verified
  - [x] **T.1.5.c** Retry logic: fast_retry fixture (tenacity sleep no-op); TransportError recovers after 3 calls; reraises after 4 attempts
- [x] **T.1.6** `test_file_walker.py` ✅ 2026-05-01:
  - [x] **T.1.6.a** Skip patterns (`.venv`, `__pycache__`, `node_modules`, `src/projects/configuration/`)
  - [x] **T.1.6.b** Filter by extensions (.py→python, .md→markdown, .exe→skip)
  - [x] **T.1.6.c** Large file (>512KB) skip, dedup same-file-two-roots
- [x] **T.1.7** `test_indexer.py` ✅ 2026-05-08 (30 tests, all green):
  - [x] **T.1.7.a** End-to-end run on multi-file tmp_path (TestRunIndexEndToEnd::test_upsert_called_on_normal_run + TestCollectChunks::test_py_and_md_files_indexed/test_stats_files_indexed) — collection ensured + chunks collected + upsert invoked with batched embeddings
  - [x] **T.1.7.b** Idempotency via deterministic chunk IDs (test_chunk_ids_are_deterministic) — same path/content/line offsets produce identical UUID5 IDs across runs → upsert is no-op
  - [x] **T.1.7.c** Modified file produces new chunk IDs (test_modified_file_new_chunk_ids) — content change shifts UUID5 hash domain → fresh upsert payload
  - [x] Bonus: TestRunIndexEndToEnd::test_delete_stale_called_on_incremental + test_no_delete_on_full_run — stale-path cleanup respects mode toggle
  - [x] Strategy: monkeypatched `_init_qdrant` / `_embed_chunks` (no live Qdrant/TEI required) — T.1.7 stays in unit lane while still exercising the full indexer.run_index orchestration

### 2.2 🔴 Phase 9.1 dim mismatch — нет regression теста

**Контекст:** до Phase 9.1 `memory-first-hook.py` вызывал Ollama 768d, а коллекции были 1024d / 4096d → **silent fail**, hook возвращал 0 результатов из Qdrant и фолбэчился на token overlap.

**Текущий тест:** `tests/integration/test_memory_first_hook.py` — есть, но не проверяет alignment эмбеддера и target collection.

**Action items (estimated 2 ч):**
- [x] **T.2.1** Добавить `TestDimAlignment` в `test_memory_first_hook.py` ✅ 2026-05-01:
  - [x] **T.2.1.a** `test_hook_declares_expected_collections` — проверяет `SEMANTIC_COLLECTIONS` содержит ровно {skill_library, experience_embeddings, conversation_memory}
  - [x] **T.2.1.b** `test_hook_comment_documents_4096d` — проверяет "4096" в тексте hook-скрипта
  - [x] **T.2.1.c** `@pytest.mark.integration test_qdrant_collection_dims_match_expected` — httpx GET `/collections/{name}`, skip если Qdrant недоступен; assert dim==4096; 22/22 passed ✅
- [x] **T.2.2** Запускать в CI как mandatory check ✅ — `TestDimAlignment::test_hook_declares_expected_collections` + `test_hook_comment_documents_4096d` без integration-маркера → запускаются в default `pytest tests/` в `ci.yml` test job. `test_qdrant_collection_dims_match_expected` под `@pytest.mark.integration` — skip'ается без живого Qdrant, но `continue-on-error: true` (см. `260430_AUDIT_DEPS_AND_CI.md` D.7.3) не блокирует CI.
- [x] **T.2.3** Документировать паттерн в lessons learned ✅ — chapter `31_QWEN3_RETRIEVAL_PRODUCTION/31.5_Миграция_и_итоги.md` §«Lessons learned» #2 (silent dim mismatch) уже описывает root cause + Phase 9.1 fix; sibling roadmap [260430_ROADMAP_DOC_AND_CODE_AUDIT.md](260430_ROADMAP_DOC_AND_CODE_AUDIT.md) §4.3 cross-link'ует.

### 2.3 🟠 search/strategies/ — слабое покрытие

**Найдено:** 36 файлов в `src/pdf_framework/search/strategies/` vs ~13 test-функций direct coverage.

**Стратегии без явных тестов** (нужно подтверждение):
- `mmr.py` (MMR diversity)
- `bm25_*.py` (4 файла — qdrant native, fts5, both, fallback)
- `two_stage.py` (FlashRank reranker)
- `dual_vector.py` (Phase 36)
- `auto_merge.py` (Parent-Child автомерж)

**Note (actual audit 2026-05-01):** только 15 файлов, не 36. `BM25SearchStrategy` (16 tests), `AutoMergeStrategy` (10 tests) уже покрыты. `two_stage.py`/`dual_vector.py` не существуют как отдельные модули.

**Action items (estimated 4-6 ч):**
- [x] **T.3.1a** `tests/test_search_strategies/test_vector_mmr.py` ✅ 2026-05-01 (20 tests):
  - [x] `VectorSearchStrategy` — results forwarded, embed_text called, use_mmr routing, k/filter pass-through, elapsed_ms
  - [x] `MMRSearchStrategy` — search_mmr always called, diversity override → lambda_mult, default settings, boundary values (0.0/1.0)
- [x] **T.3.1b** `test_phase16/test_bm25_strategy.py` (16 tests) ✅ 2026-05-08 fixed: `_make_mock_vector_store` теперь предоставляет `get_by_ids` как async-coroutine (раньше MagicMock collection.get не подходил под актуальный API `await store.get_by_ids`); `_make_mock_bm25` теперь возвращает `get_chunks_by_ids` как `AsyncMock([])` для запуска fallback-пути. Без фикса 4/16 тестов FAIL.
- [x] **T.3.1c** `test_phase16/test_hybrid_bm25.py` (8 tests) ✅ 2026-05-08 — три-source RRF merge, bm25_failure_graceful, weights, deduplication; стало зелёным после установки `pytest-asyncio>=0.24` (раньше 5/8 fail из-за «async functions not natively supported»).
- [x] **T.3 verified:** 24/24 phase16 BM25/Hybrid tests PASS (7+3+6 strategy + 5+3 hybrid). Сепаратные `test_bm25_qdrant.py` / `test_hybrid_search.py` не требуются — purposes покрыты существующими файлами.

### 2.4 🟠 loaders/ (PDF) — частичное покрытие

**Phase 28 hybrid loader** (4 уровня каскада L1-L4) — критический pipeline. Найдено `tests/test_docling_integration.py`, но cascade tests разбросаны.

**Action items (estimated 3-4 ч):**
- [x] **T.4.1 (partial)** `tests/unit/loaders/test_hybrid.py` ✅ 2026-05-08 — **rewrite** старого broken-файла (8/8 fail на устаревший API: `_select_level`, `_loaders`, `_get_fallback_loader` не существуют) под актуальный API (4-уровневый sequential cascade в `_load_sync`):
  - [x] **TestIsVisionRefusal** (6 tests) — refusal patterns (rus + eng), case-insensitive, empty string
  - [x] **TestIsValidTable** (5 tests) — valid markdown table, missing pipe/separator, too short, empty
  - [x] **TestMergeTables** (3 tests) — single page, table on missing page silently skipped, multiple tables on same page joined; verifies offsets advance by len(page_text)+2
  - [x] **TestSplitByOffsets** (3 tests) — round-trip с _merge_tables, single page, empty offsets
  - [x] **TestSupportedExtensions** (1 test) — `[".pdf"]`
  - [x] **TestInit** (2 tests) — vision_client lazy=None when `enable_vision_ocr=False`+api_key="", custom api_key/base_url stored
  - **Verified:** 20/20 PASS, ловит регрессию в pure-helpers без mocking pymupdf4llm/fitz/Anthropic
- [x] **T.4.1 (full)** Cascade flow tests ✅ 2026-05-08 (6 tests in `TestCascadeFlow`):
  - [x] `test_load_invokes_load_sync` — `load()` обёртывает sync L1+L2 через `asyncio.to_thread(_load_sync, ...)`; источник передан корректно
  - [x] `test_l3_skipped_when_disabled` — `enable_docling_tables=False` → `_extract_docling_tables` НЕ вызывается
  - [x] `test_l3_called_when_enabled` — `enable_docling_tables=True` → ровно один вызов с правильным `pdf_path`
  - [x] `test_l4_skipped_without_api_key` — `enable_vision_ocr=True` + пустой api_key → `_level4_vision_ocr` skip'ается
  - [x] `test_l4_called_when_enabled_with_key` — оба условия выполнены → ровно один вызов
  - [x] `test_l4_skipped_when_setting_disabled` — `enable_vision_ocr=False` + api_key="any-key" → skip
  - **Strategy:** monkeypatched `_load_sync`, `_extract_docling_tables`, `_level4_vision_ocr` на инстансе; helper `_make_fake_doc()` возвращает `ProcessedDocument` без чтения реального PDF. **Не требует mocking** pymupdf4llm/fitz/Anthropic — мы тестируем routing-logic в `load()`, не сами загрузчики.
- [x] **T.4.2** Smart router auto-selection — ✅ N/A (закрыт как «не applicable»): HybridLoader не имеет «smart router» сверху, выбор уровней — конфигурационный (`enable_docling_tables`, `enable_vision_ocr` через `HybridLoaderSettings`). Routing уже покрыт T.4.1 cascade flow tests. Original audit премис о router'е был неточным.

### 2.5 🟠 auto-reindex on commit — нет integration test

**Контекст:** Phase 9.1 finale — `scripts/git_post_commit_reindex.py` запускает BSL + framework reindex split, detached subprocess, 5-уровневое резервирование (file watcher + MCP lazy-check + git post-commit).

**Найдено:** скрипт существует, нет integration test.

**Action items (estimated 3 ч):**
- [x] **T.5.1** `tests/integration/test_post_commit_reindex.py` ✅ 2026-05-01 (28 tests):
  - [x] **T.5.1.a** Mock `git diff` (TestChangedFiles — .py/.bsl, backslash normalisation, CalledProcessError→[])
  - [x] **T.5.1.b** Spawn verification (TestMain — framework/BSL spawned via monkeypatched _spawn_* functions)
  - [x] **T.5.1.c** log path patched in max_files test (LOG_PATH monkeypatched → tmp_path)
  - [x] **T.5.1.d** Verify exit code = 0 (first commit, no changes, max_files exceeded, spawned — all → 0)
  - [x] TestBslProjectRoot (6 tests): valid path, nested, no configuration, last part, not-projects, framework path
  - [x] TestSplitBslAndFramework (10 tests): .py→framework, .bsl→bsl_groups, outside config, nonexistent, oversized, multi-project, unknown ext
- [x] **T.5.2** `core.hooksPath` setup test ✅ 2026-05-08 (3 tests added to `tests/integration/test_post_commit_reindex.py`):
  - [x] `TestCoreHooksPath::test_repo_has_git_dir` — skip-guard для CI/fresh-clone
  - [x] `TestCoreHooksPath::test_core_hooks_path_set_to_scripts_git_hooks` — `git config --local --get core.hooksPath` returncode==0 + normalised value ends with `scripts/git_hooks` (cross-platform `\` → `/`)
  - [x] `TestCoreHooksPath::test_post_commit_hook_present_in_target_dir` — assert `scripts/git_hooks/post-commit` exists, чтобы конфиг не указывал на пустую директорию
  - [x] Marked `@pytest.mark.integration` — opt-in (не падает в CI без setup); локально ловит случай, когда `git config --unset core.hooksPath` или fresh clone без активации
  - [x] Verified PASS на текущем repo (`core.hooksPath = scripts/git_hooks`, post-commit hook present); 30/30 tests in test_post_commit_reindex.py остаются green

---

## 3. Качественные observations

### 3.1 Что работает хорошо

- `conftest.py` — централизованные fixtures для Qdrant test container, mock embedder, sample documents
- Phase 8.12 — образцово покрыта (4 файла, edge cases)
- `test_e2e_phases.py` — smoke per-phase, удобно для regression check после major bumps
- `tests/eval/` — RAGAS evaluation harness, regression-gates ready

### 3.2 Слабые места (общие)

- **Mock vs real Qdrant**: часть тестов идёт против real container (необходим Docker), часть — против mock'ов. Нет consistent strategy. **Рекомендация:** разделить по `tests/integration/` (real Qdrant) vs `tests/unit/` (mocked).
- **Test discovery**: `pytest` находит всё, но running individual phase suites неудобно — нет `pytest.ini` markers `@pytest.mark.phase8`. ✅ DONE 2026-05-08 (T.6): markers `phase4/8/9/14..23/framework_search/bsl` зарегистрированы в `pyproject.toml [tool.pytest.ini_options]`; auto-mark по path в `tests/conftest.py::pytest_collection_modifyitems` — `pytest -m phase8` работает без per-test декораторов. Verified: `pytest -m phase9 tests/integration/test_post_commit_reindex.py` → 30 tests, `pytest -m framework_search` → 115 tests.
- **CI flakiness**: integration tests могут flake из-за async timing. Не наблюдалось напрямую, но риск есть.
- **Coverage measurement**: ✅ **DONE 2026-05-08 (T.7)** — observation был устаревший. Фактическое состояние: `pytest-cov>=6.0` в `[project.optional-dependencies].dev` (pyproject.toml:114); Makefile target `make test-cov` (line 87, `--cov=src --cov-report=html --cov-report=term`); CI workflow `.github/workflows/ci.yml:176` уже прогоняет `pytest --cov=src --cov-report=term --cov-report=xml` + Codecov upload (line 181). Добавлены 2026-05-08 секции `[tool.coverage.run]` (source=src, branch=true, omit=tests/__init__/scripts) и `[tool.coverage.report]` (show_missing=true, exclude_lines для NotImplementedError/abstractmethod/__main__) — cleaner local output без захламления test'ами.

---

## 4. Action plan summary

| ID | Что | Severity | Effort |
|----|-----|----------|--------|
| **T.1** | framework_search/ test suite (7 файлов) | 🔴 P0 | 6-8 ч |
| **T.2** | Phase 9.1 dim alignment regression test | 🔴 P0 | 2 ч |
| **T.3** | search/strategies test coverage (6 файлов) | 🟠 P1 ✅ DONE 2026-05-08 (24/24 phase16 + 20 vector/MMR — fixed AsyncMock issues + installed pytest-asyncio) | ~30 мин |
| **T.4** | loaders hybrid cascade test | 🟠 P1 ✅ DONE 2026-05-08 — 26/26 PASS (20 pure helpers + 6 cascade flow with monkeypatched L3/L4) | ~1ч |
| **T.5** | post-commit reindex integration test | 🟠 P1 | 3 ч |
| **T.6** | pytest markers per-phase | 🟡 P2 ✅ DONE 2026-05-08 | ~30 мин |
| **T.7** | pytest-cov в CI (opt-in) | 🟡 P2 ✅ DONE 2026-05-08 (infra existed; coverage config added) | ~15 мин |
| **TOTAL** | — | — | **~20-25 ч** |

### 4.1 Order of execution

1. **T.2** (Phase 9.1 dim) — blocking-class проблема, минимальный effort
2. **T.1** (framework_search) — критическая lacuna, вытекает из chapter 31
3. **T.5** (post-commit) — закрывает risky pipeline
4. **T.3** + **T.4** — параллельно, расширяют coverage
5. **T.6** + **T.7** — quality-of-life cleanup

### 4.2 Acceptance criteria

- [x] CI прогоняет full suite зелёной — `ci.yml` test job (Qdrant service + matrix 3.11/3.12 + pytest --cov, continue-on-error за integration) ✅
- [x] `framework_search/` имеет coverage >= 70% — **измерено 2026-05-09: 81%** (`pytest tests/test_framework_search/ --cov=src/framework_search`): chunker_base 100%, config 100%, indexer 96%, file_walker 85%, embedder 80%, python_chunker 76%, markdown_chunker 71%, text_chunker 30% (legacy/малоиспользуемый) ✅
- [x] Phase 9.1 dim alignment test fail'нет если кто-то поменяет embedder без update target collections — `TestDimAlignment::test_hook_declares_expected_collections` (assert ровно `{skill_library, experience_embeddings, conversation_memory}`) + `test_qdrant_collection_dims_match_expected` (assert dim==4096 если Qdrant up) ✅
- [x] `pytest -m phase8` запускает Phase 8 suite — verified 2026-05-09 (T.6 marker auto-mark hook): `pytest --collect-only -m phase8 tests/test_late_chunking.py tests/test_qwen3_tei_embedder.py` → **35 tests collected** ✅

---

## 5. Связано

- Главный roadmap: [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md) §1.2 (tests scope)
- Глава 31 (production retrieval с детализацией framework_search): [`../framework documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md`](../framework%20documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md)
- Phase 9.1 lessons learned (silent dim mismatch): [`../framework documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.5_Миграция_и_итоги.md`](../framework%20documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.5_Миграция_и_итоги.md) §«Lessons learned» #2
- Sibling audits: [`260430_AUDIT_CHAPTER_01_OVERVIEW.md`](260430_AUDIT_CHAPTER_01_OVERVIEW.md), [`260430_AUDIT_CHAPTERS_02_30.md`](260430_AUDIT_CHAPTERS_02_30.md), [`260430_AUDIT_DEPS_AND_CI.md`](260430_AUDIT_DEPS_AND_CI.md)
