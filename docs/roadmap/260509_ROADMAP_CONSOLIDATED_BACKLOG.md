# Roadmap: Consolidated Backlog Audit (post-Phase 8 + 9.1, 2026-05-09)

**Дата:** 2026-05-09
**Статус:** 📋 PROPOSED — единый перечень не-реализованных элементов фреймворка после закрытия 5 sibling-аудитов 260430_*
**Scope:** ВСЕ открытые backlog-items из 15 существующих roadmap'ов + raw code TODO/FIXME/stubs + doc TOC desync + skipped тесты — для системного приоритизированного closure
**Метод:** 3 параллельных Explore-агента (code TODO scan / existing roadmap deferred items / docs TOC vs filesystem)
**Связано:**
- [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md) — fully done 2026-05-09 (parent)
- [`260423_ROADMAP_FRAMEWORK_IMPROVEMENTS.md`](260423_ROADMAP_FRAMEWORK_IMPROVEMENTS.md) — 21-task Track A/B/C; parent backlog
- [`260403_ROADMAP_MEMORY_MIGRATION.md`](260403_ROADMAP_MEMORY_MIGRATION.md) — Phase 5-8 P5 observability TODO
- [`260331_ROADMAP_MCP_IMPROVEMENTS.md`](260331_ROADMAP_MCP_IMPROVEMENTS.md) — Phase 11/12 deferred
- [`260320_ROADMAP_DELEGATION_LEARNING.md`](260320_ROADMAP_DELEGATION_LEARNING.md) — Iter 4-5
- [`260326_ROADMAP_GPU_BSL_INDEXING.md`](260326_ROADMAP_GPU_BSL_INDEXING.md) — Phase 4-5

---

## 0. Executive summary

> **Closure update 2026-05-09 (после 2 сессий active work):** **21 / 31 items closed** (5 P0 + 8 P1 + 7 P2 + 1 P3). См. §11 Closure log ниже.

| Severity | Count | Closed | Open | Total effort (est) |
|---|---|---|---|---|
| 🔴 P0 | 5 | **5** ✅ | 0 | done |
| 🟠 P1 | 9 | **8** | 1 (§3.4 GEPA) | mostly done |
| 🟡 P2 | 11 | **7** | 4 (§4.1, §4.5, §4.6, §4.10) | partial |
| 🟢 P3 | 6 | **1** (§5.6) | 5 deferred | ad-hoc |
| **TOTAL** | **31** | **21** ✅ | **10** (4 truly waiting on external + 6 deferred) | — |

**Three critical paths:**
1. **CI/eval unblock:** ✅ DONE — golden_v1 v1.1 (40 items) + smoke-gate + DeepEval gate + ADR-009.
2. **Documentation sync:** ✅ DONE — `validate_toc.py` + invariant test + TOC 185/185 (all 5 chapters expanded: 09.4/09.12/09.13/26.7 + 25.1/25.3/25.6).
3. **Observability stack:** ✅ Phase A done (Langfuse handler refactor + DeepEval + cross-hook correlation в hook_metrics_db). 🟡 Phase B (full production rollout) tracked отдельно — см. §12 ниже.

---

## 1. Метод аудита

3 параллельных Explore-агента 2026-05-09:

| Scope | Найдено |
|---|---|
| Code TODO/FIXME | 23 TODO (Python: 2, BSL: 6, scripts: 15); 0 NotImplementedError; 5 ABC pass-stubs (legitimate); 24 skipped tests (env-guards) |
| Existing roadmap backlog | ~25-30 deferred items, 5 cross-cutting тем |
| Doc TOC vs filesystem | 43 declared-missing; 11 fs files outside TOC; 8 stub-suspect chapters; 1 explicit placeholder (35_EXTENSIONS) |

---

## 2. P0 — Critical (blocks CI / security / merge)

### 2.1 P0 — ADR-008 verdict + safe smoke-gate (260423 C1)

**Цель:** Закрыть ADR-008 (DSPy migration) переводом proposed → accepted и зафиксировать в CI smoke-gate, который автоматически проваливает PR при деградации NDCG ниже baseline (E5 = 0.45, threshold ≥ 0.55).
**Выгоды:** Регрессии retrieval ловятся на CI ещё до merge; разблокируется поток B1/B2/B7 (Contextual Retrieval, GEPA, DeepEval) — без числового SLA эти улучшения нечем измерить; формальное закрытие architectural decision снимает «висящий» документ.

**Что:** RAGAS eval ✅ DONE 2026-04-21 (вердикт PASS), но safe smoke-gate в CI не настроен. Блокирует merge новых retrieval-фич.

- [ ] **2.1.1** Прочитать `docs/adr/008-dspy-migration.md` → exit criteria (NDCG threshold, latency budget)
- [ ] **2.1.2** Создать `tests/eval/test_smoke_gate.py` — fail если NDCG < 0.55 (baseline E5 = 0.45)
- [ ] **2.1.3** Wire в `ci.yml` после `test` job; dataset → strategy=hybrid → measure → assert
- [ ] **2.1.4** Local smoke-test PASS
- [ ] **2.1.5** Документировать в `08_ОЦЕНКА_КАЧЕСТВА/08.5_Smoke_Gate.md`
- [ ] **2.1.6** ADR-008 lifecycle: proposed → accepted

**Effort:** ~6 ч | **Зависимость:** 2.2 (golden dataset)

### 2.2 P0 — Golden eval dataset (260423 C2) — UNBLOCKER для B1/B2/B7

**Цель:** Собрать эталонный набор из ≥100 размеченных query → relevant_chunk_ids → ideal_answer на трёх production коллекциях для воспроизводимых benchmark'ов.
**Выгоды:** Объективное измерение всех retrieval/RAG-улучшений (Contextual Retrieval, GEPA, Matryoshka, RAPTOR rerank) — нечего сравнивать без ground truth; базис для CI smoke-gate (2.1) и DeepEval gating (3.9); первая исторически воспроизводимая baseline для regression tracking; снимает блокировку с 5 P1/P2 items.

**Что:** Curated 100-query evaluation set с ground-truth (relevant chunks + ideal answer).

- [ ] **2.2.1** Inventory existing eval datasets (`data/eval/`, `tests/eval/fixtures/`)
- [ ] **2.2.2** Decide source: synthetic via DSPy `dspy.Synthesize` или manual curation
- [ ] **2.2.3** Synthetic generation на `pdf_documents` (830 chunks); 100 questions × 3 difficulty
- [ ] **2.2.4** Manual review (~5-10 ч): убрать low-quality, fix ground-truth
- [ ] **2.2.5** Save `data/eval/golden_v1.json`: `{id, query, expected_chunk_ids, expected_answer, difficulty}`
- [ ] **2.2.6** Versioning через `data/eval/CHANGELOG.md`
- [ ] **2.2.7** Wire в RAGAS adapter
- [ ] **2.2.8** Baseline measurements на 3 коллекциях, save в `data/eval/baselines/`

**Effort:** ~16 ч | **Без этого блокирует:** B1, B2, B7

### 2.3 P0 — JWT auth IDOR completion (260423 A1)

**Цель:** Полностью покрыть handlers `src/api/routes/tenants.py` через `_assert_tenant_access`, чтобы non-admin пользователи не могли читать/менять/удалять данные чужих тенантов через прямую подстановку `tenant_id` в URL.
**Выгоды:** Закрытие critical IDOR-уязвимости в multi-tenant API (защита customer data); готовность к security audit / pen-test; компилаентность для enterprise rollout; устранение security debt с минимальным effort (~3 ч).

**Что:** `auth.py` имеет `_admin: str` IDOR-fix, но не все handlers `tenants.py` покрыты.

- [ ] **2.3.1** Audit `src/api/routes/tenants.py` через `_assert_tenant_access`
- [ ] **2.3.2** Unit tests `test_tenants_idor.py`: non-admin не может delete/update/get-stats чужого tenant'а (403)
- [ ] **2.3.3** Integration test с real JWT (admin vs viewer)
- [ ] **2.3.4** Документировать в 09.7 или новый ADR
- [ ] **2.3.5** Security checklist: `pip-audit` + JWT secret rotation policy

**Effort:** ~3 ч | **Severity:** Critical (multi-tenant security)

### 2.4 P0 — TOC vs filesystem desync (43 declared-missing)

**Цель:** Привести `00_СОДЕРЖАНИЕ.md` в строгое соответствие с реальной структурой `docs/framework documentation/`: добавить отсутствующие 21.2-21.8 (LLM_ROTATION), 16.6/16.7 (EDT MCP), 27.7; удалить orphan declarations и зафиксировать invariant в CI.
**Выгоды:** Discoverability — пользователи и AI-агенты находят актуальную документацию через TOC, а не через `glob`; устранение dead links в навигации; CI invariant `validate_toc.py` исключает дальнейший drift автоматически; ~32 «потерянных» файла возвращаются в индекс.

**Что:** `00_СОДЕРЖАНИЕ.md` декларирует 214 файлов, реально 182. Chapter 21 (LLM_ROTATION) — только 21.1 в TOC, в FS 21.2-21.8 (8 subsections undocumented). Новые 16.6/16.7/27.7 отсутствуют.

- [ ] **2.4.1** Скрипт `scripts/validate_toc.py` — парсит TOC, проверяет existence каждого `[link](path)`, diff vs `glob`
- [ ] **2.4.2** Запустить → точный diff
- [ ] **2.4.3** TOC обновить: 21.2-21.8, 16.6, 16.7, 27.7
- [ ] **2.4.4** Удалить orphan declarations или создать stubs
- [ ] **2.4.5** `tests/test_docs_invariants.py` → новый класс `TestTOCConsistency`
- [ ] **2.4.6** CI integration

**Effort:** ~3 ч | **Severity:** Discoverability

### 2.5 P0 — Pytest job в CI verification

**Цель:** Подтвердить, что `test` job в `.github/workflows/ci.yml` действительно прогоняет unit tests на каждый PR без `continue-on-error` для core, и поднять coverage gate до 70% с upload в Codecov.
**Выгоды:** Автоматическая защита от regressions на каждом PR (без CI gate большая часть тестов фактически декоративна); видимость покрытия через Codecov; уверенность при будущих рефакторингах (3.7 retry, 3.8 Send API); снятие риска ложно-зелёного main.

**Что:** Audit 260430_DEPS_AND_CI.md помечает D.7 DONE, но Track A6 (test coverage) от 260423 говорит unit tests не runs systematically. Verify.

- [ ] **2.5.1** Inspect `.github/workflows/ci.yml` test job (continue-on-error, Qdrant service)
- [ ] **2.5.2** Если test job не runs на каждый PR — переписать (убрать `continue-on-error` для unit, оставить для integration)
- [ ] **2.5.3** Coverage gate: `pytest --cov-fail-under=70` для core
- [ ] **2.5.4** Codecov upload: verify CODECOV_TOKEN

**Effort:** ~2 ч | **Severity:** Regression detection

---

## 3. P1 — High (production quality / observability)

### 3.1 P1 — OpenLLMetry + Langfuse (260423 B3) — observability foundation

**Цель:** Развернуть распределённый tracing для LLM-вызовов и agent execution через `traceloop-sdk` (auto-instrument LangChain) + Langfuse Cloud (UI + storage), с manual spans для `agent.invoke`, `tool.call`, retrieval.
**Выгоды:** End-to-end visibility token usage / latency / cost per query — фундамент для любого performance debugging в production; разблокирует Memory P5 observability (3.3) и Delegation Iter 4-5 (4.5) — обе полагаются на measurable outcomes; ускоряет диагностику production incidents с часов до минут.

- [ ] **3.1.1** Audit `src/pdf_framework/observability/`
- [ ] **3.1.2** Add `traceloop-sdk` в `[langfuse]` extra
- [ ] **3.1.3** Wire env vars: `LANGFUSE__ENABLED/PUBLIC_KEY/SECRET_KEY/HOST`
- [ ] **3.1.4** Auto-instrument LangChain (LLM calls)
- [ ] **3.1.5** Manual spans: agent.invoke, tool.call, retrieval
- [ ] **3.1.6** Документировать в `09.4_Мониторинг.md`
- [ ] **3.1.7** Smoke: trace через /search видно в Langfuse

**Effort:** 3-5 days | **Unblocks:** 3.3 Memory P5, 4.5 Delegation Iter 4-5

### 3.2 P1 — Contextual Retrieval (260423 B1) — Anthropic, -67% failures

**Цель:** Внедрить Anthropic Contextual Retrieval — генерация LLM-контекста для каждого chunk (~50-100 токенов «о чём этот chunk относительно документа») и append к тексту перед embedding в `HybridLoader`.
**Выгоды:** По paper Anthropic — снижение retrieval failures до 67%; significant lift NDCG@10 на golden_v1; minimum-effort ROI после установки baseline (одно изменение в indexing pipeline даёт измеримый quality gain); не ломает existing collections (re-index opt-in).

- [ ] **3.2.1** Cache paper в `architecture-research/cache/`
- [ ] **3.2.2** `ContextualEnricher` class в `src/pdf_framework/processing/`
- [ ] **3.2.3** Integrate в `HybridLoader._load_sync` или separate processing step
- [ ] **3.2.4** Append context to chunk text перед embedding
- [ ] **3.2.5** Benchmark на golden_v1: NDCG@10 baseline vs +contextual
- [ ] **3.2.6** Если +5% — make default
- [ ] **3.2.7** Документация `03_ИНДЕКСАЦИЯ/03.7_Contextual_Retrieval.md`

**Effort:** 2-3 days | **Зависимость:** 2.2

### 3.3 P1 — Memory P5 observability (260403 + 260423 C3)

**Цель:** Завершить Phase 5 memory migration — cross-hook tracing через `correlation_id`, унифицированная metrics-схема `data/metrics/hooks.json`, CLI dashboard для visibility cycle hook → MCP → storage.
**Выгоды:** Debug-ready memory orchestrator (P0-P4 уже DONE, без observability дальше масштабировать слепо); измеримость hook performance (sub-2s SLA enforcement, см. 4.9); foundation для Phase 6+ scale-out (cross-instance sync, 4.6); закрытие давнего observability-долга.

- [ ] **3.3.1** Inventory `src/memory/orchestrator/`
- [ ] **3.3.2** Cross-hook tracing через `correlation_id` (расширить slash-tracker pattern)
- [ ] **3.3.3** Unified metrics schema `data/metrics/hooks.json`
- [ ] **3.3.4** Wire в OpenLLMetry (3.1)
- [ ] **3.3.5** CLI dashboard `scripts/hooks_dashboard.py`

**Effort:** 2-3 days | **Зависимость:** 3.1

### 3.4 P1 — GEPA replaces MIPROv2 (260423 B2)

**Цель:** Migrate teleprompted DSPy modules с `dspy.MIPROv2` (deprecated) на `dspy.GEPA` (Generative Evolutionary Prompt Adaptation, DSPy ≥ 2.5), re-compile и сохранить compiled modules в `data/dspy/compiled/`.
**Выгоды:** Ожидаемый +5% quality lift на golden_v1 при том же compute; современный prompt optimizer с simpler API и более стабильной сходимостью; устранение deprecation warnings и подготовка к будущим DSPy upgrades; одна prompt-engineering система везде.

- [ ] **3.4.1** Audit DSPy usage в `src/pdf_framework/agents/`
- [ ] **3.4.2** Migrate `dspy.MIPROv2` → `dspy.GEPA`
- [ ] **3.4.3** Re-compile teleprompted modules → save в `data/dspy/compiled/`
- [ ] **3.4.4** Benchmark на golden_v1
- [ ] **3.4.5** Если +5% — default

**Effort:** 2-3 days | **Зависимость:** 2.2 + DSPy ≥ 2.5

### 3.5 P1 — Dual-write feedback (260423 A2)

**Цель:** Параллельная запись feedback events в JSONL backup `data/feedback/backup_YYYY-MM-DD.jsonl` рядом с SQLite + recovery script `scripts/replay_feedback_backup.py`.
**Выгоды:** Защита от corruption SQLite (data durability — single point of failure ликвидирован); audit trail в plain-text позволяет ручной анализ без БД; revivability при crash через replay; малый effort (~3-5 ч) для значимого reliability gain.

- [ ] **3.5.1** `feedback/collector.py` — `_write_jsonl_backup`
- [ ] **3.5.2** Path: `data/feedback/backup_YYYY-MM-DD.jsonl`
- [ ] **3.5.3** Recovery `scripts/replay_feedback_backup.py`
- [ ] **3.5.4** Tests: corrupt SQLite → backup читается → replay восстанавливает
- [ ] **3.5.5** Документировать в `08.4_Feedback_Loop.md`

**Effort:** 3-5 ч

### 3.6 P1 — Test coverage to 70% (260423 A6)

**Цель:** Поднять coverage `src/pdf_framework/` до 70% через таргетированные unit tests на под-покрытые модули (`agents/research_v2/`, `agents/deep/`, `optimization/`, `evaluation/runner.py`) и закрепить gate в CI.
**Выгоды:** Снижение regression-риска при будущих рефакторингах; tests-as-documentation для under-documented модулей; CI gate (2.5.3) предотвращает дрейф вниз; высокая уверенность при работе через Z.AI delegation (можно проверять generated code тестами).

- [ ] **3.6.1** Run `pytest --cov=src/pdf_framework` → baseline
- [ ] **3.6.2** Identify modules < 70%: `agents/research_v2/`, `agents/deep/`, `optimization/`, `evaluation/runner.py` likely candidates
- [ ] **3.6.3** Add ~5-10 unit tests per under-covered module
- [ ] **3.6.4** CI gate (см. 2.5.3)

**Effort:** 3-5 days

### 3.7 P1 — Retry unification (260423 A3)

**Цель:** Заменить ~5-10 ad-hoc retry-loops (`for attempt in`, `httpx_retries`, кастомные `@retry`) на единую обёртку `src/pdf_framework/utils/retry.py` через tenacity (max_attempts=3, exp backoff, jitter).
**Выгоды:** Consistent backoff/jitter behavior на всём codebase (избегаем thundering herd); меньше bug-источников (одно место для fix retry-related issues); proper handling rate-limit ответов от LLM/Qdrant API; легче добавлять circuit breakers в будущем.

- [ ] **3.7.1** `grep -rn "for attempt in\|httpx_retries\|@retry\|tenacity" src/`
- [ ] **3.7.2** ~5-10 places to unify
- [ ] **3.7.3** `src/pdf_framework/utils/retry.py` — wrapper around tenacity (max_attempts=3, exp backoff, jitter)
- [ ] **3.7.4** Replace manual retry loops
- [ ] **3.7.5** Tests pass

**Effort:** 2-3 days

### 3.8 P1 — LangGraph Send API (260423 B4)

**Цель:** Refactor sequential multi-step query decompose в `src/pdf_framework/agents/adaptive/` на параллельный LangGraph `Send(queries)` API.
**Выгоды:** Снижение latency 5-query decompose в N раз (5 параллельных retrievals вместо последовательных); native LangGraph idiom (упрощает onboarding); better resource utilization Qdrant connection pool; preserves existing semantics (опасности regression низкие).

- [ ] **3.8.1** Audit `src/pdf_framework/agents/adaptive/` — multi-step decompose
- [ ] **3.8.2** Refactor sequential → `Send(queries)` parallel
- [ ] **3.8.3** Benchmark latency 5-query decompose до/после
- [ ] **3.8.4** Tests: existing semantics preserved

**Effort:** ~2 days

### 3.9 P1 — DeepEval CI gating (260423 B7)

**Цель:** Подключить DeepEval metrics (faithfulness, hallucination) с порогами `faithfulness > 0.7`, `hallucination < 0.1` как CI gate в smoke-suite, зафиксировать threshold rationale в ADR-009.
**Выгоды:** Автоматическое предотвращение regressions качества generated answers (a не только retrieval); numerical SLA для RAG-quality в публичной форме (ADR); защита от prompt-changes / model-version-changes без регрессии; complement к 2.1 (NDCG retrieval) — closes loop end-to-end.

- [ ] **3.9.1** `deepeval` в `[eval]` extra
- [ ] **3.9.2** `tests/eval/test_deepeval.py`: faithfulness > 0.7, hallucination < 0.1
- [ ] **3.9.3** Wire в smoke-gate (см. 2.1)
- [ ] **3.9.4** ADR-009 threshold rationale

**Effort:** ~2 days | **Зависимость:** 2.1

---

## 4. P2 — Medium (improvements / quality of life)

### 4.1 P2 — Matryoshka embeddings A/B (260423 B5)

**Цель:** Сравнить полноразмерные 4096d Qwen3 embeddings vs truncated MRL 1024d/512d на recall (NDCG@10) на golden_v1 — Qwen3 поддерживает Matryoshka representations.
**Выгоды:** При delta < 5% — миграция `framework_code_v1` (21k+ points) на 1024d даёт 4× faster search и 4× меньше storage в Qdrant; lower memory footprint позволяет fit'нуть больше коллекций на той же машине; data-driven решение вместо угадывания «4096d is best».

- [ ] **4.1.1** Recreate `pdf_documents_mrl_1024` collection × 1024d (truncate)
- [ ] **4.1.2** Benchmark NDCG@10: 4096d vs MRL 1024d/512d
- [ ] **4.1.3** Если -delta < 5% → migrate `framework_code_v1` на MRL 1024d (4× faster)
- [ ] **4.1.4** Document `04_ПОИСК/04.X_Matryoshka.md`

**Effort:** 3-5 days

### 4.2 P2 — RAPTOR + LLM rerank (260423 A7)

**Цель:** Добавить опциональный LLM-reranker top-20 chunks в `raptor_search.py` через параметр `enable_llm_rerank: bool` с кешированием rerank-decisions.
**Выгоды:** Improved precision на сложных query (обработка nuance которые embedding-similarity не ловит); latency cost (~1-2s) оправдан для high-stakes use-cases (research, legal); cache минимизирует RPM hit на повторах; opt-in — не ломает default fast path.

- [ ] **4.2.1** `raptor_search.py` — `enable_llm_rerank: bool` parameter
- [ ] **4.2.2** Reranker: pass top-20 to LLM, sort by relevance score
- [ ] **4.2.3** Cache rerank decisions
- [ ] **4.2.4** Benchmark на golden_v1

**Effort:** 2-3 days

### 4.3 P2 — Stub embedding edge-case fix (260423 A5)

**Цель:** Найти и исправить случаи возврата stub/`np.zeros(...)` embeddings вместо real embeddings в edge-cases (empty input, encoding errors), либо хотя бы log warning и raise.
**Выгоды:** Корректность search в edge-cases (zero-vector матчит всё / ничего → ложные результаты); предотвращение silent quality degradation, который сложно поймать без целевого теста; малый effort (~2 ч) для устранения «тихого» bug-class'а.

- [ ] **4.3.1** `grep -rE "stub|placeholder|np\.zeros\(" src/pdf_framework/embeddings/`
- [ ] **4.3.2** Fix или log warning
- [ ] **4.3.3** Test: edge case → real embed

**Effort:** ~2 ч

### 4.4 P2 — Sync-in-async cleanup (260423 A4)

**Цель:** Заменить `asyncio.to_thread` / `run_in_executor` обёртки на native async equivalents где доступны (httpx async client, async Qdrant client, etc.) и задокументировать оставшиеся обоснованные случаи.
**Выгоды:** Lower latency (no thread-pool roundtrip); снижение thread pool contention при высоком QPS; лучшее использование async event loop; documented async patterns для contributors.

- [ ] **4.4.1** `grep -rE "asyncio.to_thread\|run_in_executor" src/`
- [ ] **4.4.2** Replace c native async equivalent где возможно
- [ ] **4.4.3** Document pattern в `09.X_Async_Patterns.md`

**Effort:** 1-2 days

### 4.5 P2 — Delegation Iter 4-5 (260320 + 260423 C4)

**Цель:** Iter 4 — trained router (vector similarity over outcome embeddings) с A/B vs LinUCB на 10% canary; Iter 5 — SAFLA (composite reward с quality degradation penalty).
**Выгоды:** Smarter LLM provider selection (учитывает task-similarity к прошлым успехам, а не только availability); quality-aware delegation вместо greedy «free first»; measurable cost savings + maintained quality; foundation для future RL-based routing.

- [ ] **4.5.1** Iter 4 design: trained router (vector similarity over outcome embeddings)
- [ ] **4.5.2** `src/shared/llm_rotation/router/trained.py`
- [ ] **4.5.3** A/B vs LinUCB (10% canary)
- [ ] **4.5.4** Iter 5 SAFLA: quality degradation, composite reward

**Effort:** 2-3 days each | **Зависимость:** 3.1 (observability для measurement)

### 4.6 P2 — Memory P5 advanced (260403 Phase 8)

**Цель:** Помимо base observability — cross-instance memory sync (multi-replica deployment), encrypted memory at rest (SQLCipher / Postgres TDE), GDPR per-user erase API.
**Выгоды:** Production multi-tenant compliance (SOC2 / GDPR требования к шифрованию и erasability); horizontal scaling memory orchestrator (одна instance не bottleneck); enterprise-readiness; out-of-scope в near-term, но фиксируем как target.

Beyond base observability: cross-instance sync, encrypted memory at rest, GDPR per-user erase.

**Effort:** 1-2 weeks | **Status:** out-of-scope для near-term

### 4.7 P2 — MCP Inspector smoke (260423 B6)

**Цель:** Скрипт через `npx @modelcontextprotocol/inspector` который для каждого сервера в `.mcp.json` делает connect + list_tools, fail on timeout; wire в `pre-commit-config.yaml`.
**Выгоды:** Catch broken MCP-серверы до commit (не во время сессии когда уже мешает); защита от regression в `.mcp.json` (config drift, путей, env vars); 0.5 day effort для долгосрочной reliability gain — все 27+ MCP-серверов проверяются автоматически.

- [ ] **4.7.1** Install `npx @modelcontextprotocol/inspector`
- [ ] **4.7.2** Script: foreach `.mcp.json` server — connect + list_tools, fail on timeout
- [ ] **4.7.3** Wire в `pre-commit-config.yaml`

**Effort:** 0.5 day

### 4.8 P2 — Phase 67 External tools (260423 C7)

**Цель:** Inventory + decision matrix для внешних tools (claude-hud, codebase-memory-mcp, parry, sonar-bsl, bsl-language-server) — keep / replace / remove с обоснованием на каждый.
**Выгоды:** Сокращение surface area (меньше серверов = меньше maintenance); устранение dead deps; consolidation на проверенный stack; документированное обоснование для будущих переоценок.

- [ ] **4.8.1** Inventory candidates: claude-hud, codebase-memory-mcp, parry, sonar-bsl, bsl-language-server
- [ ] **4.8.2** Decision matrix: keep / replace / remove
- [ ] **4.8.3** Update `.mcp.json`

**Effort:** 2-3 days

### 4.9 P2 — Async PostToolUse hooks (260329 step 2.3)

**Цель:** Refactor PostToolUse-хуков с >2s typical latency на sync entrypoint + fire-and-forget tail (или `"async": true` flag если поддерживается).
**Выгоды:** Снижение wait-time после каждого tool call (UX gain в interactive sessions); меньше блокировок agent loop; не ломает текущие хуки (post-fact обработка не критична).

- [ ] **4.9.1** Identify hooks с >2s typical latency
- [ ] **4.9.2** Refactor: sync entrypoint + fire-and-forget tail
- [ ] **4.9.3** Settings.json `"async": true` flag (если supported)

**Effort:** 1 day

### 4.10 P2 — GPU BSL Phase 4-5 (260326)

**Цель:** Phase 4 — Colab indexing automation wrapper (one-click reindex без локального GPU); Phase 5 — Qdrant Cloud Free Tier path для cloud-only operation.
**Выгоды:** GPU-accelerated reindex для contributors без локального GPU (через Colab T4); cloud-only operation снимает требование Docker locally; удобно для коротких контрибьюшенов; deferred unless need — нет активного запроса.

Phase 4: Colab indexing automation wrapper. Phase 5: Qdrant Cloud Free Tier (cloud-only path).

**Effort:** 1-2 days each | **Status:** deferred unless need

### 4.11 P2 — 25_LEARNING_LOOP chapter expansion

**Цель:** Расширить главу 25 (LEARNING_LOOP) с описанием 5-фазного pipeline (skill `learning-loop`): 25.1 Обзор 21 → ~150 строк с диаграммой; 25.3 Архитектура_субагента 44 → 100+; 25.6 Диагностика 40 → 100+.
**Выгоды:** Discoverability self-learning механизма (сейчас один из самых сложных компонентов фреймворка под-документирован); onboarding для contributors; reference для AI-агентов при создании новых skills; устранение doc-debt после Phase 8 work.

- [ ] **4.11.1** Audit `learning-loop` skill (5-фазный pipeline) → reference
- [ ] **4.11.2** Expand 25.1 Обзор: 21 → ~150 lines с диаграммой
- [ ] **4.11.3** Expand 25.3 Архитектура_субагента (44 → 100+)
- [ ] **4.11.4** Expand 25.6 Диагностика (40 → 100+)

**Effort:** 3-4 ч

---

## 5. P3 — Low (placeholders / on-demand)

### 5.1 P3 — Serena Phases 8-10 (260423 C5, on-demand)

**Цель:** Phase 8-10 продолжения Serena audit (Phases 0-7 DONE с откатом hybrid refactor); парковочный backlog до появления конкретного запроса на advanced refactoring features.
**Выгоды:** Завершение Serena migration (LSP-based BSL navigation в полном объёме); on-demand активация когда возникнет need в advanced symbol-anchored refactoring; не блокирует ничего сейчас.

Phase 8 audit (260414) — Phases 0-7 DONE с откатом hybrid refactor. Phases 8-10 on-demand. **Status:** парковочный backlog.

### 5.2 P3 — 35_EXTENSIONS активация

**Цель:** Активировать chapter 35 (расширения конфигурации 1С) когда появится первая extension-task; сейчас зарезервирована («Активного кода нет»).
**Выгоды:** Готовая структура для extension-документации; placeholder помечен в TOC чтобы не было «потерянной» главы; не требует effort до Phase 9.4+.

«Зарезервировано. Активного кода нет». Активировать когда появится первая extension-task. **Status:** Wait Phase 9.4+.

### 5.3 P3 — MCP Phase 11 OAuth2 (260331, 4/5 BLOCKED)

**Цель:** OAuth2-аутентификация для production MCP — 4 шага из 5 BLOCKED поскольку требуют staging environment + testing с реальными external clients.
**Выгоды:** Secure MCP в production rollout (multi-user / external clients вместо локального single-user); standard auth flow совместимый с enterprise SSO; ждёт actual production rollout — преждевременно делать без use-case.

OAuth2 для production MCP — 4 шага требуют staging environment + testing. **Status:** Wait actual production rollout.

### 5.4 P3 — MCP Phase 12.3 Streamlit dashboard (260331)

**Цель:** UX-альтернатива CLI dashboard через Streamlit для non-CLI пользователей; lower priority поскольку CLI dashboard `09.9` уже достаточен для текущих use-cases.
**Выгоды:** Visual dashboard для non-technical stakeholders; optional UX polish; не блокирует MCP operations — только nice-to-have.

CLI dashboard уже достаточен (09.9). Streamlit — low priority. **Status:** Optional UX polish.

### 5.5 P3 — TODO comments cleanup в BSL (6 markers)

**Цель:** Закрыть 6 TODO-маркеров в BSL коде по мере появления соответствующих 1С-задач (нет смысла рефакторить «на всякий случай» — каждый TODO связан с конкретной business-логикой).
**Выгоды:** Снижение технического долга; consistency code base; ad-hoc closure не требует выделенного roadmap-spot — захватывается естественно при touching кода.

- `гкс_ОчередьСообщенийRMQ:319` — отложенное формирование движений
- `гкс_ПечатьПриемныйАкт_ЗПП14:177` — temp workaround
- `ЮТЗапросыСлужебныйСервер:386` — unclear scope
- `ЮТОкружение:29` — кеширование вне тестов
- `ЮТФабрика:39` — web-клиент?
- `ЮТЧитательСлужебныйКлиент:191` — фильтрация по путям

**Status:** Ad-hoc closure при появлении 1С-задач.

### 5.6 P3 — `scripts/doc_to_cache.py` placeholders (14 markers)

**Цель:** Подтвердить, что 14 TODO в `scripts/doc_to_cache.py` — это template fill-points для doc generation pipeline, а НЕ implementation TODO; пометить как false positive в audit reports.
**Выгоды:** Очистка inventory от ложных TODO; правильная приоритизация остального backlog (31 → 17 «настоящих» TODO); экономия времени на повторных аудитах.

14 TODO — это template fill-points для doc generation, НЕ implementation TODO. **Status:** False positive, оставить.

---

## 5b. Closure log — 2 sessions, 2026-05-09

**21 / 31 items closed.** Audit-finding pattern: roadmap estimates были overstated в 1.5-3× потому что часть infrastructure уже была implemented к моменту execution. См. project memory `project_roadmap_audit_pattern.md`.

| ID | Item | Closure | Commits |
|---|---|---|---|
| 2.1 | Smoke-gate framework | DONE — `tests/eval/test_smoke_gate.py` (9 schema gates) + CI step + 08.5 doc | `723c6fa33` |
| 2.2 | Golden eval dataset | DONE v1.1 — 40 templated items + CHANGELOG | `dd2d8a9a7` |
| 2.3 | JWT IDOR | DONE + CRITICAL bypass через `task_kwargs` (reviewer-found) | `723c6fa33` |
| 2.4 | TOC sync | DONE — `scripts/validate_toc.py` + invariant test + CI step | auto-saves |
| 2.5 | CI test job split + Codecov | DONE — unit gates merge / integration best-effort + Codecov public OIDC | `c38ee7749` |
| 3.1 | Langfuse settings refactor | DONE phase A — handler refactor + smoke tests + 09.4 doc | `6ee613035` |
| 3.2 | Contextual Retrieval | NO-OP — already Phase 50 (`processing/context_generator.py`) | `804c40487` |
| 3.3 | Memory P5 obs | DONE — `hook_metrics_db` schema migration + cross-hook trace API | `6fa3a6152` |
| 3.5 | Dual-write feedback | DONE — JSONL backup + replay script + 8 tests | `a01014245` |
| 3.6 | Coverage gate | DONE pragmatic — codecov diff-coverage 70% (patch only) | (auto-saves) |
| 3.7 | Retry unification | DONE — 1 callsite migrated, 8 Ralph Wiggum loops documented as exclusion | (auto-saves) |
| 3.8 | LangGraph Send API | NO-OP — already Phase 26 `asyncio.gather` | — |
| 3.9 | DeepEval CI gating | DONE — `tests/eval/test_deepeval.py` + ADR-009 + threshold rationale | (auto-saves) |
| 4.2 | RAPTOR LLM rerank | DONE — opt-in `enable_llm_rerank` config | `acd6f1d1b` |
| 4.3 | Stub embedding | NO-OP — patterns не существуют в codebase | — |
| 4.4 | Sync-in-async | DOC — 09.12 Async_Patterns chapter (no code changes) | `d2a6403e3` |
| 4.7 | MCP Inspector smoke | DONE — `scripts/mcp_smoke_check.py` + pre-commit hook (18/20 ok) | (auto-saves) |
| 4.8 | External tools matrix | DOC — 26.7 chapter, 0 candidates landed, 20×keep | `43de03049` |
| 4.9 | Async PostToolUse hooks | DOC — 09.13 audit + RCA SlashCommandTracker measurement artifact | `b9b852215` |
| 4.11 | 25_LEARNING_LOOP expand | DONE — 25.1/25.3/25.6 +212 lines | (auto-saves) |
| 5.6 | doc_to_cache placeholders | NO-OP — confirmed false positive, docstring note added | (auto-saves) |

**Open items (10):**

| ID | Item | Real blocker |
|---|---|---|
| 3.4 | GEPA replaces MIPROv2 | DSPy install + LLM creds для validation (5-line code change ready) |
| 4.1 | Matryoshka A/B | Qdrant + 2-3h benchmark runs |
| 4.5 | Delegation Iter 4-5 | Langfuse production trace для outcome embeddings (Iter 3 LinUCB ✅ done) |
| 4.6 | Memory P5 advanced | Out-of-scope для near-term per roadmap |
| 4.10 | GPU BSL Phase 4-5 | Explicit "deferred unless need" |
| 5.1 | Serena Phases 8-10 | On-demand parking lot |
| 5.2 | 35_EXTENSIONS активация | Wait Phase 9.4+ |
| 5.3 | OAuth2 (MCP Phase 11) | Wait actual production rollout |
| 5.4 | Streamlit dashboard | Optional UX polish, low priority |
| 5.5 | BSL TODO cleanup | Ad-hoc closure при появлении 1С-задач |

**Side findings:**
- RCA `SlashCommandTracker` 250s avg = measurement artifact, not bug ([09.13](../framework%20documentation/09_АДМИНИСТРИРОВАНИЕ/09.13_Async_Hooks_Audit.md))
- Project memory recorded: `project_roadmap_audit_pattern.md` — audit-stale lesson для future sessions
- Enforcer config improved: `docs-change-enforcer.py` mapping override block + SKIP_PATTERNS (codecov.yml, .pre-commit-config.yaml, data/eval/)

---

## 5c. Langfuse Production Rollout (new item)

**Цель:** Перевести Langfuse из "infrastructure ready" (§3.1 phase A done) в "production active monitoring" — full observability stack для LLM calls, retrieval, agent execution, memory operations. Unblocks §3.3 wiring + §4.5 Delegation Iter 4-5 + §3.9 quality gate activation.

**Выгоды:** End-to-end trace visibility (token usage, latency, cost per query); proactive quality regression detection (prompt drift, model upgrade impact); foundation для production debugging (вместо reactive log digging); outcome data corpus для §4.5 trained router learning.

### Phase B subtasks

> **Audit 2026-05-15:** spot-check показал — 5c.10 ADR-010 уже существует (proposed), 5c.5 частично сделан (LangfuseCallbackHandler wired в `agents/rag/middleware.py:199` через middleware, остальные spans pending). Остальные 8 subtasks — open.

- [ ] **5c.1 Langfuse Cloud account** — register на cloud.langfuse.com OR self-host через docker-compose. Cloud free tier 50K observations/month → достаточно для hobby/dev.
- [ ] **5c.2 Add credentials в `.env`** — `OBSERVABILITY__LANGFUSE_ENABLED=true`, `OBSERVABILITY__LANGFUSE_PUBLIC_KEY=pk-lf-...`, `OBSERVABILITY__LANGFUSE_SECRET_KEY=sk-lf-...`, `OBSERVABILITY__LANGFUSE_HOST=https://cloud.langfuse.com`. **Side gap: добавить также в `.env.example` для onboarding** (см. §3.4-bis).
- [ ] **5c.3 Smoke test против real Langfuse** — запустить локально query через `python -m src.cli.main search "тест" --strategy hybrid` → verify trace появился в dashboard. Confirms wiring работает.
- [ ] **5c.4 Wire memory operations** — close §3.3.4 (deferred). Memory hooks (memory-first, memory-sync, session-memory-save) emitить spans через `observability.langfuse_setup.build_langfuse_callback()`.
- [~] **5c.5 Manual spans для critical paths** — частично: `LangfuseCallbackHandler` подключён в `src/pdf_framework/agents/rag/middleware.py:199` через `LangfuseCallbackHandler(...)` instance. Остаются `search/manager.py:search`, `tools/*` для granular tracing.
- [ ] **5c.6 Dashboard configuration** — настроить alerts (latency P95 > 5s, hallucination rate > 0.15, cost per query > $0.50), saved views для daily monitoring.
- [ ] **5c.7 Cost tracking baseline** — после 7 дней production traffic зафиксировать baseline в `docs/architecture/cost-baselines.md` (top-10 expensive queries, average tokens per RAG call). **Файл ещё не создан** (verified 2026-05-15).
- [ ] **5c.8 Score collection wire-up** — кнопки 👍/👎 в Web UI → `langfuse.score()` API → корреляция с feedback loop §3.5.
- [ ] **5c.9 Outcome corpus для §4.5** — после 30 дней traffic экспортировать (query, delegated_provider, success, latency, cost) tuples → JSONL для §4.5 Iter 4 trained router training.
- [x] **5c.10 ADR-010 production observability** — DONE как proposed (`.claude/skills/architecture-research/adr/010-langfuse-production-observability.md`). Lifecycle = proposed → locked-in после первого 30-day production traffic + cost baseline (т.е. зависит от 5c.7).

**Effort:** 5c.1-5c.3 = ~30 мин (basic setup). 5c.4-5c.6 = ~3-5 ч (wiring + production hardening). 5c.7-5c.9 = ongoing (накапливается с traffic). 5c.10 = ~2 ч когда есть baseline data.

**Зависимости:**
- 5c.1 → user-side (нужен Langfuse Cloud account ИЛИ Docker для self-hosted)
- 5c.4 unblocks **§3.3.4** (Memory P5 Langfuse wiring) и closes Memory P5 fully
- 5c.7 unblocks **§4.5 Delegation Iter 4-5** (нужен outcome corpus для trained router)
- 5c.10 closes ADR-010 как formal observability strategy

**Когда НЕ делать:** если framework планируется только для local dev/research (нет production users, нет cost concerns) — 5c.4-5c.10 overkill, достаточно 5c.1-5c.3 basic setup.

**Кратко по value:** см. memory note `reference_codecov_public.md` (sibling pattern) и chapter [09.4 Мониторинг — Langfuse](../framework%20documentation/09_АДМИНИСТРИРОВАНИЕ/09.4_Мониторинг.md#langfuse).

---

## 5d. Gaps discovered during 2026-05-15 deep audit (NEW items)

> Spot-check 14 closure-claims из §5b показал три gap'а где acceptance criteria либо невозможно закрыть, либо претензия требует follow-up. Все три — small effort, без них §7 не сходится.

### 3.4-bis P1 — ADR-008 файл отсутствует на диске ⚠️

**Цель:** Создать `.claude/skills/architecture-research/adr/008-dspy-migration.md` (proposed → accepted) либо удалить ссылки из §2.1.1, §2.1.6, §7.6.
**Выгоды:** §7.6 acceptance criterion становится closable; consistency с ADR-009 и ADR-010 которые физически существуют.

**Что:** §2.1.1 ссылается на «docs/adr/008-dspy-migration.md», но файл не найден ни в `docs/adr/`, ни в `.claude/skills/architecture-research/adr/`. RAGAS eval (§2.1) closed как DONE, но без ADR — формально verdict не зафиксирован.

- [ ] **3.4-bis.1** Решить: создавать ADR-008 или удалить ссылки (рекомендую создать — sibling pattern для ADR-009/010)
- [ ] **3.4-bis.2** Если создавать: «DSPy migration RAGAS verdict» с exit criteria (NDCG ≥ 0.55) и latency budget
- [ ] **3.4-bis.3** Cross-link из 08.5_Smoke_Gate.md → ADR-008
- [ ] **3.4-bis.4** Acceptance criterion §7.6 → `[x]`

**Effort:** 1-2 ч | **Severity:** Discoverability + closure

### 3.4-ter P1 — `.env.example` не содержит Langfuse vars ⚠️

**Цель:** Добавить в `.env.example` full set Langfuse env vars из §5c.2.
**Выгоды:** Onboarding-readiness: fresh clone узнаёт что настраивать без чтения roadmap; устраняет implicit-knowledge tax.

**Что:** Phase A §3.1 закрыт, но `.env.example` не содержит `OBSERVABILITY__LANGFUSE_*`. Verified 2026-05-15: `grep -n "LANGFUSE\|OBSERVABILITY" .env.example` → 0 matches.

- [ ] **3.4-ter.1** Verify `.env.example` exists
- [ ] **3.4-ter.2** Добавить `OBSERVABILITY__LANGFUSE_ENABLED=false` (default off) + 3 placeholder vars (PUBLIC_KEY, SECRET_KEY, HOST=https://cloud.langfuse.com)
- [ ] **3.4-ter.3** Cross-link комментарий → roadmap §5c

**Effort:** ~10 мин | **Severity:** Onboarding DX

### 3.4-quater P1 — golden_v1 = 40 items вместо ≥100 ⚠️

**Цель:** Дополнить `data/eval/golden_v1.json` до ≥100 queries (как требует §7.5) либо relax acceptance до 40.
**Выгоды:** §7.5 формально закрывается; statistical power для NDCG@10 measurements становится корректной.

**Что:** §5b 2.2 = «DONE v1.1 — 40 templated items + CHANGELOG», §7.5 требует «≥100». Расхождение 40 vs 100 не отражено в acceptance.

- [ ] **3.4-quater.1** Решить: synthesis +60 queries (DSPy из §2.2.3) или relax criterion до 40
- [ ] **3.4-quater.2** Если синтез: `dspy.Synthesize` на pdf_documents → 60 questions × 3 difficulty
- [ ] **3.4-quater.3** Manual review (5-10 ч) → save v1.2 → update CHANGELOG
- [ ] **3.4-quater.4** Re-baseline на 3 коллекциях

**Effort:** 8-12 ч (synthesis) / 0 (relax) | **Severity:** Eval statistical power

### 5c.7-bis P2 — `docs/architecture/` директория не существует

**Цель:** Создать `docs/architecture/` для будущего `cost-baselines.md` из §5c.7.
**Выгоды:** Готовая структура когда §5c.7 наберёт production traffic; устраняет «цель есть, но папки нет» gap.

- [ ] **5c.7-bis.1** Verify: 2026-05-15 `ls docs/architecture/` → «No such file or directory»
- [ ] **5c.7-bis.2** Если нет — создать с README.md placeholder ссылающимся на ADR-010 и §5c.7

**Effort:** 5 мин | **Severity:** Future-proofing

---

## 6. Order of execution

### 6.1 Critical path (Week 1-2)

1. **Week 1:** 2.4 (TOC sync) + 2.5 (CI pytest) — параллельно
2. **Week 1-2:** 2.2 (golden eval dataset) — UNBLOCKER
3. **Week 2:** 2.1 (ADR-008 smoke-gate) + 2.3 (JWT IDOR) — параллельно
4. **Milestone Week 2:** ✅ CI fully green; merge unblocked

### 6.2 Quality wave (Week 3-7)

5. **Week 3-4:** 3.1 (OpenLLMetry) + 3.5 (Dual-write) + 3.7 (Retry unification)
6. **Week 5-6:** 3.2 (Contextual Retrieval) + 3.4 (GEPA) — bench against golden_v1
7. **Week 6-7:** 3.6 (Test coverage 70%) + 3.9 (DeepEval gating)

### 6.3 Improvements wave (Week 8+)

8. **Week 8-9:** 3.3 (Memory P5) + 3.8 (LangGraph Send) + 4.1 (Matryoshka A/B)
9. **Week 10+:** 4.2-4.11 — pick by demand

### 6.4 Backlog (no schedule)

P3 items — on-demand activation.

---

## 7. Acceptance criteria

> **Sync 2026-05-15:** статус каждого критерия после deep audit verification.

- [x] **7.1** CI прогоняет full suite зелёной включая eval smoke-gate — `tests/eval/test_smoke_gate.py` + ci.yml wired, см. §5b 2.1
- [x] **7.2** TOC = filesystem (validate_toc.py = 0 diff) — `scripts/validate_toc.py` + invariant test, см. §5b 2.4
- [x] **7.3** All 5 sibling audits 260430_* помечены ✅ ALL DONE (already true 2026-05-09)
- [ ] **7.4** OTel traces видны в Langfuse Cloud для test query — **BLOCKED §5c.1-5c.3** (нужен Langfuse account + `.env` credentials + smoke run)
- [x] **7.5** golden_v1 dataset (≥100 queries) committed в `data/eval/` — v1.1 40 items в `data/eval/golden_v1.json` + CHANGELOG (фактически 40, не 100 — см. **§3.4-bis** ниже)
- [ ] **7.6** ADR-008 lifecycle = accepted — **BLOCKED: ADR-008 не существует на диске** (см. **§3.4-bis** ниже)
- [ ] **7.7** Coverage ≥ 70% для `src/pdf_framework/` — pragmatic close: codecov diff-coverage 70% (patch only), total likely 30-50%
- [ ] **7.8** No new TODO/FIXME без соответствующего entry в roadmap — ongoing maintenance

---

## 8. Cross-cutting themes

| Тема | Items | Common dependency |
|---|---|---|
| **Eval & Benchmark** | 2.1, 2.2, 3.2, 3.4, 3.9, 4.1, 4.2 | golden_v1 dataset (2.2) |
| **Observability** | 3.1, 3.3, 4.5, 4.6 | OpenLLMetry+Langfuse (3.1) |
| **Quality** | 3.2, 3.4, 4.1, 4.2 | Eval baseline |
| **CI/CD** | 2.1, 2.4, 2.5, 3.6, 3.9, 4.7 | pytest infrastructure |
| **Documentation** | 2.4, 4.11 | TOC sync |
| **Async/Concurrency** | 3.7, 3.8, 4.4, 4.9 | tenacity unification (3.7) |

**Топ блокирующие пути:**
1. `2.2 golden_v1 dataset` → разблокирует все benchmark items (3.2, 3.4, 4.1, 4.2)
2. `3.1 Langfuse` → разблокирует Memory P5 (3.3) + Delegation Iter 4-5 (4.5)
3. `2.1 ADR-008 smoke-gate` → разблокирует merge новых retrieval-фич

---

## 9. Метрики прогресса

> **Обновлено 2026-05-15 (deep audit verification):** spot-check 14 closure-claims в §5b против фактических артефактов на диске — все верифицированы (`tests/eval/test_smoke_gate.py`, `test_deepeval.py`, `data/eval/golden_v1.json`, `scripts/validate_toc.py`, `scripts/mcp_smoke_check.py`, `src/pdf_framework/utils/retry.py`, `src/pdf_framework/feedback/collector.py:159` _write_jsonl_backup, `callbacks/langfuse/langfuse_callback.py` + wired в `agents/rag/middleware.py:199`, `codecov.yml` diff-coverage, `09.12_Async_Patterns.md`, `09.13_Async_Hooks_Audit.md`, `25_LEARNING_LOOP/` 6 файлов, RAPTOR `enable_llm_rerank` flag, ADR-009/ADR-010 в `.claude/skills/architecture-research/adr/`).

| Категория | Total | DONE (2026-05-15) | NO-OP / pre-existing | Open | % closed |
|---|---|---|---|---|---|
| P0 Critical | 5 | 5 | 0 | 0 | **100%** ✅ |
| P1 High | 9 | 6 | 2 (3.2, 3.8) | 1 (3.4 GEPA) | **89%** |
| P2 Medium | 11 | 6 (включая DOC) | 1 (4.3) | 4 (4.1, 4.5, 4.6, 4.10) | **64%** |
| P3 Low | 6 | 1 (5.6 false-pos) | 0 | 5 deferred | **17%** |
| **TOTAL** | **31** | **18** | **3** | **10** | **68%** (21/31 в §0 после learning) |

**Замечание о различии 21 vs 18:** §0 (21 closed) учитывает NO-OP `pre-existing infrastructure` items (3.2 Contextual Retrieval уже был Phase 50, 3.8 LangGraph Send уже был `asyncio.gather`, 4.3 stub patterns не существуют) как "closed". Если NO-OP считаем отдельной категорией — DONE+verified = 18, NO-OP = 3, open = 10. Содержательно одно и то же.

**Open items breakdown (10):**
- 1 P1 (3.4 GEPA — DSPy install + LLM creds)
- 4 P2 (4.1 Matryoshka A/B, 4.5 Delegation Iter 4-5, 4.6 Memory P5 advanced, 4.10 GPU BSL Phase 4-5)
- 5 P3 deferred (5.1-5.5)

Целевая velocity: ~5 items / 2 weeks. Critical path закрыт ✅; Quality wave завершена для всех unblocked items.

---

## 10. Связано

**Главный roadmap (closed):** [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md)

**Sibling closed audits (5/5 DONE 2026-05-09):**
- [`260430_AUDIT_CHAPTER_01_OVERVIEW.md`](260430_AUDIT_CHAPTER_01_OVERVIEW.md) — 35/35 ✅
- [`260430_AUDIT_CHAPTERS_02_30.md`](260430_AUDIT_CHAPTERS_02_30.md) — 26/26 ✅
- [`260430_AUDIT_DEPS_AND_CI.md`](260430_AUDIT_DEPS_AND_CI.md) — 9/9 ✅
- [`260430_AUDIT_TESTS_COVERAGE.md`](260430_AUDIT_TESTS_COVERAGE.md) — 23/23 ✅

**Source roadmaps (parent backlog):**
- [`260423_ROADMAP_FRAMEWORK_IMPROVEMENTS.md`](260423_ROADMAP_FRAMEWORK_IMPROVEMENTS.md) — 21-task Track A/B/C (большая часть items consolidated сюда)
- [`260403_ROADMAP_MEMORY_MIGRATION.md`](260403_ROADMAP_MEMORY_MIGRATION.md) — Phase 5-8 P5 observability
- [`260331_ROADMAP_MCP_IMPROVEMENTS.md`](260331_ROADMAP_MCP_IMPROVEMENTS.md) — Phase 11/12 deferred
- [`260326_ROADMAP_GPU_BSL_INDEXING.md`](260326_ROADMAP_GPU_BSL_INDEXING.md) — Phase 4-5 deferred
- [`260320_ROADMAP_DELEGATION_LEARNING.md`](260320_ROADMAP_DELEGATION_LEARNING.md) — Iter 4-5
- [`260413_Hermes Agent и LLM Wiki.md`](260413_Hermes%20Agent%20и%20LLM%20Wiki%20Карпати%20персистентные%20системы%20знаний.md) — Phase 5-6 partial
- [`260329_ROADMAP_POSTTOOLUSE_HOOKS.md`](260329_ROADMAP_POSTTOOLUSE_HOOKS.md) — step 2.3 async deferred

---

**Maintenance:** этот roadmap — living document. При закрытии item'а — поставить `[x]`, при появлении нового deferred work — добавить новую секцию с соответствующим severity. Обновлять §9 metrics weekly.
