# Roadmap — Memory Full Observability (логирование всех процессов для оценки эффективности)

> **Дата:** 2026-06-05 · **Статус:** 🟢 IN PROGRESS — **P0 ✅ · P1 ✅ · P2..P4 ⏳** · **Родитель:** [27.12 Memory Systems Map §10](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md) · **Смежные:** [§22 confidence](260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md) · [§25 effectiveness](260601_ROADMAP_MEMORY_EFFECTIVENESS.md) · [§26 ingestion](260602_ROADMAP_MEMORY_INGESTION_SYNC.md)
>
> Цель: **каждый процесс памяти оставляет структурный след** (per-event JSONL), чтобы §25-аналитика могла измерять эффективность сквозного цикла **ingestion → consolidation → sync → retrieval → forget**. Инвентаризация — code-grounded аудит 2026-06-05 (8 sink'ов × ~25 процессов, §2).

---

## 0. Промежуточные результаты (2026-06-05)

**Сделано:** **P0 завершён** — 3 из 8 топ-гэпов закрыты. Система памяти получила недостающих **writers** для уже построенных sink'ов + симметрию script/MCP путей. Слепые зоны ingestion/forget/audit стали наблюдаемы.

| Фаза | Статус | Итог |
|---|---|---|
| **P0** Подключить построенные sink'и | ✅ DONE | D0.1 `memory-ingestion.log` **оживлён** (харвестер per-action события + cadence `record_store_size`) · D0.2 ForgetGate script-path → `confidence-lifecycle.log` + epoch bump · D0.3 audit write-path **оживлён** (`_audit` ×4 + flush-on-stop + hardening re-entrant deadlock). **20 unit, 3× code-verify PASS**, live sink-revival |
| **P1** Новые event-логи слепых процессов | ✅ DONE | D1.1 routing + D1.2 federated-read + D1.3 propagation + D1.4 circuit-breaker — все через shared `trace_log`; 5 unit, 3× code-verify PASS |
| **P2** Persist metrics + cadence run-лог | ⏳ PENDING | |
| **P3** Единый envelope + сквозная корреляция | ⏳ PENDING | |
| **P4** Слой анализа эффективности (§25) | ⏳ PENDING | |

**Закрытые топ-гэпы:** #1 (ingestion sink без писателей), #2 (ForgetGate script невидим + epoch-баг), #3 (audit write-path мёртв).
**Остаются:** #4 federated-read трейс, #5 routing-решения, #6 propagation/breaker, #7 metrics persist, #8 cadence run-лог.
**Follow-up P0:** `record_ingest`-атрибуция reflection + `route_and_save` per-store + skills-harvester.
**⚠ Runtime:** D0.3 (MCP-side `memory_orchestrator`/`audit_service`) — нужен `/mcp reconnect`; D0.1/D0.2 (хуки/скрипты) — effective сразу.

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
- **D2.1 — flush метрик:** `MetricsCollector` периодически (Stop / cadence) сбрасывается в `memory-metrics.jsonl` (лонгитюдный ряд counters/gauges/timers).
- **D2.2 — P4 append-only run-лог:** `memory_maintenance` дописывает одну строку-сводку на прогон в `memory-maintenance-runs.jsonl` (в дополнение к timestamped-дашбордам) → `tail`-able тренд.
- **D2.3 — store-size time-series:** `record_store_size` на каждый cadence (через D0.1) → ряд роста store'ов.

**Acceptance:**
- [ ] Метрики переживают рестарт (ряд в файле, не только in-proc).
- [ ] Тренд cadence/размеров store'ов читается из ОДНОГО потока.

### P3 — Единая схема и сквозная корреляция

**Deliverables:**
- **D3.1 — канонический конверт события:** общий helper (envelope в стиле §15: `id/source/type/time/correlation_id/causation_id`), к которому приводятся новые логи (P1/P2) + reader-адаптер для старых (confidence-lifecycle/surfacing/ingestion).
- **D3.2 — корреляция по `content_hash`/`correlation_id`:** сквозной трейс одного факта: save → route → store-write → link → event → (позже) surfacing/apply → forget.

**Acceptance:**
- [ ] End-to-end трейс одного факта через ingestion→consolidation→sync→retrieval→forget восстановим (один запрос по correlation_id/content_hash).
- [ ] DuckDB-слой (как `scripts/audit_query.py` §15) поверх всех memory-логов: union-by-name, ignore-errors.

### P4 — Слой анализа эффективности (потребление полных логов)

**Deliverables:**
- **D4.1 — расширить §25-analyzer + P4-dashboard:** считать из полных логов метрики эффективности — ingest_rate, dup_rate, **forget_volume/rate**, routing_accuracy, read hit-rate, propagation_reach, store_growth, audit-coverage.
- **D4.2 — unified observability report:** один отчёт-роллап по всем sink'ам (`data/reports/memory/observability_*.md`) + DuckDB-вью (recent/latency/error-rate/correlation-chain).

**Acceptance:**
- [ ] Единый отчёт отвечает «становится ли память эффективнее?» из **реальных** логов (не заглушек).
- [ ] Регрессия наблюдаемости детектируется (любой процесс перестал логировать → отчёт это показывает).

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

> Обновлять при старте/закрытии каждой фазы (P0…P4): отметка DONE + ключевые коммиты + отклонения.
