---
name: memory-unified
description: "Unified Memory System — кросс-системная память (AI Memory, Vector Memory, Skill Learning). ИСПОЛЬЗУЙ когда работаешь с unified ID, link registry, federated search, pattern learning, confidence decay. Триггеры: 'memory', 'unified id', 'link registry', 'federated search', 'pattern learning', 'confidence decay', 'memory-ai', 'vector-memory', 'skill-learning'. НЕ для MEMORY.md (→ auto-memory)."
---

# Unified Memory System

> **⚠ Test debt (2026-06-08):** many memory-subsystem unit tests
> (`tests/unit/hooks/`, `vector_store/test_qdrant*`, `processing/`, `agents/`) are
> temporarily skipped pending rewrite against current APIs — see
> [roadmap 260608](../../../docs/roadmap/260608_ROADMAP_UNIT_TEST_REMEDIATION.md)
> and [`tests/unit/conftest.py`](../../../tests/unit/conftest.py). Green CI ≠ full
> coverage for these areas until the listed tests are rewritten.

## When to use
- "memory", "unified id", "link registry", "federated search"
- "pattern learning", "confidence decay", "evidence"
- "memory-ai", "vector-memory", "skill-learning"
- Working with cross-system memory references

## Architecture

```
                    Memory Orchestrator
                   /        |          \
          UnifiedID    LinkRegistry   FederatedSearch
              |            |              |
    ┌─────────┼────────────┼──────────────┼──────────┐
    │         │            │              │          │
  memory-ai  vector-memory  skill-learning  pdf-docs
  (episodic)  (semantic)    (learning)     (docs)
```

### 4 Subsystems

| System | Type | Backend | Collection/DB |
|--------|------|---------|---------------|
| Memory AI | Episodic | SQLite | `data/memory_ai.db` |
| Vector Memory | Semantic | Qdrant | `learned_patterns` (4096d, Qwen3) |
| Skill Learning | Learning | JSONL files | `data/skill_learning/` |
| PDF Docs | Documentation | Qdrant | existing framework collections |

### UnifiedID Format

```
{memory_type}:{source}:{identifier}
```

Examples:
- `episodic:memory-ai:550e8400-e29b-41d4-a716-446655440000`
- `semantic:vector-memory:660f9500-f30c-52e5-b827-557766551111`
- `docs:pdf-docs:a1b2c3d4e5f67890`
- `learning:skill-learning:770g0600-g41d-63f6-c938-668877662222`

### Link Types (8 — ADR-L1, roadmap 260612 LinkRegistry)

**Авто-писатели:**

| Type | Писатель |
|------|----------|
| `mirrors` | cross_store_sync (mirror→canonical, §26 P3) |
| `derives_from` | reflection (§26 P2: semantic→episodic sources) |
| `session_context` | route_and_save multi-target (unified-ID концы с 2026-06-12) |
| `promoted_to` | WikiPromoter (проведён F7; выстрелит на первом промоуте) |

**Ручной словарь `create_link`:** `supports`, `contradicts`, `extends`, `superseded_by`
(участвуют в весах propagation/каскада).

**Ретированы 2026-06-12 (ADR-L1):** `based_on` (non-goal по ADR-D2/D4 pdf-docs,
0 рёбер за историю), `graph_node` (ни писателя, ни читателя, 0 рёбер).
`create_link` принимает ТОЛЬКО unified-ID `type:source:identifier` (P0.1 —
сырые UUID отклоняются ValueError); CRUD эмитит `link_create`/`link_delete`
в sink `memory-links.log` (§27, P3.1), пустой каскад виден событием
`cascade_empty` (P3.2). Acceptance: `scripts/link_registry_acceptance.py`.

**§26 P3 cross-store sync (auto-links).** [`scripts/cross_store_sync.py`](../../../scripts/cross_store_sync.py) + [`src/memory/orchestrator/cross_store_sync.py`](../../../src/memory/orchestrator/cross_store_sync.py) консолидируют дубли (из [`cross_store_index`](../../../src/memory/orchestrator/cross_store_index.py), D3.1): `ConflictResolver(SOURCE_PRIORITY)` выбирает canonical store (`wiki > learned_patterns > skill_learning > memory_ai`) и создаёт `MIRRORS`-связи (mirror→canonical) в link_registry — **idempotent, dry-run default, additive/reversible** (`--apply` для записи). [`WikiPromoter`](../../../src/memory/librarian/wiki_promoter.py) создаёт `PROMOTED_TO` при promotion learned→wiki (opt-in `link_registry`, fail-soft). `unified_search` `Deduplicator` уже коллапсит идентичный контент при запросе; `MIRRORS` добавляет персистентную провенанс-связь. См. [roadmap §26 P3](../../../docs/roadmap/260602_ROADMAP_MEMORY_INGESTION_SYNC.md).

**§26 P4 maintenance cadence (scheduling + ForgetGate + dashboard).** [`scripts/memory_maintenance.py`](../../../scripts/memory_maintenance.py) — оркестратор, последовательно гоняет джобы (reflect → cross_store_sync → promote → forget) и пишет дашборд в `data/reports/memory/memory_maintenance_*.md`. **READ-ONLY по умолчанию** (`--apply` для записи). **ForgetGate** [`src/memory/maintenance/forget_gate.py`](../../../src/memory/maintenance/forget_gate.py) — bounded-growth: `plan_forget` переиспользует §22 `should_archive` (archive = invalidate-not-delete `expired_at`; invariant-типы `architectural-principle`/`bsl-pattern` исключены из staleness, но fail-archived). **Dashboard** [`dashboard.py`](../../../src/memory/maintenance/dashboard.py) — store_sizes / cross_store_dup_rate / ingest+dup rates (из `memory-ingestion.log`) / forget summary / link stats; **+260612 pdf-docs P3.2/P4:** store_sizes считает ТОЧКИ `pdf_documents`/`wiki_pages_v1` в Qdrant (не drafts на диске); секция «Docs freshness» — `compute_docs_freshness` (pure, возраст последнего `run_end` из `data/indexing-progress.jsonl`, ⚠ STALE при > `DOCS_STALE_DAYS=30` или отсутствии run_end); job `reindex_wiki` сразу после `promote` (apply-only, wiki .md ↔ `wiki_pages_v1` одним пайплайном); acceptance `scripts/pdf_docs_acceptance.py`. **Scheduling** — Stop-hook [`memory-maintenance-cadence.py`](../../../.claude/hooks/memory-maintenance-cadence.py) запускает оркестратор каждые N distinct sessions (sentinel-state, detached, cold-start seed). Opt-out: `MEMORY_MAINTENANCE_DISABLE=1`; cadence `MEMORY_MAINTENANCE_EVERY=N` (default 10); запись `MEMORY_MAINTENANCE_APPLY=1`. См. [roadmap §26 P4](../../../docs/roadmap/260602_ROADMAP_MEMORY_INGESTION_SYNC.md). **§26 завершён (P0..P4).**

### Confidence System (Vector Memory)

**Обновлено 2026-05-31 (§22 P0, commit `c8409e30b`):** confidence теперь **производный** от Beta(7,3) posterior над time-decayed счётчиками успехов/фейлов (раньше — наивный `+0.02/−0.01`). Чистые функции: [`src/memory/vector_memory/confidence.py`](../../../src/memory/vector_memory/confidence.py).

- Range: 0.0-1.0; **prior Beta(7,3)** → стартовое значение **0.70**.
- Формула (derived, денорм-кэш `confidence` для Qdrant-фильтра): `confidence = (7 + succ) / (10 + succ + fail)`.
- Хранятся sufficient stats: `succ`, `fail` (float-счётчики), `last_decay_at`. Prior — read-time константа, не хранится. Без clamp (ratio ∈ (0,1)).
- Application (`apply_pattern`): сначала decay счётчиков `succ,fail *= exp(−decay_rate·Δdays/30)` (floor <1e-6→0), затем `succ+=1` (success) / `fail+=1` (fail). 5 чистых успехов: 0.70 → **0.80**; +1 фейл → 0.75.
- Decay (`decay_confidence`): затухают **счётчики**, confidence дрейфит к **prior 0.70** (НЕ к 0). Простой → де-промоушен, не обнуление.
- **Lazy decay-on-read (§22 P2, `b05d1081d`):** `confidence.payload_effective_confidence` пересчитывает confidence ПРИ ЧТЕНИИ из stored counts (без записи). `search_patterns` (drop server-prefilter + client-side effective filter/rank), `get_pattern` (отдаёт `effective_confidence`), `WikiPromoter` (gate на effective) — stale-паттерны ранжируются/фильтруются ниже автоматически.
- **FSRS-lite stability (§22 P4, `942f55fa0`):** `confidence.stability_adjusted_rate(base, application_count) = base/(1+0.3·ln(1+count))` — established паттерны (высокий lifetime `application_count`) затухают медленнее (use-modulated λ). Применён в `_resolve_state` (все decay-пути) + `decay_confidence` sweep. Без нового поля. Full FSRS power-curve — deferred.
- **Forgetting + revive (§22 P3, `2aa6fcb21`):** invalidate-not-delete — флаг `expired_at` вместо удаления. `confidence.should_archive` = `fail_floor (eff<0.40)` ИЛИ `staleness (idle>180д & eff<0.75 & не invariant)`; `is_invariant` = architectural-principle/bsl-pattern (вечные правила не архивируются по времени, только по фейлам). `decay_confidence` архивирует (не удаляет); `search_patterns` оставляет archived в выдаче с весом ×0.5 (revive-on-recurrence) — любой `apply` снимает `expired_at` (оживляет). `WikiPromoter` пропускает archived. DEFER: neighbor-aware gate (link_registry). Полный цикл (raise→decay→forget→revive): roadmap §22 (P0-P3 DONE).
- Legacy-миграция (lazy, on-read): `succ=conf·n, fail=(1−conf)·n` (n=application_count); отсутствие полей → prior 0.70.
- Threshold: `<0.3` auto-delete сохранён (но count-decay floors at 0.70 → срабатывает редко; staleness-архивация — §22 P3, ещё не реализована).
- Полная стратегия (raise/decay/forgetting/enrichment) + research: roadmap §22 ([260523](../../../docs/roadmap/260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md)).

## Key Files

- Orchestrator: `src/memory/orchestrator/` (unified_id, link_registry, unified_search, cross_store_index, cross_store_sync)
- Maintenance cadence (§26 P4): `src/memory/maintenance/` (`forget_gate`, `dashboard`) + `scripts/memory_maintenance.py` (orchestrator) + Stop-hook `.claude/hooks/memory-maintenance-cadence.py`
- AI Memory: `src/memory/ai_memory/server.py` (5 MCP tools)
- Vector Memory: `src/memory/vector_memory/server.py` (7 MCP tools)
- Confidence lifecycle log (§22): `src/memory/vector_memory/lifecycle_log.py` — `log_event()` пишет JSONL всех confidence-мутаций в `.claude/cache/confidence-lifecycle.log` (события `reinforce`/`reinforce_miss`/`reinforce_error` из `reinforce.py`, `session`/`session_error` из Stop-hook `pattern_reinforce.py`, **MCP-side** `apply`/`decay_sweep`/`save`/`delete`/`server_start` из `server.py` — нужен `/mcp reconnect`); fail-soft, atomic-rotation 2MB, buffered append (`O_APPEND`-вариант откатан — терял записи на win32 concurrent-open), opt-out `CONFIDENCE_LOG_DISABLE=1`. Диагностика raise/decay/reinforce/archive. Анализ: `tail` + построчный `json.loads`
- Confidence epoch (§24): `src/memory/vector_memory/epoch.py` — `bump()`/`read()` маркер мутаций confidence/archive в `.claude/cache/confidence-epoch.txt`; вшит в `memory-first-hook` cache_key для мгновенной инвалидации surfacing-кеша без Qdrant-roundtrip. Бампается из `reinforce.py:reinforce_pattern` + server.py `handle_apply_pattern`/`decay_confidence`/`save_pattern`/`delete_pattern` (MCP-side → нужен `/mcp reconnect`)
- Skill Learning: `src/memory/skill_learning/server.py` (7 MCP tools)
- Surfacing trace log (§24.4): `memory-first-hook` пишет per-invocation JSONL в `.claude/cache/memory-first-surfacing.log` (стадии cache/tei/arms/gate/layers/rrf/rerank/outcome/duration; fail-soft, atomic-rotation 2MB, opt-out `MEMORY_SURFACE_LOG_DISABLE=1`) — диагностика «почему паттерн всплыл/не всплыл». Анализ: `tail` + построчный `json.loads`
- **Full observability (§27)**: `src/memory/infrastructure/trace_log.py` (`write_trace` — generic JSONL writer для P1 routing/read/propagation/circuit логов; global opt-out `MEMORY_TRACE_DISABLE=1`) + `src/memory/infrastructure/event_envelope.py` (`normalize`/`make_envelope`/`known_sinks` — канонический reader-адаптер 10 sink'ов в плоскую схему). Анализ: `python scripts/memory_observability_query.py --view {recent|by-source|error-rate|latency|freshness|fact-trace}` (DuckDB cross-log; **`fact-trace --key <content_hash|pattern_id>`** тредит факт ingestion→reinforce→forget) + `python scripts/memory_observability_report.py [--since 7d]` (unified `data/reports/memory/observability-*.md`: cross-process метрики + stale-sink regression detection). Дизайн: [roadmap 260605](../../../docs/roadmap/260605_ROADMAP_MEMORY_FULL_OBSERVABILITY.md)
- Tests: `tests/integration/test_memory_unified.py` (26 tests)
- MCP config: `.mcp.json` (4 servers registered)

## MCP Tools

### memory-ai (5 tools)
- `get_important_messages` — filter by importance/category
- `save_important_message` — save with importance score
- `search_messages` — full-text search
- `delete_message` — remove by ID
- `get_categories` — list categories with stats

### vector-memory (8 tools)
- `save_pattern` — save with confidence
- `search_patterns` — semantic search + confidence filter
- `apply_pattern` — track usage, update confidence
- `get_pattern` / `delete_pattern` — CRUD
- `decay_confidence` — apply temporal decay
- `health_check` — Qdrant status
- `list_patterns` — browse pattern CONTENT without a query (scroll-based, no embedding → no TEI cold-start); filters: pattern_type / min_confidence (effective) / grep / limit / full (added 2026-06-02)

### skill-learning (7 tools)
- `capture_pattern` — capture from tool use
- `batch_capture` — multiple patterns
- `get_pending_patterns` — awaiting confirmation
- `confirm_pattern` / `reject_pattern` — review
- `get_learning_stats` — statistics
- `health_check` — storage status

### memory-orchestrator (33 tools)

**Core (8, P0):**
- `unified_search` — federated search across all subsystems
- `route_and_save` — auto-classify and route to targets
- `get_full_context` — entity + BFS graph traversal
- `create_link` — cross-reference between entities
- `get_related` — find related via BFS
- `propagate_update` — confidence propagation through graph
- `get_system_stats` — aggregate statistics (includes P4 services)
- `health_check` — subsystem health (includes P4 services)

**Realtime (8, P3):**
- `memory_subscribe` / `memory_unsubscribe` — event subscriptions
- `memory_publish` — publish custom event
- `memory_get_events` — poll pending events
- `memory_replay` / `memory_event_history` — event replay/history
- `memory_event_stats` — bus/store/subscription stats
- `memory_subscription_health` — heartbeat/list

**Extended (4, P3):**
- `memory_research` — deep analysis (relationships, anomalies, clusters)
- `memory_id_management` — UUIDv7, resolution, conflicts
- `memory_surprise` — novelty scoring
- `memory_warmup` — cache preloading

**Services (13, P4):**
- `memory_audit_log` — query audit log with filters
- `memory_audit_stats` — audit statistics
- `memory_circuit_status` — circuit breaker status
- `memory_circuit_reset` — reset circuit breaker
- `memory_metrics` — aggregated metrics (counters, gauges, durations)
- `memory_ttl_set` — register/update TTL for entity
- `memory_ttl_check` — check TTL status / get expired
- `memory_ttl_cleanup` — remove expired entries
- `memory_version_history` — entity version history
- `memory_version_rollback` — rollback to specific version
- `memory_version_compare` — diff between two versions
- `memory_forget` — ForgetGate evaluation (dry-run by default)
- `memory_graph_analyze` — PageRank, centrality, communities, shortest path

### Hooks (P5)

- `session-memory-save.py` (Stop) — auto-saves session context to SQLite + wiki log on session end
  - Extracts: git diff, activated skills, commits, completed tasks
  - Writes to `data/memory_ai.db` (category: `session_summary`)
  - Also appends brief summary to `docs/wiki/log.md` (Hermes Phase 2)
  - Dedup by session_id or date, auto-importance (0.5-0.95), auto-tags
  - ⚠ §22 reinforce здесь БОЛЬШЕ НЕ живёт (roadmap 260609 P0.1) — см. следующий хук
- `pattern-reinforce-stop.py` (Stop, timeout 15s async) — §22 reinforcement bridge (roadmap 260609 P0.1, 2026-06-09)
  - Выделен из session-memory-save: там вызов стоял ПОСЛЕ early-return'ов `is_meaningful`/`already_saved` и в 5s-бюджете → **0 production-reinforce за всю историю** (все события в lifecycle-логе были pytest-фикстурами)
  - session_id строго из Stop-payload (тот же источник, которым memory-first-hook именует `surfaced-patterns-<sid>.json`)
  - Early-exit через `load_surfaced()` ДО импорта Qdrant; cap `REINFORCE_CAP=10`; ошибки → `session_error` в lifecycle-лог (не `except: pass`)
  - Первый production-прогон 2026-06-09: `session=1bab9bcd applied=10 errors=0`
  - F14 (260611): `not_found`-miss считается в `missing` (не `errors`) — паттерн легитимно удалён cleanup'ом; баннер `[REINFORCE] ... missing=N` и lifecycle-событие `session` несут отдельный счётчик
  - Opt-out: `P1_REINFORCE_DISABLE=1`

### Test isolation (roadmap 260609 P0.2)

`tests/conftest.py` на import-time уводит memory-sinks в tmp: `CLAUDE_CACHE_DIR` (lifecycle/epoch/trace/ingest/surfaced) + `LINK_REGISTRY_PATH` (env-override в `LinkRegistry.__init__`). Раньше pytest писал фикстуры в production `confidence-lifecycle.log` и `data/link_registry.db`. Чистка остатков: `scripts/cleanup_memory_test_pollution.py` (dry-run default). Opt-out: `MEMORY_TEST_ISOLATION_DISABLE=1`.

### Write-contract + cache redesign (roadmap 260609 P1, 2026-06-10)

- **§26 write-contract в прямых писателях (P1.3):** `content_hash` + skip-on-exists dedup + `record_ingest` теперь во ВСЕХ прямых писателях, не только харвестерах — `save_pattern`, `route_and_save._save_to_target` (4 target'а), `save_important_message` (content-equality dedup), `capture_pattern` (dedup по pending+saved). Общий [`content_hash.point_id()`](../../../src/memory/orchestrator/content_hash.py) (UUID5, namespace харвестера) делает id детерминированным от контента → повторный save = `action=dup`, новой точки нет, и manual-write коллапсит в ту же точку, что harvest. Записи видны `cross_store_sync` / `fact-trace`. ⚠ MCP-side → нужен `/mcp reconnect`.
- **Честный `route_and_save` (P1.4):** partial-fail target'ов → `success:false` + `saved_partial:true` + `failed_targets[]` (раньше — всегда `success:true`, потери молча).
- **Surfacing cache-key редизайн (P1.2):** `_surface_cache_key` ослаблен с exact-token-set до top-K (8) salient-stem токенов (длинные = content-bearing в RU/BSL) → промпты на одну тему с разным filler'ом хитуют; epoch по-прежнему вшит (мгновенная инвалидация). TTL 300→900s; empty-результаты на коротком `SURFACE_CACHE_EMPTY_TTL` (180s). Env-knobs: `MEMORY_SURFACE_CACHE_KEY_TOPK`, `MEMORY_SURFACE_CACHE_EMPTY_TTL`, `MEMORY_SURFACE_LEXICAL_SCROLL` (100→50). Per-stage timing (`sqlite/qdrant/md/rerank`) в surfacing-log для профилирования (P1.1).
- **Тесты:** `tests/unit/test_write_contract.py` (11), `tests/unit/test_surfacing_cache.py` (4). ⚠ Production-acceptance P1.1 (латентность) / P1.2 (hit-rate) подтвердятся накоплением surfacing-лога после reconnect.

### PropagationEngine wired + стабы восстановлены (roadmap 260609 P2.2/P2.3, 2026-06-10)

- **P2.3 — `propagate_update` реально мутирует:** `PropagationEngine._apply_update` честный (handler→`bool(result)`, no-handler→`False` — конец «simulate success», больше нет фантомных `entities_updated`). `MemoryOrchestrator._build_propagation_handlers()` подключает реальные handlers: **vector-memory** (нудж Beta `succ/fail` по знаку delta → `derive_confidence` → `set_payload` на тёплом `_get_qdrant`), **memory-ai** (`importance ± delta` clamp `[0,1]` в SQLite; env `MEMORY_AI_DB_PATH` для изоляции тестов). `success` сворачивается в знак delta. Сосуществует с server-side `_cascade_confidence` (синхронный каскад на горячем `apply_pattern`) — два разных входа, не конфликтуют. ⚠ MCP-side → нужен `/mcp reconnect`.
- **P2.2 — стабы B1 восстановлены (L5-план):** `session-memory-save.py` снова пишет `docs/wiki/log.md` (`save_to_wiki_log`, UTF-8 + trim 500), делегирует промоут `export_graph_to_wiki promote-patterns` (`try_promote_patterns`, = §26 P4 cadence job, opt-out `SESSION_MEMORY_NO_PROMOTE=1`), эмитит Langfuse-span (`_emit_langfuse_span`, graceful no-op без Langfuse). Восстановлено из git `7bc57e463`.
- **Тесты:** `tests/unit/test_propagation_honest.py` (5) + 2 BFS-теста в `test_p1_infrastructure.py` (dummy success-handler). 5 unit + 9 engine + 18 orchestrator integration PASS.
- **Post-review remediation (2026-06-10, та же сессия):** (1) lazy-init движка в оркестраторе получил `PropagationConfig(enable_background_processing=False, enable_event_deduplication=False)` — иначе production-вызов возвращал `entities_updated=[]` / `reason="queued_for_background_processing"` (честный результат прятался за очередью), а dedup молча глотал повторный `propagate_update` по тому же entity; (2) vector-handler бампит §24 epoch после `set_payload` (инвариант: каждый писатель confidence инвалидирует surfacing-кэш); (3) `try_promote_patterns` → detached `Popen` (паттерн post-indexing-analyzer, лог `.claude/cache/session-promote.log`) — Stop-бюджет не платит за Qdrant-scroll; (4) `_emit_langfuse_span` — дешёвый pre-gate `_langfuse_configured()` (env/`.env` probe ДО импорта `src.*`; в этом окружении Langfuse реально включён — `OBSERVABILITY__LANGFUSE_ENABLED=true`, span стоит ~2.3s network-flush, emit последний в `execute()`); (5) timeout хука 5→15s в `settings.json`; (6) `ai_memory/server.py` `DB_PATH` теперь тоже уважает `MEMORY_AI_DB_PATH`. +2 теста-пина: sync+repeatable orchestrator-путь, epoch-bump handler'а.


### Honest-failure & governance wiring (roadmap 260611, 2026-06-11)

Контракт «ошибка доезжает до ответа/лога, а не глотается» — закрывает F5/F8/F9/F10/F12/F13/F14 из chain-testing 260610:

- **`propagate_update` (F10):** `PropagationResult.failed_entities{entity→reason}` — handler-исключение больше не схлопывается в тихий skip; tri-state `_apply_update` (`applied` / `skipped_*` / `failed:<ExcType>`). Named breakers **`propagation:<source>`** вокруг handler-вызовов (реестр оркестратора): 5 фейлов → OPEN → `failed:circuit_open` fail-fast; `memory_circuit_status`/`memory_circuit_reset` управляют реальными breakers, transitions пишутся в `memory-circuit.log` (sink ожил, observability 10/10).
- **`unified_search` (F12):** vector-плечо больше не глотает исключения — TEI/Qdrant-outage виден в `sources_failed[]` (как у ai-плеча); потребители читают `results`, не падая на непустом `sources_failed`.
- **Versioning (F8, ADR-V wire-minimal):** снапшотятся только orchestrator-mediated мутации — `route_and_save` (CREATE), propagation-handlers (UPDATE), rollback (ROLLBACK + **store-writeback**: memory-ai content/importance, vector payload-поля без re-embed `vector_reembedded:false`). Прямые писатели MCP-серверов вне версионирования (JSONL не concurrent-safe между процессами).
- **TTL (F9):** `memory_ttl_cleanup` исполняет до store'ов: vector → archive (`expired_at`, §22 invalidate-not-delete + epoch bump), memory-ai → delete; ответ `{removed_ledger, store_actions{archived/deleted/skipped}, failed}`.
- **WikiPromoter (F13):** идемпотентен — `promoted_to` пишется на source-точку (`_mark_promoted`), pre-filter по нему до векторного dedup, `_append_log` дедупит по упоминанию `drafts/{slug}.md`.
- **F5/F14:** `get_pattern` отдаёт согласованные `archived`/`expired_at`; reinforce-мост считает `not_found`-miss в `missing` (не `errors`) — `[REINFORCE]`-баннер не врёт.
- **§18 live re-run follow-ups (2026-06-11, после прогона D2–D5 живыми MCP-tools):**
  - **F16**: `_apply_version_to_store` (MEMORY_AI) разворачивает `metadata.importance` из CREATE-снапшотов `route_and_save` — rollback к v1 восстанавливает importance, не только content (top-level приоритетен, UPDATE-снапшоты propagation не задеты). Открытый N2-гэп: vector-ветка rollback-to-CREATE восстанавливает только `content` (не `metadata.confidence/name/description`) — ответ честный (`fields`), чинить при появлении live-пути.
  - **Cold-start warmup**: `vector_memory/server.py` — daemon-поток `_warmup_qdrant` при старте сервера пре-оплачивает импорт `qdrant_client` (под contention одновременного старта MCP-серверов первый tool-вызов сгорал на 60s client-timeout); fail-soft, opt-out `MEMORY_VECTOR_NO_WARMUP=1`; `_get_qdrant` под double-checked lock, глобал публикуется только после успешного `_ensure_collection(client)` (упавший init ретраится следующим вызовом).
- ⚠ Всё MCP-side (кроме F14-моста и F13-скрипта) → `/mcp reconnect` после правок. Тесты: `test_propagation_honest.py` (10), `test_governance_wiring.py` (8), `test_unified_search_honest.py` (2), `test_quick_fixes_260611.py` (5).

## Незадокументированные memory_subsystem

- `LinkType` (src\memory\orchestrator\link_registry.py)
- `EntityLink` (src\memory\orchestrator\link_registry.py)
- `RelatedEntity` (src\memory\orchestrator\link_registry.py)
- `ContentType` (src\memory\orchestrator\memcube.py)
- `AiMemorySearchAdapter` (src\memory\orchestrator\memory_orchestrator.py)
- `VectorMemorySearchAdapter` (src\memory\orchestrator\memory_orchestrator.py)
- `SkillLearningSearchAdapter` (src\memory\orchestrator\memory_orchestrator.py)
- `MemoryOrchestrator` (src\memory\orchestrator\memory_orchestrator.py)
- `RoutingDecision` (src\memory\orchestrator\memory_router.py)
- `RoutingStats` (src\memory\orchestrator\memory_router.py)
- `ClassificationResult` (src\memory\orchestrator\memory_router.py)
- `ContentClassifier` (src\memory\orchestrator\memory_router.py)
- `MemoryRouter` (src\memory\orchestrator\memory_router.py)
- `PropagationEvent` (src\memory\orchestrator\propagation_engine.py)
- `PropagationResult` (src\memory\orchestrator\propagation_engine.py)
- `PropagationEngine` (src\memory\orchestrator\propagation_engine.py)
- `MemoryType` (src\memory\orchestrator\unified_id.py)
- `SourceServer` (src\memory\orchestrator\unified_id.py)
- `IDRegistry` (src\memory\orchestrator\unified_id.py)
- `SearchOptions` (src\memory\orchestrator\unified_search.py)
- `LinkedEntity` (src\memory\orchestrator\unified_search.py)
- `SearchResultItem` (src\memory\orchestrator\unified_search.py)
- `UnifiedSearchResult` (src\memory\orchestrator\unified_search.py)
- `BaseSearchAdapter` (src\memory\orchestrator\unified_search.py)
- `ScoreNormalizer` (src\memory\orchestrator\unified_search.py)
- `RRFMerger` (src\memory\orchestrator\unified_search.py)
- `Deduplicator` (src\memory\orchestrator\unified_search.py)
- `Reranker` (src\memory\orchestrator\unified_search.py)
- `LinkEnricher` (src\memory\orchestrator\unified_search.py)
- `UnifiedSearchEngine` (src\memory\orchestrator\unified_search.py)
- `PatternType` (src\memory\vector_memory\models.py)
- `ConfidenceLevel` (src\memory\vector_memory\models.py)
- `EvidenceSource` (src\memory\vector_memory\models.py)
- `LearnedPattern` (src\memory\vector_memory\models.py)
- `PatternSearchResult` (src\memory\vector_memory\models.py)
- `LearningStats` (src\memory\vector_memory\models.py)
- `WikiDecayService` (src\memory\librarian\wiki_decay.py)
- `CacheEntry` (src\memory\infrastructure\cache.py)
- `LRUCache` (src\memory\infrastructure\cache.py)
- `CircuitState` (src\memory\infrastructure\circuit_breaker.py)
- `CircuitStats` (src\memory\infrastructure\circuit_breaker.py)
- `CircuitBreaker` (src\memory\infrastructure\circuit_breaker.py)
- `CircuitBreakerRegistry` (src\memory\infrastructure\circuit_breaker.py)
- `ConflictStrategy` (src\memory\infrastructure\conflict_resolver.py)
- `ConflictRecord` (src\memory\infrastructure\conflict_resolver.py)
- `ConflictResult` (src\memory\infrastructure\conflict_resolver.py)
- `ConflictResolver` (src\memory\infrastructure\conflict_resolver.py)
- `EventBusStats` (src\memory\infrastructure\event_bus.py)
- `EventStore` (src\memory\infrastructure\event_store.py)
- `MetricsCollector` (src\memory\infrastructure\metrics.py)
- `MetricsTimer` (src\memory\infrastructure\metrics.py)
- `ManagedSubscription` (src\memory\infrastructure\subscription_manager.py)
- `SubscriptionManager` (src\memory\infrastructure\subscription_manager.py)
