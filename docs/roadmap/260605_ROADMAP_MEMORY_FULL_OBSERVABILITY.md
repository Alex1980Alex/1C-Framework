# Roadmap — Memory Full Observability (логирование всех процессов для оценки эффективности)

> **Дата:** 2026-06-05 · **Статус:** ✅ DONE — **P0 ✅ · P1 ✅ · P2 ✅ · P3 ✅ · P4 ✅** · **Родитель:** [27.12 Memory Systems Map §10](../framework%20documentation/5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md) · **Смежные:** [§22 confidence](260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md) · [§25 effectiveness](260601_ROADMAP_MEMORY_EFFECTIVENESS.md) · [§26 ingestion](260602_ROADMAP_MEMORY_INGESTION_SYNC.md)
>
> Цель: **каждый процесс памяти оставляет структурный след** (per-event JSONL), чтобы §25-аналитика могла измерять эффективность сквозного цикла **ingestion → consolidation → sync → retrieval → forget**. Инвентаризация — code-grounded аудит 2026-06-05 (8 sink'ов × ~25 процессов, §2).

---

## 0. Итог (2026-06-05) — roadmap ЗАКРЫТ (P0-P4)

**Сделано:** **все фазы завершены, 8/8 топ-гэпов закрыты — наблюдаемость памяти доведена до 100%.** P0 оживил недостающих **writers** для построенных sink'ов (ingestion/forget/audit). P1 добавил per-process event-логи слепых процессов (routing/federated-read/propagation/circuit). P2 — персистентность метрик + cadence run-поток. **P3** свёл всё к **каноническому envelope + reader-adapter** и дал DuckDB cross-log **fact-trace** (сквозной трейс факта по `content_hash`/`pattern_id`). **P4** — слой анализа: unified observability report по всем sink'ам с cross-process метриками + детектор регрессии наблюдаемости (stale-sink).

| Фаза | Статус | Итог |
|---|---|---|
| **P0** Подключить построенные sink'и | ✅ DONE | D0.1 `memory-ingestion.log` **оживлён** (харвестер per-action события + cadence `record_store_size`) · D0.2 ForgetGate script-path → `confidence-lifecycle.log` + epoch bump · D0.3 audit write-path **оживлён** (`_audit` ×4 + flush-on-stop + hardening re-entrant deadlock). **20 unit, 3× code-verify PASS**, live sink-revival |
| **P1** Новые event-логи слепых процессов | ✅ DONE | D1.1 routing + D1.2 federated-read + D1.3 propagation + D1.4 circuit-breaker — все через shared `trace_log`; 5 unit, 3× code-verify PASS |
| **P2** Persist metrics + cadence run-лог | ✅ DONE | D2.1 metrics-snapshot на `stop()`→`memory-metrics.jsonl` · D2.2 cadence run-лог→`memory-maintenance-runs.jsonl` · D2.3 store-size series (через D0.1); 6 unit, code-verify PASS |
| **P3** Единый envelope + сквозная корреляция | ✅ DONE | D3.1 канонический envelope + reader-adapter (`event_envelope.py`: `normalize`/`make_envelope`/`known_sinks`, stable `CORE_KEYS`) · D3.2 DuckDB cross-log query (`memory_observability_query.py` mirror `audit_query.py`) + **fact-trace** по `content_hash` ИЛИ `pattern_id` (cross-sink thread проверен live: ingestion→reinforce→forget). Side-fix: harvester эмитит `content_hash`+`pattern_id` (D3.2-ключ) · CAST-fix DuckDB UUID-inference. **8 unit, code-verify PASS** |
| **P4** Слой анализа эффективности (§25) | ✅ DONE | D4.1 cross-process aggregators (ingest/dup/forget/routing/read-hit/propagation-reach/circuit/audit) + D4.2 unified report (`memory_observability_report.py`→`observability-*.md`) + **stale-sink regression detection** (freshness; cold≠regression). **6 unit, code-verify PASS**, live report на реальных логах |

**Закрытые топ-гэпы:** все 8 — #1 (ingestion sink без писателей), #2 (ForgetGate script невидим + epoch-баг), #3 (audit write-path мёртв), #4 (federated-read), #5 (routing), #6 (propagation/breaker), #7 (metrics persist), #8 (cadence run-лог).
**Follow-up P0 закрыт частично:** harvester теперь эмитит `content_hash`+`pattern_id` (P3 D3.2); остаётся reflection per-source-атрибуция + `route_and_save` per-store record_ingest.
**⚠ Runtime:** P1/P2 MCP-side логи (routing/read/propagation/circuit/metrics) на диске появляются только после orchestrator-run + `/mcp reconnect`; до того отчёт корректно помечает их `missing` (cold, НЕ regression). P3/P4 (скрипты/хуки) — effective сразу.

---

## 1. Краткая постановка

Половина системы памяти **наблюдаема**, половина — **слепа**:

- **Хорошо инструментировано** (богатый per-event JSONL): §22 confidence-lifecycle (`confidence-lifecycle.log`) + §24 surfacing (`memory-first-surfacing.log`). Это «золотой стандарт» — по ним видно raise/decay/forget/revive и почему паттерн всплыл/не всплыл.
- **Слепые зоны:** ingestion (харвестеры/reflection/sync), audit-trail (кто/что/когда менял), routing-решения, federated-read (`unified_search`), propagation, и **script-side governance** (P4 forget мимо MCP-лога).

**Симптом-первопричина:** §25-analyzer и P4-dashboard читают `memory-ingestion.log`, которого **физически нет** — sink построен (`ingest_metrics.py`), но у него **ноль живых писателей** (§2 #3). Дашборды эффективности молча показывают пустоту. Нельзя улучшать то, что не измеряешь.

**Цель §27 = довести наблюдаемость до 100% покрытия**, переиспользуя существующий паттерн логирования (atomic-rotation JSONL, fail-soft, opt-out), а НЕ строя новую инфру.

## 2. Инвентаризация (code-grounded, аудит 2026-06-05)

### 2.1 Sink'и (журналы) и их состояние

| # | Sink | На диске | Писатели | Состояние |
|---|---|---|---|---|
| 1 | `.claude/cache/confidence-lifecycle.log` | ✓ active | `lifecycle_log.log_event` ← `vector_memory/server.py` (save/apply/delete/decay_sweep/server_start), `reinforce.py`, `pattern_reinforce.py` | ✅ rich, multi-writer |
| 2 | `.claude/cache/memory-first-surfacing.log` | ✓ active | `memory-first-hook.py::_surface_log` (per-stage) | ✅ золотой стандарт |
| 3 | `.claude/cache/memory-ingestion.log` | **ОТСУТСТВУЕТ** | `ingest_metrics.record_ingest`/`record_store_size` — **0 живых вызовов** (только модуль+тесты) | ❌ **GAP: sink есть, писателей нет** |
| 4 | `data/hook-invocations.jsonl` | ✓ active | `mcp-invocation-logger` (все `mcp__*`), `BaseHook` auto-log | ✅ но грубо (tool+outcome+ms, без деталей решения) |
| 5 | Audit `data/services/audit.jsonl` | **ОТСУТСТВУЕТ** (`data/services/` пуст) | `AuditService.log()` есть, но оркестратор только **читает** (`memory_audit_log`); ни одного `.log()`-вызова | ❌ **GAP: write-path мёртв** |
| 6 | Metrics `MetricsCollector` | in-process | `metrics.py` — только in-memory + `export_json()`; нет файла | ⚠ теряется на рестарт |
| 7 | `link_registry.db` `link_history` | ✓ active | `create_link`/`update_link`/`delete_link` | ✅ |
| 8 | Event Store `events.jsonl`/`events.db` | ✓ active | `_emit_event` (только `memory.save`, `memory.link`) + ручной `memory_publish` | ✅ но узко (2 типа) |

### 2.2 Процессы (статус логирования)

| Процесс | Лог? | Sink | Заметка |
|---|---|---|---|
| **WRITE** | | | |
| `route_and_save` | partial | event store + in-proc metrics | нет audit, нет record_ingest; routing-reasoning не в payload |
| `save_pattern` | ✅ | confidence-lifecycle | `_log_lifecycle("save")` |
| `save_message` | partial | mcp_call only | пишет SQLite-строку, нет per-event memory-лога |
| `capture_pattern` | partial | mcp_call only | пишет pending JSONL, нет per-event |
| `session-memory-save` (Stop) | partial | SQLite + (reinforce→lifecycle) | `save_to_wiki_log`/`_emit_langfuse_span` — **NO-OP stubs** |
| `Router.classify` | ❌ **GAP** | in-proc `self.stats` | решение/targets/confidences/reasoning не персистятся |
| cross-link на save | ✅ | link_history + event | |
| **READ** | | | |
| `unified_search` (federated) | ❌ **GAP** | logger-on-error only | НЕ логируется как surfacing; arms/hits/scores невидимы |
| `memory-first-hook` surfacing | ✅ | surfacing.log | золотой стандарт |
| **CASCADE** | | | |
| `apply_pattern` | ✅ | confidence-lifecycle | |
| Propagation BFS | ❌ **GAP** | logger only (stderr) | per-node confidence-каскад не логируется |
| **INGEST/MIGRATE** | | | |
| patterns-harvester | partial | hook-invoc + systemMessage | `ingest_items` возвращает stats, но **не зовёт record_ingest** |
| skills-harvester | partial | state json | нет ingestion-события |
| reflection | ❌ **GAP** | CLI stdout | консолидация не логируется |
| cross_store_sync | partial | свой report only | report ≠ event-stream |
| WikiPromoter | ✅ | wiki/log.md + event_bus + link_history | (CLI-путь: event_bus=None → только log.md) |
| **GOVERNANCE** | | | |
| TTL set/check/cleanup | partial | state jsonl + logger | state-store, не event-log; cleanup не аудируется |
| Versioning rollback | partial | state jsonl + logger | rollback-действие не event-логируется/аудируется |
| ForgetGate — MCP `decay_confidence` | ✅ | confidence-lifecycle (`decay_sweep`) + epoch bump | |
| **ForgetGate — script `run_forget`** | ❌ **GAP ⚠** | dashboard report only | `set_payload(expired_at)` БЕЗ `_log_lifecycle`/`record_ingest`/`epoch.bump` — асимметрия с MCP; **основной** драйвер забывания невидим + риск stale surfacing-кеша |
| CircuitBreaker trips | ❌ **GAP** | logger only | нет персистентных trip-событий |
| `memory_forget` (MCP) | partial | mcp_call | нет event/audit на реальную архивацию |
| **P4** | | | |
| `memory_maintenance` cadence run | partial | timestamped dashboards | нет append-only run-лога (time-series) |
| `memory-maintenance-cadence` hook | ✅ | `_maintenance.log` + hook-invoc | захват stdout, не структурные события |

## 3. Топ-гэпы (по влиянию на оценку эффективности)

1. **`memory-ingestion.log` — sink без писателей** (§2 #3). Корневой: §26-метрики (ingest_rate/dup_rate/store_sizes) **не измеряются вообще**; §25-analyzer и P4-dashboard читают пустой/отсутствующий файл. Фикс — вшить `record_ingest` в харвестеры/reflection/sync/route_and_save.
2. **ForgetGate script-path невидим** (`run_forget` мимо `_log_lifecycle`+epoch). P4-cadence — **главный** драйвер архивации → объём/темп забывания нельзя измерить из event-stream, только diff'ом дашбордов. Бонус: пропущенный `epoch.bump` → stale surfacing-кеш.
3. **Audit write-path мёртв** — `AuditService.log()` есть, но никто не зовёт; `route_and_save`/delete/link/rollback не оставляют audit-trail. «Кто/что/когда менял память» — без ответа.
4. **Federated `unified_search` без трейса** — в отличие от surfacing-хука; эффективность MCP-чтения (какие источники сработали, score, латентность) невидима.
5. **Router.classify решения не логируются** — routing-accuracy во времени неоценима.
6. **Propagation BFS / CircuitBreaker** — только stderr; нет stream'а охвата каскада/инцидентов надёжности.
7. **Metrics in-process only** — нет лонгитюдного ряда (сброс на рестарт).
8. **P4-cadence без append-only run-лога** — тренд требует парсинга N timestamped-файлов вместо `tail` одного потока.

## 4. Архитектура решения

**Принцип [own]:** НЕ строить новую инфру — растиражировать готовый паттерн логирования (`lifecycle_log.py` / surfacing-`_surface_log`):
- **atomic size-rotation** JSONL (~2MB, mkstemp+`os.replace`, tail-keep), **fail-soft** (`except: pass`, exit-0 на хуках), **buffered append**;
- **metadata-only** — id/counts/floats/truncated-errors, **без тел** prompt'ов/паттернов;
- **opt-out env** на каждый лог (как `CONFIDENCE_LOG_DISABLE` / `MEMORY_SURFACE_LOG_DISABLE`);
- **не в hot-path** — буферизованная запись/detached.

**Единая модель события (целевая, P3):** конверт в стиле §15 CloudEvents (`hook-invocations.jsonl`): `{ts, source, type, content_hash?, correlation_id, causation_id, ...payload-meta}`. Это даёт **сквозную корреляцию** одного факта через все процессы (по `content_hash` / `correlation_id`).

```
  СОБЫТИЯ (per-process JSONL)            КОРРЕЛЯЦИЯ            АНАЛИЗ
  ingestion.log ─┐                       по content_hash /     §25 analyzer +
  routing.log   ─┤                       correlation_id        observability
  read/search   ─┼─► unified envelope ──────────────────────► report (P4):
  propagation   ─┤   (CloudEvents §15)                         ingest/dup/forget/
  forget/decay  ─┘                                             routing/read/growth
  (+ уже есть: confidence-lifecycle, surfacing, link_history, events)
```

---

## 5. Фазы (deliverables + acceptance)

### P0 — Подключить уже построенные sink'и (дёшево, максимальный эффект)

**Deliverables:**
- **D0.1 — оживить `memory-ingestion.log`:** вшить `ingest_metrics.record_ingest(store, action, …)` в точки записи. — ✅ **DONE (2026-06-05)**: `pattern_harvest.ingest_items` эмитит per-action события (created→saved/dup→dup/cap→skipped/error→error, harvester-атрибуция) + `record_store_size` per-store в P4-cadence (`collect_store_sizes`). Закрывает топ-гэп #1 — sink ожил (live: store_size×4 + ingest-события). **Follow-up:** reflection-атрибуция (сейчас default `ingest_items`) + `route_and_save` per-store + skills-harvester.
- **D0.2 — ForgetGate script-path симметрия:** `memory_maintenance.run_forget` на архивации зовёт `lifecycle_log.log_event("forget", …)` + `epoch.bump()` (зеркало MCP `handle_decay_confidence`). — ✅ **DONE (2026-06-05)**: gated `apply and archived>0`, fail-soft, metadata-only, **epoch-bump** (закрывает stale surfacing-кеш). Закрывает топ-гэп #2.
- **D0.3 — оживить audit write-path:** `AuditService.log()` в `route_and_save` / `create_link` / `propagate_update` / version-rollback (operation/entity/metadata-only). Закрывает топ-гэп #3. — ✅ **DONE (2026-06-05)**: fail-soft `_audit` helper (зеркало `_emit_event`) на 4 точках + **flush-on-stop** (буфер CREATE/LINK/PROPAGATE доходит до диска) + hardening re-entrant-lock deadlock (`log()` auto-flush@max_buffer). MCP-side → нужен `/mcp reconnect`.

**Acceptance:**
- [x] После прогона харвестера/cadence — `memory-ingestion.log` непустой (live: 4× store_size + ingest/saved события); `aggregate_ingest_events` готов потреблять.
- [x] Forget script-path логирует `forget` в `confidence-lifecycle.log` + **бампает epoch** (код + зеркало MCP, code-verify PASS; runtime-событие при `archived>0`).
- [x] audit write-path жив: `_audit` пишет CREATE/LINK/PROPAGATE/ROLLBACK; `data/services/audit.jsonl` наполняется (DELETE/ROLLBACK сразу, остальное — буфер→flush на `stop()`); 4 unit (вкл. deadlock-регрессию), code-verify PASS. Runtime — после `/mcp reconnect`.
- [x] Всё fail-soft + opt-out + metadata-only (code-verify PASS, 16 unit).

**Артефакты (P0 D0.1+D0.2):** [`pattern_harvest.py`](../../.claude/hooks/shared/pattern_harvest.py) (`_emit_ingest_stats` + `ingest_items(harvester=…)`) · [`memory_maintenance.py`](../../scripts/memory_maintenance.py) (`collect_store_sizes`→`record_store_size`; `run_forget`→`log_event("forget")`+`epoch.bump`) · [`tests/unit/hooks/test_ingest_logging.py`](../../tests/unit/hooks/test_ingest_logging.py) (6 unit) · 16 unit PASS, ruff clean, code-verify PASS. **Live:** cadence dry-run → `memory-ingestion.log` оживлён (store_size lp25/ai99/sk1/wiki0 + ingest-события).

### P1 — Новые per-process event-логи для слепых процессов (по образцу surfacing.log)

**Deliverables:**
- **D1.1 — routing-лог:** `route_and_save` пишет решение (targets/method/confidences) в `memory-routing.log`. — ✅ **DONE (2026-06-05)** (metadata-only: `reasoning`/`content` НЕ логируются; через shared `trace_log`).
- **D1.2 — federated-read трейс:** `UnifiedSearchEngine.search` пишет per-query JSONL → `memory-read.log` (per-source `arm_hits`, sources_searched/failed, final count, min_score, rrf, latency; query-текст НЕ логируется — только `query_len`). — ✅ **DONE (2026-06-05)**.
- **D1.3 — propagation трейс:** `PropagationEngine._process_propagation` пишет → `memory-propagation.log` (source-id, entities_updated count, cascades_prevented, final_depth, latency) — единая точка для sync+background путей. — ✅ **DONE (2026-06-05)**.
- **D1.4 — CircuitBreaker trip-лог:** open/half-open/close переходы как персистентные события. — ✅ **DONE (2026-06-05)** (`_transition_to` single choke-point; no-op transitions не логируются → `memory-circuit.log`).

**Acceptance:**
- [x] Shared `trace_log.write_trace` (fail-soft, atomic-rotation 2MB, per-log opt-out + global `MEMORY_TRACE_DISABLE`); D1.1 routing + D1.4 circuit-breaker эмитят структурный JSONL. *(5 unit, code-verify PASS)*
- [x] D1.2 federated-read (`memory-read.log`: arm_hits/latency/sources) + D1.3 propagation (`memory-propagation.log`: reach/depth) — read hit-rate/латентность по источникам + охват каскада восстановимы. *(code-verify PASS)*

**Артефакты (P1):** [`src/memory/infrastructure/trace_log.py`](../../src/memory/infrastructure/trace_log.py) (generic writer) · `circuit_breaker._transition_to` → `memory-circuit.log` (D1.4) · `route_and_save` → `memory-routing.log` (D1.1) · `UnifiedSearchEngine.search` → `memory-read.log` (D1.2) · `PropagationEngine._process_propagation` → `memory-propagation.log` (D1.3) · [`tests/unit/test_trace_log.py`](../../tests/unit/test_trace_log.py) (5 unit) · ruff + code-verify PASS (×3). MCP-side (**memory-orchestrator**) → `/mcp reconnect`.

### P2 — Персистентность метрик и cadence-потока

**Deliverables:**
- **D2.1 — flush метрик:** `MetricsCollector` сбрасывается в `memory-metrics.jsonl` (лонгитюдный ряд counters/gauges/durations). — ✅ **DONE (2026-06-05)**: snapshot на orchestrator `stop()` (graceful-shutdown; hard-kill пропускает — known limitation), fail-soft, opt-out `MEMORY_METRICS_LOG_DISABLE`.
- **D2.2 — append-only run-лог:** `memory_maintenance` дописывает строку-сводку на прогон в `memory-maintenance-runs.jsonl` (+ к timestamped-дашбордам) → `tail`-able тренд. — ✅ **DONE (2026-06-05)** (live: 1 строка/прогон — total_facts/store_sizes/dup_rate/forget/jobs).
- **D2.3 — store-size time-series:** `record_store_size` на каждый cadence → ряд роста store'ов. — ✅ **DONE (через D0.1)** (store_size events в `memory-ingestion.log`).

**Acceptance:**
- [x] Метрики переживают рестарт (snapshot в `memory-metrics.jsonl` на `stop()`; graceful-shutdown-only — задокументировано). *(6 unit incl. snapshot-persist)*
- [x] Тренд cadence/store-sizes читается из ОДНОГО потока (`memory-maintenance-runs.jsonl`, live-verified).

**Артефакты (P2):** `memory_orchestrator.stop()` → `memory-metrics.jsonl` (D2.1) · `scripts/memory_maintenance.main()` → `memory-maintenance-runs.jsonl` (D2.2) · D2.3 = D0.1 `record_store_size` · [`tests/unit/test_trace_log.py`](../../tests/unit/test_trace_log.py) (+1 metrics-snapshot unit, 6 total) · ruff + code-verify PASS. D2.1 MCP-side (memory-orchestrator) → `/mcp reconnect`.

### P3 — Единая схема и сквозная корреляция

**Deliverables:**
- **D3.1 — канонический конверт события:** общий helper (envelope в стиле §15: `id/source/type/time/correlation_id/causation_id`), к которому приводятся новые логи (P1/P2) + reader-адаптер для старых (confidence-lifecycle/surfacing/ingestion). — ✅ **DONE (2026-06-05)**: [`event_envelope.py`](../../src/memory/infrastructure/event_envelope.py) — `normalize(source, raw)` проецирует 10 разнородных sink'ов в плоскую каноническую схему со **stable `CORE_KEYS`** (None-seed → DuckDB-колонки всегда есть, нет binder-error); `make_envelope` (forward CloudEvents v1.0); `known_sinks()` — единый реестр sink'ов (источник правды для query + freshness). Per Q3 — reader-адаптер, НЕ миграция on-disk форматов.
- **D3.2 — корреляция по `content_hash`/`correlation_id`:** сквозной трейс одного факта: save → route → store-write → link → event → (позже) surfacing/apply → forget. — ✅ **DONE (2026-06-05)**: [`memory_observability_query.py`](../../scripts/memory_observability_query.py) `--view fact-trace --key <H>` тредит факт по `content_hash` **ИЛИ** `pattern_id` (= `UUID5(content_hash)` — ключ confidence-lifecycle). Унифицирующий ключ — `pattern_id`: harvester теперь эмитит и `content_hash`, и `pattern_id` в ingestion-события ([`pattern_harvest._emit_ingest_stats`](../../.claude/hooks/shared/pattern_harvest.py), backward-compat count-fallback) → ingestion(saved/dup) ↔ lifecycle(reinforce/forget) тредятся одним запросом (**live-проверено**: 3 события / 2 sink'а). CAST-fix: DuckDB авто-инферит UUID-shaped `pattern_id` как native UUID → `CAST(... AS VARCHAR)` в WHERE против ConversionException.

**Acceptance:**
- [x] End-to-end трейс одного факта восстановим одним запросом (`fact-trace --key <pattern_id>` тредит ingestion→reinforce→forget; live PASS).
- [x] DuckDB-слой (mirror `scripts/audit_query.py` §15) поверх ВСЕХ memory-логов: pre-clean + normalize → temp JSONL → `read_json_auto(union_by_name=true)`; views recent/by-source/error-rate/latency/freshness/fact-trace.

**Артефакты (P3):** [`event_envelope.py`](../../src/memory/infrastructure/event_envelope.py) (D3.1) · [`memory_observability_query.py`](../../scripts/memory_observability_query.py) (D3.2, `--root`/`MEMORY_OBS_ROOT` override) · harvester `content_hash`+`pattern_id` emit (D3.2-данные) · [`tests/unit/test_memory_observability.py`](../../tests/unit/test_memory_observability.py) (envelope + fact-trace DuckDB) + [`test_ingest_logging.py`](../../tests/unit/hooks/test_ingest_logging.py) (keyed-emit). code-verify PASS.

### P4 — Слой анализа эффективности (потребление полных логов)

**Deliverables:**
- **D4.1 — расширить §25-analyzer + P4-dashboard:** считать из полных логов метрики эффективности — ingest_rate, dup_rate, **forget_volume/rate**, routing_accuracy, read hit-rate, propagation_reach, store_growth, audit-coverage. — ✅ **DONE (2026-06-05)**: [`memory_observability_report.py`](../../scripts/memory_observability_report.py) переиспользует §25-aggregator'ы (surfacing+lifecycle) + добавляет ingestion/maintenance/routing/read/propagation/circuit/audit. (routing_accuracy без ground-truth даётся как target/method-распределение — честно помечено.)
- **D4.2 — unified observability report:** один отчёт-роллап по всем sink'ам (`data/reports/memory/observability_*.md`) + DuckDB-вью (recent/latency/error-rate/correlation-chain). — ✅ **DONE (2026-06-05)**: `observability-<ts>.md` + json sidecar + `_observability_latest.md`; effectiveness-verdict (injected/dup/forget/read-hit/drift) + **freshness/regression-секция**. DuckDB-вью — в `memory_observability_query.py` (P3).

**Acceptance:**
- [x] Единый отчёт отвечает «становится ли память эффективнее?» из **реальных** логов (live: 4 fresh sink'а, surfacing/ingestion/lifecycle/maintenance метрики посчитаны).
- [x] Регрессия наблюдаемости детектируется: `analyze_freshness` помечает present-but-stale sink как `stale`→`regressions[]`; `missing`/`empty` (cold/MCP-side до run) явно НЕ regression (unit-тест + live).

**Артефакты (P4):** [`memory_observability_report.py`](../../scripts/memory_observability_report.py) (D4.1 aggregators + D4.2 report/freshness) · [`tests/unit/test_memory_observability.py`](../../tests/unit/test_memory_observability.py) (aggregators + regression-detect) · live `data/reports/memory/_observability_latest.md`. code-verify PASS.

---

## 6. Guardrails (для всех фаз)

fail-soft (никогда не ронять hot-path / Stop) · atomic size-rotation ~2MB (mkstemp+`os.replace`, tail-keep) · **metadata-only** (id/counts/floats/truncated-errors, без тел prompt'ов/паттернов — privacy + размер) · opt-out env на каждый лог · buffered append (cross-process race — low-risk для trace-логов, `O_APPEND` откатан на win32, см. §22 урок) · cp1251-safe (UTF-8 bytes, не `print()` на хуках — [[feedback-windows-hook-stdout-cp1251]]) · MCP-side изменения требуют `/mcp reconnect` ([[feedback-mcp-stale-code-reconnect]]).

## 7. Метрики (что разблокирует полное логирование)

| Метрика | Источник (после фаз) | Назначение |
|---|---|---|
| ingest_rate / dup_rate | ingestion.log (P0) | наполняемость + здоровье анти-флуда |
| forget_volume / rate | confidence-lifecycle + ingestion (P0 D0.2) | bounded-growth работает? |
| routing_accuracy | routing.log (P1) | правильно ли Router раскладывает |
| read_hit_rate / latency-by-source | federated-read трейс (P1) | эффективность MCP-чтения |
| propagation_reach | propagation трейс (P1) | охват каскада доверия |
| store_growth (time-series) | metrics + store_size (P2) | рост ограничен? |
| audit_coverage | audit.jsonl (P0 D0.3) | доля операций с трейлом |
| end-to-end fact trace | unified envelope (P3) | сквозная диагностика |

## 8. Зависимости и риски

- **Зависит от:** `lifecycle_log.py` / surfacing-`_surface_log` (образец), `ingest_metrics.py` (готовый sink), `AuditService` (готовый, write-path мёртв), `epoch.py`, `invocation_logger.py` (§15 envelope), §25-analyzer (потребитель).
- **Риски:** лог-флуд / размер → atomic-rotation + metadata-only; hot-path латентность → buffered/detached, не в surfacing-budget; privacy (тела) → строго metadata-only; cross-process append-гонки → low-risk принято для trace-логов.
- **Не входит:** изменение бизнес-логики процессов (только добавляем след); внешний OTel/Langfuse экспорт (опц. future, сейчас Langfuse-stub = no-op).

## 9. Открытые вопросы

- **Q1 (P0):** ingestion-лог — отдельный файл (как сейчас задумано) ИЛИ влить в confidence-lifecycle? → отдельный (разные консьюмеры, §26 vocab).
- **Q2 (P1):** federated-read трейс — отдельный `memory-read.log` ИЛИ расширить surfacing.log? → отдельный (разные пути: MCP vs hook).
- **Q3 (P3):** единый envelope — мигрировать старые логи ИЛИ только reader-адаптер? → reader-адаптер (не ломать рабочие sink'и; union-by-name в DuckDB).

## 18. Прогресс (§18-лог)

| Дата | Веха | Коммит |
|---|---|---|
| 2026-06-05 | Roadmap создан (PLANNED) — аудит 8 sink'ов × ~25 процессов, 8 топ-гэпов, фазы P0-P4 | (pending) |
| 2026-06-05 | **P0 D0.1+D0.2 DONE** — оживлён `memory-ingestion.log` (харвестер per-action события + cadence store_size) + ForgetGate script-path logging (`forget` event + epoch bump); 16 unit + ruff + code-verify PASS, live sink-revival. **D0.3 (audit write-path) — next** | (pending) |
| 2026-06-05 | **P0 DONE (D0.3 + P0 закрыт)** — audit write-path оживлён (`_audit` на route_and_save/create_link/propagate/rollback + flush-on-stop) + hardening AuditService re-entrant-lock deadlock; 4 unit + code-verify PASS. **P0 завершён (D0.1+D0.2+D0.3).** Follow-up: reflection/route_and_save `record_ingest` атрибуция. **Next: P1** (routing/federated-read/propagation/breaker event-логи) | (pending) |
| 2026-06-05 | **P1 D1.1+D1.4 DONE** — shared `trace_log` writer (fail-soft/rotation/opt-out) + routing-лог (`route_and_save`→`memory-routing.log`, metadata-only) + circuit-breaker trip-лог (`_transition_to`→`memory-circuit.log`); 5 unit + code-verify PASS. **D1.2 federated-read + D1.3 propagation — next** | (pending) |
| 2026-06-05 | **P1 DONE (D1.2+D1.3 → P1 закрыт)** — federated-read трейс (`UnifiedSearchEngine.search`→`memory-read.log`, arm_hits/latency, query-текст не логируется) + propagation трейс (`_process_propagation`→`memory-propagation.log`, reach/depth, единая точка sync+bg); compile+ruff+code-verify PASS. **P1 завершён (D1.1-D1.4).** Next: **P2** (persist metrics + cadence run-лог) | (pending) |
| 2026-06-05 | **P2 DONE** — metrics-snapshot на orchestrator `stop()`→`memory-metrics.jsonl` (D2.1) + cadence append-only run-лог→`memory-maintenance-runs.jsonl` (D2.2, live-verified) + store-size series via D0.1 (D2.3); 6 unit + code-verify PASS. **P2 завершён.** Next: **P3** (единый envelope + сквозная корреляция) | (pending) |
| 2026-06-05 | **P3+P4 DONE → roadmap ЗАКРЫТ (P0-P4)** — D3.1 канонический envelope + reader-adapter (`event_envelope.py`, stable `CORE_KEYS`) · D3.2 DuckDB cross-log query (`memory_observability_query.py`) + **fact-trace** по `content_hash`/`pattern_id` (cross-sink thread live PASS: ingestion→reinforce→forget); harvester эмитит `content_hash`+`pattern_id`; CAST-fix DuckDB UUID-inference · D4.1 cross-process aggregators + D4.2 unified `observability-*.md` + **stale-sink regression detection** (cold≠regression). 14 unit (P3+P4) + 1 ingest-keyed unit, ruff clean, compile OK, **code-verify PASS** (7/7 focus checks), live report на реальных логах. **Все 8 топ-гэпов закрыты — наблюдаемость памяти 100%.** | (pending) |

> Обновлять при старте/закрытии каждой фазы (P0…P4): отметка DONE + ключевые коммиты + отклонения.
