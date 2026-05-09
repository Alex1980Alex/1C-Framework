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

| Severity | Count | Total effort (est) | Блокирует |
|---|---|---|---|
| 🔴 P0 | 5 | ~12 ч | CI merge, security |
| 🟠 P1 | 9 | ~7-10 дней | Production quality, observability |
| 🟡 P2 | 11 | ~3-4 недели | Improvements, polish |
| 🟢 P3 | 6 | ad-hoc | Long-term / on-demand |
| **TOTAL** | **31** | **~6-9 weeks elapsed (1 dev)** | — |

**Three critical paths:**
1. **CI/eval unblock:** C1 ADR-008 verdict + C2 golden eval dataset → разблокирует B1/B2/B7 quality benchmarks
2. **Documentation sync:** TOC vs filesystem 43 declared-missing files (Chapter 21 LLM_ROTATION 8 subsections undocumented)
3. **Observability stack:** B3 OpenLLMetry + Langfuse → unblocks Memory P5 (C3) + Delegation Iter 4-5 (C4)

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

**Что:** RAGAS eval ✅ DONE 2026-04-21 (вердикт PASS), но safe smoke-gate в CI не настроен. Блокирует merge новых retrieval-фич.

- [ ] **2.1.1** Прочитать `docs/adr/008-dspy-migration.md` → exit criteria (NDCG threshold, latency budget)
- [ ] **2.1.2** Создать `tests/eval/test_smoke_gate.py` — fail если NDCG < 0.55 (baseline E5 = 0.45)
- [ ] **2.1.3** Wire в `ci.yml` после `test` job; dataset → strategy=hybrid → measure → assert
- [ ] **2.1.4** Local smoke-test PASS
- [ ] **2.1.5** Документировать в `08_ОЦЕНКА_КАЧЕСТВА/08.5_Smoke_Gate.md`
- [ ] **2.1.6** ADR-008 lifecycle: proposed → accepted

**Effort:** ~6 ч | **Зависимость:** 2.2 (golden dataset)

### 2.2 P0 — Golden eval dataset (260423 C2) — UNBLOCKER для B1/B2/B7

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

**Что:** `auth.py` имеет `_admin: str` IDOR-fix, но не все handlers `tenants.py` покрыты.

- [ ] **2.3.1** Audit `src/api/routes/tenants.py` через `_assert_tenant_access`
- [ ] **2.3.2** Unit tests `test_tenants_idor.py`: non-admin не может delete/update/get-stats чужого tenant'а (403)
- [ ] **2.3.3** Integration test с real JWT (admin vs viewer)
- [ ] **2.3.4** Документировать в 09.7 или новый ADR
- [ ] **2.3.5** Security checklist: `pip-audit` + JWT secret rotation policy

**Effort:** ~3 ч | **Severity:** Critical (multi-tenant security)

### 2.4 P0 — TOC vs filesystem desync (43 declared-missing)

**Что:** `00_СОДЕРЖАНИЕ.md` декларирует 214 файлов, реально 182. Chapter 21 (LLM_ROTATION) — только 21.1 в TOC, в FS 21.2-21.8 (8 subsections undocumented). Новые 16.6/16.7/27.7 отсутствуют.

- [ ] **2.4.1** Скрипт `scripts/validate_toc.py` — парсит TOC, проверяет existence каждого `[link](path)`, diff vs `glob`
- [ ] **2.4.2** Запустить → точный diff
- [ ] **2.4.3** TOC обновить: 21.2-21.8, 16.6, 16.7, 27.7
- [ ] **2.4.4** Удалить orphan declarations или создать stubs
- [ ] **2.4.5** `tests/test_docs_invariants.py` → новый класс `TestTOCConsistency`
- [ ] **2.4.6** CI integration

**Effort:** ~3 ч | **Severity:** Discoverability

### 2.5 P0 — Pytest job в CI verification

**Что:** Audit 260430_DEPS_AND_CI.md помечает D.7 DONE, но Track A6 (test coverage) от 260423 говорит unit tests не runs systematically. Verify.

- [ ] **2.5.1** Inspect `.github/workflows/ci.yml` test job (continue-on-error, Qdrant service)
- [ ] **2.5.2** Если test job не runs на каждый PR — переписать (убрать `continue-on-error` для unit, оставить для integration)
- [ ] **2.5.3** Coverage gate: `pytest --cov-fail-under=70` для core
- [ ] **2.5.4** Codecov upload: verify CODECOV_TOKEN

**Effort:** ~2 ч | **Severity:** Regression detection

---

## 3. P1 — High (production quality / observability)

### 3.1 P1 — OpenLLMetry + Langfuse (260423 B3) — observability foundation

- [ ] **3.1.1** Audit `src/pdf_framework/observability/`
- [ ] **3.1.2** Add `traceloop-sdk` в `[langfuse]` extra
- [ ] **3.1.3** Wire env vars: `LANGFUSE__ENABLED/PUBLIC_KEY/SECRET_KEY/HOST`
- [ ] **3.1.4** Auto-instrument LangChain (LLM calls)
- [ ] **3.1.5** Manual spans: agent.invoke, tool.call, retrieval
- [ ] **3.1.6** Документировать в `09.4_Мониторинг.md`
- [ ] **3.1.7** Smoke: trace через /search видно в Langfuse

**Effort:** 3-5 days | **Unblocks:** 3.3 Memory P5, 4.5 Delegation Iter 4-5

### 3.2 P1 — Contextual Retrieval (260423 B1) — Anthropic, -67% failures

- [ ] **3.2.1** Cache paper в `architecture-research/cache/`
- [ ] **3.2.2** `ContextualEnricher` class в `src/pdf_framework/processing/`
- [ ] **3.2.3** Integrate в `HybridLoader._load_sync` или separate processing step
- [ ] **3.2.4** Append context to chunk text перед embedding
- [ ] **3.2.5** Benchmark на golden_v1: NDCG@10 baseline vs +contextual
- [ ] **3.2.6** Если +5% — make default
- [ ] **3.2.7** Документация `03_ИНДЕКСАЦИЯ/03.7_Contextual_Retrieval.md`

**Effort:** 2-3 days | **Зависимость:** 2.2

### 3.3 P1 — Memory P5 observability (260403 + 260423 C3)

- [ ] **3.3.1** Inventory `src/memory/orchestrator/`
- [ ] **3.3.2** Cross-hook tracing через `correlation_id` (расширить slash-tracker pattern)
- [ ] **3.3.3** Unified metrics schema `data/metrics/hooks.json`
- [ ] **3.3.4** Wire в OpenLLMetry (3.1)
- [ ] **3.3.5** CLI dashboard `scripts/hooks_dashboard.py`

**Effort:** 2-3 days | **Зависимость:** 3.1

### 3.4 P1 — GEPA replaces MIPROv2 (260423 B2)

- [ ] **3.4.1** Audit DSPy usage в `src/pdf_framework/agents/`
- [ ] **3.4.2** Migrate `dspy.MIPROv2` → `dspy.GEPA`
- [ ] **3.4.3** Re-compile teleprompted modules → save в `data/dspy/compiled/`
- [ ] **3.4.4** Benchmark на golden_v1
- [ ] **3.4.5** Если +5% — default

**Effort:** 2-3 days | **Зависимость:** 2.2 + DSPy ≥ 2.5

### 3.5 P1 — Dual-write feedback (260423 A2)

- [ ] **3.5.1** `feedback/collector.py` — `_write_jsonl_backup`
- [ ] **3.5.2** Path: `data/feedback/backup_YYYY-MM-DD.jsonl`
- [ ] **3.5.3** Recovery `scripts/replay_feedback_backup.py`
- [ ] **3.5.4** Tests: corrupt SQLite → backup читается → replay восстанавливает
- [ ] **3.5.5** Документировать в `08.4_Feedback_Loop.md`

**Effort:** 3-5 ч

### 3.6 P1 — Test coverage to 70% (260423 A6)

- [ ] **3.6.1** Run `pytest --cov=src/pdf_framework` → baseline
- [ ] **3.6.2** Identify modules < 70%: `agents/research_v2/`, `agents/deep/`, `optimization/`, `evaluation/runner.py` likely candidates
- [ ] **3.6.3** Add ~5-10 unit tests per under-covered module
- [ ] **3.6.4** CI gate (см. 2.5.3)

**Effort:** 3-5 days

### 3.7 P1 — Retry unification (260423 A3)

- [ ] **3.7.1** `grep -rn "for attempt in\|httpx_retries\|@retry\|tenacity" src/`
- [ ] **3.7.2** ~5-10 places to unify
- [ ] **3.7.3** `src/pdf_framework/utils/retry.py` — wrapper around tenacity (max_attempts=3, exp backoff, jitter)
- [ ] **3.7.4** Replace manual retry loops
- [ ] **3.7.5** Tests pass

**Effort:** 2-3 days

### 3.8 P1 — LangGraph Send API (260423 B4)

- [ ] **3.8.1** Audit `src/pdf_framework/agents/adaptive/` — multi-step decompose
- [ ] **3.8.2** Refactor sequential → `Send(queries)` parallel
- [ ] **3.8.3** Benchmark latency 5-query decompose до/после
- [ ] **3.8.4** Tests: existing semantics preserved

**Effort:** ~2 days

### 3.9 P1 — DeepEval CI gating (260423 B7)

- [ ] **3.9.1** `deepeval` в `[eval]` extra
- [ ] **3.9.2** `tests/eval/test_deepeval.py`: faithfulness > 0.7, hallucination < 0.1
- [ ] **3.9.3** Wire в smoke-gate (см. 2.1)
- [ ] **3.9.4** ADR-009 threshold rationale

**Effort:** ~2 days | **Зависимость:** 2.1

---

## 4. P2 — Medium (improvements / quality of life)

### 4.1 P2 — Matryoshka embeddings A/B (260423 B5)

- [ ] **4.1.1** Recreate `pdf_documents_mrl_1024` collection × 1024d (truncate)
- [ ] **4.1.2** Benchmark NDCG@10: 4096d vs MRL 1024d/512d
- [ ] **4.1.3** Если -delta < 5% → migrate `framework_code_v1` на MRL 1024d (4× faster)
- [ ] **4.1.4** Document `04_ПОИСК/04.X_Matryoshka.md`

**Effort:** 3-5 days

### 4.2 P2 — RAPTOR + LLM rerank (260423 A7)

- [ ] **4.2.1** `raptor_search.py` — `enable_llm_rerank: bool` parameter
- [ ] **4.2.2** Reranker: pass top-20 to LLM, sort by relevance score
- [ ] **4.2.3** Cache rerank decisions
- [ ] **4.2.4** Benchmark на golden_v1

**Effort:** 2-3 days

### 4.3 P2 — Stub embedding edge-case fix (260423 A5)

- [ ] **4.3.1** `grep -rE "stub|placeholder|np\.zeros\(" src/pdf_framework/embeddings/`
- [ ] **4.3.2** Fix или log warning
- [ ] **4.3.3** Test: edge case → real embed

**Effort:** ~2 ч

### 4.4 P2 — Sync-in-async cleanup (260423 A4)

- [ ] **4.4.1** `grep -rE "asyncio.to_thread\|run_in_executor" src/`
- [ ] **4.4.2** Replace c native async equivalent где возможно
- [ ] **4.4.3** Document pattern в `09.X_Async_Patterns.md`

**Effort:** 1-2 days

### 4.5 P2 — Delegation Iter 4-5 (260320 + 260423 C4)

- [ ] **4.5.1** Iter 4 design: trained router (vector similarity over outcome embeddings)
- [ ] **4.5.2** `src/shared/llm_rotation/router/trained.py`
- [ ] **4.5.3** A/B vs LinUCB (10% canary)
- [ ] **4.5.4** Iter 5 SAFLA: quality degradation, composite reward

**Effort:** 2-3 days each | **Зависимость:** 3.1 (observability для measurement)

### 4.6 P2 — Memory P5 advanced (260403 Phase 8)

Beyond base observability: cross-instance sync, encrypted memory at rest, GDPR per-user erase.

**Effort:** 1-2 weeks | **Status:** out-of-scope для near-term

### 4.7 P2 — MCP Inspector smoke (260423 B6)

- [ ] **4.7.1** Install `npx @modelcontextprotocol/inspector`
- [ ] **4.7.2** Script: foreach `.mcp.json` server — connect + list_tools, fail on timeout
- [ ] **4.7.3** Wire в `pre-commit-config.yaml`

**Effort:** 0.5 day

### 4.8 P2 — Phase 67 External tools (260423 C7)

- [ ] **4.8.1** Inventory candidates: claude-hud, codebase-memory-mcp, parry, sonar-bsl, bsl-language-server
- [ ] **4.8.2** Decision matrix: keep / replace / remove
- [ ] **4.8.3** Update `.mcp.json`

**Effort:** 2-3 days

### 4.9 P2 — Async PostToolUse hooks (260329 step 2.3)

- [ ] **4.9.1** Identify hooks с >2s typical latency
- [ ] **4.9.2** Refactor: sync entrypoint + fire-and-forget tail
- [ ] **4.9.3** Settings.json `"async": true` flag (если supported)

**Effort:** 1 day

### 4.10 P2 — GPU BSL Phase 4-5 (260326)

Phase 4: Colab indexing automation wrapper. Phase 5: Qdrant Cloud Free Tier (cloud-only path).

**Effort:** 1-2 days each | **Status:** deferred unless need

### 4.11 P2 — 25_LEARNING_LOOP chapter expansion

- [ ] **4.11.1** Audit `learning-loop` skill (5-фазный pipeline) → reference
- [ ] **4.11.2** Expand 25.1 Обзор: 21 → ~150 lines с диаграммой
- [ ] **4.11.3** Expand 25.3 Архитектура_субагента (44 → 100+)
- [ ] **4.11.4** Expand 25.6 Диагностика (40 → 100+)

**Effort:** 3-4 ч

---
