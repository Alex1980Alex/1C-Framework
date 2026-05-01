# Audit: tests/ coverage vs реализация

**Дата:** 2026-04-30 (вечер)
**Статус:** 🔄 IN PROGRESS — T.1 ✅ DONE (2026-05-01) | T.2 ✅ DONE (2026-05-01) | T.1.5 ✅ DONE (2026-05-01)
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
- [ ] **T.1.5** `test_embedder.py` (FrameworkTEIEmbedder) — отложено (требует httpx mock):
  - [ ] **T.1.5.a** Mock httpx.Client → embed_batch возвращает 4096d векторы
  - [ ] **T.1.5.b** is_query=True добавляет instruction prompt
  - [ ] **T.1.5.c** Retry logic при httpx.TransportError (3 попытки)
- [x] **T.1.6** `test_file_walker.py` ✅ 2026-05-01:
  - [x] **T.1.6.a** Skip patterns (`.venv`, `__pycache__`, `node_modules`, `src/projects/configuration/`)
  - [x] **T.1.6.b** Filter by extensions (.py→python, .md→markdown, .exe→skip)
  - [x] **T.1.6.c** Large file (>512KB) skip, dedup same-file-two-roots
- [ ] **T.1.7** `test_indexer.py` (integration):
  - [ ] **T.1.7.a** Run end-to-end на `tests/fixtures/mini_repo/` (3-5 файлов) → проверить что коллекция создана с N точек
  - [ ] **T.1.7.b** Idempotent re-run: same files → no new upserts
  - [ ] **T.1.7.c** File modified → upsert обновляет соответствующие чанки

### 2.2 🔴 Phase 9.1 dim mismatch — нет regression теста

**Контекст:** до Phase 9.1 `memory-first-hook.py` вызывал Ollama 768d, а коллекции были 1024d / 4096d → **silent fail**, hook возвращал 0 результатов из Qdrant и фолбэчился на token overlap.

**Текущий тест:** `tests/integration/test_memory_first_hook.py` — есть, но не проверяет alignment эмбеддера и target collection.

**Action items (estimated 2 ч):**
- [x] **T.2.1** Добавить `TestDimAlignment` в `test_memory_first_hook.py` ✅ 2026-05-01:
  - [x] **T.2.1.a** `test_hook_declares_expected_collections` — проверяет `SEMANTIC_COLLECTIONS` содержит ровно {skill_library, experience_embeddings, conversation_memory}
  - [x] **T.2.1.b** `test_hook_comment_documents_4096d` — проверяет "4096" в тексте hook-скрипта
  - [x] **T.2.1.c** `@pytest.mark.integration test_qdrant_collection_dims_match_expected` — httpx GET `/collections/{name}`, skip если Qdrant недоступен; assert dim==4096; 22/22 passed ✅
- [ ] **T.2.2** Запускать в CI как mandatory check (post-Phase 9.1)
- [ ] **T.2.3** Документировать паттерн в lessons learned (chapter 31.5 §2 — уже есть, ссылаться)

### 2.3 🟠 search/strategies/ — слабое покрытие

**Найдено:** 36 файлов в `src/pdf_framework/search/strategies/` vs ~13 test-функций direct coverage.

**Стратегии без явных тестов** (нужно подтверждение):
- `mmr.py` (MMR diversity)
- `bm25_*.py` (4 файла — qdrant native, fts5, both, fallback)
- `two_stage.py` (FlashRank reranker)
- `dual_vector.py` (Phase 36)
- `auto_merge.py` (Parent-Child автомерж)

**Action items (estimated 4-6 ч):**
- [ ] **T.3.1** `tests/test_search_strategies/`:
  - [ ] `test_mmr.py` — diversity λ=0/0.5/1, проверка отсутствия duplicates
  - [ ] `test_bm25_qdrant.py` — sparse vectors, FusionQuery RRF
  - [ ] `test_bm25_fts5.py` — SQLite fallback, language=russian, k1/b params
  - [ ] `test_two_stage.py` — FlashRank reranking порядок
  - [ ] `test_dual_vector.py` — комбинация dense + sparse query
  - [ ] `test_auto_merge.py` — child→parent merge при threshold≥3

### 2.4 🟠 loaders/ (PDF) — частичное покрытие

**Phase 28 hybrid loader** (4 уровня каскада L1-L4) — критический pipeline. Найдено `tests/test_docling_integration.py`, но cascade tests разбросаны.

**Action items (estimated 3-4 ч):**
- [ ] **T.4.1** `tests/test_loaders/test_hybrid_cascade.py`:
  - [ ] L1 fitz fast → если text >= threshold, не идти на L2
  - [ ] L2 docling → таблицы, layout
  - [ ] L3 vision OCR → если text < threshold (scanned PDF)
  - [ ] L4 ensemble verification
- [ ] **T.4.2** Smart router auto-selection — fixture с 4 типами PDF (text-heavy, scan, table-heavy, mixed)

### 2.5 🟠 auto-reindex on commit — нет integration test

**Контекст:** Phase 9.1 finale — `scripts/git_post_commit_reindex.py` запускает BSL + framework reindex split, detached subprocess, 5-уровневое резервирование (file watcher + MCP lazy-check + git post-commit).

**Найдено:** скрипт существует, нет integration test.

**Action items (estimated 3 ч):**
- [ ] **T.5.1** `tests/integration/test_post_commit_reindex.py`:
  - [ ] **T.5.1.a** Mock `git diff` (одно .py + одно .bsl изменение)
  - [ ] **T.5.1.b** Запустить script — проверить что spawned 2 detached subprocess (BSL + framework)
  - [ ] **T.5.1.c** Verify log file создан
  - [ ] **T.5.1.d** Verify exit code = 0 (commit не блокируется даже при failure dispatch)
- [ ] **T.5.2** `core.hooksPath` setup test — verify `git config core.hooksPath` = `scripts/git_hooks` после init

---

## 3. Качественные observations

### 3.1 Что работает хорошо

- `conftest.py` — централизованные fixtures для Qdrant test container, mock embedder, sample documents
- Phase 8.12 — образцово покрыта (4 файла, edge cases)
- `test_e2e_phases.py` — smoke per-phase, удобно для regression check после major bumps
- `tests/eval/` — RAGAS evaluation harness, regression-gates ready

### 3.2 Слабые места (общие)

- **Mock vs real Qdrant**: часть тестов идёт против real container (необходим Docker), часть — против mock'ов. Нет consistent strategy. **Рекомендация:** разделить по `tests/integration/` (real Qdrant) vs `tests/unit/` (mocked).
- **Test discovery**: `pytest` находит всё, но running individual phase suites неудобно — нет `pytest.ini` markers `@pytest.mark.phase8`. **Рекомендация:** добавить markers, в `pyproject.toml [tool.pytest.ini_options]`.
- **CI flakiness**: integration tests могут flake из-за async timing. Не наблюдалось напрямую, но риск есть.
- **Coverage measurement**: нет `pytest-cov` в CI или README. **Рекомендация:** добавить как opt-in (`make coverage`).

---

## 4. Action plan summary

| ID | Что | Severity | Effort |
|----|-----|----------|--------|
| **T.1** | framework_search/ test suite (7 файлов) | 🔴 P0 | 6-8 ч |
| **T.2** | Phase 9.1 dim alignment regression test | 🔴 P0 | 2 ч |
| **T.3** | search/strategies test coverage (6 файлов) | 🟠 P1 | 4-6 ч |
| **T.4** | loaders hybrid cascade test | 🟠 P1 | 3-4 ч |
| **T.5** | post-commit reindex integration test | 🟠 P1 | 3 ч |
| **T.6** | pytest markers per-phase | 🟡 P2 | 1 ч |
| **T.7** | pytest-cov в CI (opt-in) | 🟡 P2 | 1 ч |
| **TOTAL** | — | — | **~20-25 ч** |

### 4.1 Order of execution

1. **T.2** (Phase 9.1 dim) — blocking-class проблема, минимальный effort
2. **T.1** (framework_search) — критическая lacuna, вытекает из chapter 31
3. **T.5** (post-commit) — закрывает risky pipeline
4. **T.3** + **T.4** — параллельно, расширяют coverage
5. **T.6** + **T.7** — quality-of-life cleanup

### 4.2 Acceptance criteria

- [ ] CI прогоняет full suite зелёной
- [ ] `framework_search/` имеет coverage >= 70%
- [ ] Phase 9.1 dim alignment test fail'нет если кто-то поменяет embedder без update target collections
- [ ] `pytest -m phase8` запускает Phase 8 suite

---

## 5. Связано

- Главный roadmap: [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md) §1.2 (tests scope)
- Глава 31 (production retrieval с детализацией framework_search): [`../framework documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md`](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md)
- Phase 9.1 lessons learned (silent dim mismatch): [`../framework documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.5_Миграция_и_итоги.md`](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.5_Миграция_и_итоги.md) §«Lessons learned» #2
- Sibling audits: [`260430_AUDIT_CHAPTER_01_OVERVIEW.md`](260430_AUDIT_CHAPTER_01_OVERVIEW.md), [`260430_AUDIT_CHAPTERS_02_30.md`](260430_AUDIT_CHAPTERS_02_30.md), [`260430_AUDIT_DEPS_AND_CI.md`](260430_AUDIT_DEPS_AND_CI.md)
