# Roadmap 260708 — Autonomous 1C Debugging: от DAP-parity к agent-driven root-cause

> **Дата:** 2026-07-08
> **Автор запроса:** пользователь — «глубокий анализ 1c-debug-hmr, лучшие практики отладки с GitHub, отладка с максимальной автономностью — реальное чтение кода с реальным получением результата, дорожная карта улучшений»
> **Связано:** [260511 Deep Analysis](260511_DEEP_ANALYSIS_DEBUG_HMR_BEST_PRACTICES.md) (реализовано P0.A–G/P1/P2.A/P3.B), [260511 Deficiencies](260511_ROADMAP_1C_DEBUG_HMR_DEFICIENCIES_FROM_GKSTCPLK_2468.md), [260603 Long-poll ping](260603_ROADMAP_DEBUG_LONGPOLL_PING.md), skill [`1c-debug-hmr`](../../.claude/skills/1c-debug-hmr/SKILL.md), cache [`bp_propagation_race_patterns.md`](../../.claude/skills/1c-debug-hmr/cache/bp_propagation_race_patterns.md)
> **Статус:** RESEARCH + ROADMAP + **W1 РЕАЛИЗОВАН** (2026-07-08, сабмодуль `ce11644`, parent `6030a30f1`, 331 unit passed) + **W2 B5.a/B5.b РЕАЛИЗОВАНЫ** (2026-07-09, сабмодуль `91e89a8`, 352 unit passed, code-verify PASS) + **W2 B3 РЕАЛИЗОВАН** (2026-07-10, 366 unit passed, code-verify PASS)

> **⚙ W1 IMPLEMENTED + LIVE-VERIFIED (2026-07-08):** W1.0 рефактор-фундамент (3 хелпера, дедуп 4+4) + A0 `debug_inspect_frame` + A1 `debug_autotrace` (two-phase) + B2 auto-calibrate offset + C0 `debug_collection_info`/`_page`. 337 unit passed, code-verify PASS. Коммиты сабмодуля: 903f449/9496a2f/b2eb39a/51433c7/ce11644/1af1478/**89fbc5d**.
>
> **Живой E2E (5 прогонов, ИБTransportManagementDevelop):** BP `гкс_ВходнойКонтрольКачества:2333` + trigger `execute_code` → **hit=true, verdict PASS** (`Пакет1` expected=0 actual=0 ✓, `Пакет2` expected=4 actual=4 ✓), frame=2333, `resolved_source` FQN, `locals_mode=auto` (реальные значения рантайма: `ДокументРегистрации=Неопределено`, `Результат=Структура`). **Live-прогон нашёл и починил 3 бага (89fbc5d):** (1) race collect — транзиентный системный spawn-halt принимался за user-hit (фикс: reason="breakpoint"+debounce); (2) `_extract_eval_value` не знал реальную RDBG-форму (`resultValueInfo.valueDecimal` + base64 `pres`); (3) **Ф-2 разрешён**: callStack-массив outermost-first, eval-stackLevel innermost-first → инверсия индексации в bundle И в предсуществующем `eval_locals_auto` (auto-discovery на глубоких стеках парсил внешний фрейм). Плюс порядок: verdict-eval'ы ПЕРЕД bundle (окно halt server-контекста ~1-2с). **Находка окружения:** `гкс_ОтладкаВыполненияКода` ОТСУТСТВУЕТ в живой БД (пересоздана из .dt?) — Шаблон 6 (JOB-harness) сейчас сломан; закроется B1/ADR-049 (worker в расширении MCP_Сервер). Отложено: C0.3 авто-paging в A0, transport (a) HTTP one-call.

> **⚙ W2 B3 IMPLEMENTED (2026-07-10):** event-driven long-poll wait — `debug_autotrace` collect больше не крутит фиксированный 0.3s poll-loop, а ждёт `asyncio.Event` (`RDBGClient._get_stop_event`, lazy loop-bound, HMR-safe), взводимый в `_handle_command` (`_signal_bp_stop`) ТОЛЬКО на user-visible BP-стоп (`stop_by_bp and not stop_suppressed`). Новый module-level `_await_bp_stop(client, timeout_sec)` сохраняет предикат старого цикла байт-в-байт (reason="breakpoint" + 0.15s debounce + re-check в `_stopped_targets`); Event = wakeup-hint, `_stopped_targets` — source of truth. Инвариант против lost-wakeup: между re-check предиката и `event.wait()` нет `await` (продюсер не вклинится), state обновляется ДО `set()`, `clear()` после пробуждения безопасен; ≤1.0s cap на `wait_for` = eventual-guarantee даже при пропущенном сигнале. Trap-latency: с poll-гранулярности до event-dispatch (~0.1s active ping-каденс). Контракт `debug_autotrace` (`{verdict, raw}`, `raw.hit`/`waited_sec`, Continue в finally) не изменён. **+14 unit (`tests/test_longpoll_b3.py`: Event lifecycle / предикат+debounce / event-driven wakeup <0.5s / safety-net без сигнала / `_handle_command` signals / collect hit+NO_HIT) → 366 passed**, code-verify PASS (behavior-preservation + async race-safety, 7/7). `_AutotraceClient` mock расширен зеркалом event-surface. Осталось в W2: **B1** (persistent JOB-контекст, ADR-049, env-heavy — BSL-worker в расширении MCP_Сервер) + **B5.c/d** (file-cleanup).
>
> **⚙ W2 B5 IMPLEMENTED (2026-07-09, сабмодуль `91e89a8`):** **B5.a portability** - `BSL_DEBUG_CONFIG_SRC_MAP="Alias=path;..."` (alias -> config_src, `=`-сепаратор из-за `:` в Windows-путях) + per-alias `UUIDIndex`-реестр (свой cache-файл на каждый config_src через `_cache_path_for` sha1); `set_active_config` вызывается в `RDBGClient.__init__` (одно live-соединение за раз -> module-global точен); `resolve_uuid`/`get_source_info` получили опц. `alias` (fallback на `_active_alias`). Разблокирует отладку SVETLY/MFM без правки кода. **No-op при незаданном env** - byte-identical маршрут на default singleton (code-verify behavior-preservation PASS; покрыты `_enrich_stack`/`autonomy.read_source_context`/`inspect_frame` - все module-level вызовы полагаются на active alias, выставленный при connect). **B5.b recursive cache-invalidation** - `_src_fingerprint` `{max_mtime,count,total_size}` над `*.mdo` (stat-only, без чтения) вместо coarse top-level dir-mtime, который НЕ ловил вложенные `.mdo`-правки (класс stale-cache); старые `src_mtime`-кэши инвалидируются и ребилдятся. **352 unit passed (+12: парсинг map вкл. Windows-пути, alias-роутинг, active-config, fingerprint-инвалидация на nested edit/add/remove)**, code-verify PASS. **Осталось в B5** (отложено, file-cleanup): B5.c архивировать ad-hoc `test_rdbg*.py`/`.log` из корня сабмодуля; B5.d вынести Java-артефакты (`bsl-debug-server-1.1-SNAPSHOT.jar` и пр.). **Далее W2:** B1 (persistent JOB-контекст, ADR-049, env-heavy - BSL-worker в расширении MCP_Сервер) + B3 (long-poll ping, event-loop).

---

## §0. TL;DR

Отладчик `1c-debug-hmr` за roadmap'ы 260508→260511 достиг **DAP-feature-parity 14/19** (conditional/hit-count BP, logpoints, source-mapping, exception BP, coverage, snapshot-replay, warm-pool arming, HMR persistent session). Инструменты **живые и проверены сегодня** (health-check: `dbgs :1550` ✅, `ragent -debug -http` ✅, 5 инфобаз ✅).

**Пробел, который предыдущие карты НЕ закрывали:** всё это — *ручные примитивы*. Агент (Claude) до сих пор оркеструет отладку пошагово: connect → set_bp → trigger → ping×3 → stack → variables → step. Каждый шаг — отдельный tool-call с ручным разбором JSON. **Нет слоя автономности**: агент не формулирует гипотезу, не ставит BP автоматически «где сломается», не читает состояние и не верифицирует гипотезу в одном замкнутом цикле.

Эта карта добавляет **три класса улучшений**:
- **Эпик A — Autonomy Orchestration Layer** (главная новизна): meta-tools, которые сворачивают «гипотеза→точка→запуск→чтение→вердикт» в один автономный проход.
- **Эпик B — Root-fixes надёжности**: корневые фиксы хронических болей (эфемерный JOB: lifetime <100ms + halt-окно 1-2с, сдвиг строк src↔deployed, long-poll ping).
- **Эпик C — Remaining DAP gaps**: function BP, data BP (watch), drop-frame alternative, обогащение replay.

---

## §1. Глубокий анализ текущего инструментария (32 tools)

### 1.1 Слои архитектуры

```
Claude (агент-оркестратор)
   │  32 MCP-tools (ручные примитивы)
   ▼
mcp_hmr_proc.py  ──watchfiles──►  live-reload без потери session
   │  stdio
   ▼
mcp_debug_server.py (4083 строки)  ──►  RDBGClient (HTTP к dbgs.exe :1550)
   │                                       ├─ bsl_locals.py    (парсинг BSL-локалов)
   │                                       ├─ uuid_index.py    (UUID→FQN→file)
   │                                       ├─ logpoints.py     (tracepoint eval+JSONL)
   │                                       ├─ coverage.py      (genericCoverage.xml)
   │                                       ├─ snapshot.py      (replay .jsonl)
   │                                       ├─ exception_bps.py (фильтры)
   │                                       ├─ bp_conditions.py (hit-count)
   │                                       └─ system_stops.py  (cascade auto-Continue)
   ▼
dbgs.exe :1550  ──►  rphost / ManagedClient (debug targets)
```

### 1.2 Что реализовано (сильные стороны)

| Класс | Инструменты | Зрелость |
|---|---|---|
| Управление сессией | connect (5 recycle-стратегий), disconnect, ping (+no_fire_diagnostics), targets, target_state, attach_targets, wait_for_target, launch_thin_client, health_check, **capture_mode** (sticky re-arm эфемерных JOB) | ✅ production, live-verified |
| Breakpoints | set_breakpoint (condition + hit_condition), set_logpoint, get_breakpoints, break_on_next, **calibrate_lines/calibrate_result** | ✅ + калибровка (2026-07-07) |
| Warm-pool | arm_warm_rphosts, arm_next_rphost (silent) | ✅ закрывает RC2 через JOB |
| Inspection | stack_trace (+resolved_source per frame), variables (auto-discovery), evaluate (composite types) | ✅ live |
| Execution | step (Continue/Step/StepIn/StepOut) | ✅ |
| Coverage/Artifacts | coverage_register, coverage_export, session_summary(artifacts ZIP) | ✅ SonarQube-compatible |
| Exception BP | set/clear/list_exception_bp (message+module фильтры) | ✅ |
| Replay / Diff | session_record, replay_list, replay_seek, **session_diff** (regression verdict) | ⚠ post-mortem, НЕ true time-travel |
| HMR | persistent session через `.active.json` | ✅ переживает restart |

**DAP-coverage: 14/19 industry-standard features** (было 8/19 до 260511).

### 1.3 Хронические боли (корневые ограничения, НЕ закрытые)

| # | Боль | Симптом | Текущий workaround | Корень |
|---|---|---|---|---|
| **P-1** | Эфемерный JOB — **два разных окна**: (a) lifetime rphost **<100ms** (spawn→строка→quit) — гонка attach/BP; (b) halt-окно после fire BP ≈ **1-2 с** — платформа принудительно возобновляет | (a) BP молча не fire (attach не успел); (b) `variables`/`evaluate` успевают, `step` — нет; «Предмет отладки не зарегистрирован» | (a) `arm_next_rphost`/`capture_mode` (sticky re-arm); (b) logpoint (inline eval) вместо интерактива; персистентный контекст (тонкий клиент) | Платформа не имеет paused-on-entry для JOB и force-resume'ит halt server-контекста |
| **P-2** | Сдвиг строк src↔deployed | BP по git-строке молча не fire'ит (кейс: 67→70, +3) | `calibrate_lines` (silent-веер) — *детектирует*, но не устраняет | git-исходники систематически отстают от развёрнутой конфигурации |
| **P-3** | Ping-polling вместо long-poll | 3 итерации × 2с задержки на каждый trap | ping×3 + no_fire_diagnostics | RDBG event-pull синхронный; нет long-poll-обёртки (частично адресовано в 260603) |
| **P-4** | Warm-pool HTTPService BP ceiling | pre-existing rphost невидим, BP не fire | JOB-based execution (Шаблон 6) — обходной, требует `гкс_ОтладкаВыполненияКода` в БД | Vendor-level: RDBG не умеет attach-by-PID (подтверждено XSD 40+ команд, yukon39, EDT) |
| **P-5** | Ручная оркестрация | агент делает 6-10 tool-calls на один trap, вручную парсит JSON | шаблоны 1-6 в SKILL | **Нет meta-tool автономного цикла** — центральная тема этой карты |

**Незадействованные возможности RDBG (потенциал):**
- **`valueModified`/`setValue`** — в enum событий есть, но запись значений переменных НЕ реализована (`_handle_command` → `Skipping`). Разблокирует runtime hypothesis-test (C1) и drop-frame-эмуляцию (C5).
- **`measureResultProcessing`** — RDBG умеет замеры производительности (профилирование), no-op ветка. Потенциал для perf-hunting (см. 260511 BP-4).
- **Warm-pool P0.5** — `getDbgAllTargetStates` фундаментально не видит pre-existing HTTP-service rphost (нет cluster-UUID→debug-UUID mapping API). Vendor-level ceiling; обходится JOB-путём (Шаблон 6) и `capture_mode`.

---

## §2. Лучшие практики отладки (GitHub / индустрия) — срез с фокусом на автономность

> Дополняет §3 из 260511 (там — feature-parity фокус: DAP conditional/logpoint/coverage). Здесь — **автономность агента** и **надёжность**.

### 2.1 Debug Adapter Protocol — канонические фичи, которых ещё нет

[microsoft/debug-adapter-protocol](https://github.com/microsoft/debug-adapter-protocol). Не закрыто у нас:
- **`FunctionBreakpoints`** — BP по имени метода без указания строки (устойчив к сдвигу строк P-2!).
- **`DataBreakpoints`** — halt при изменении значения переменной/реквизита (watchpoint).
- **`setExpression`** — присвоить значение переменной в рантайме (предпосылка для drop-frame-эмуляции).
- **`gotoTargets`/`goto`** — переместить указатель исполнения (аналог drop-frame).
- **`stepInTargets`** — выбор, в какой вызов шагнуть на строке с несколькими вызовами.
- **`completions`** — автодополнение в evaluate-контексте (полезно агенту для валидных выражений).
- **`Variables` paging** (`start`/`count`) — постраничное чтение больших коллекций (ТаблицаЗначений на 10k строк).

### 2.2 Chrome DevTools Protocol — auto-attach как модель автономности

Из кэша [`bp_propagation_race_patterns.md`](../../.claude/skills/1c-debug-hmr/cache/bp_propagation_race_patterns.md): CDP `Target.setAutoAttach({waitForDebuggerOnStart:true})` — **каждый новый worker рождается на паузе**, адаптер вооружает BP до `runIfWaitingForDebugger`. Мы эмулируем это через `arm_next_rphost` + drain-window 150ms. **Применимо:** сделать auto-attach политикой по умолчанию для JOB-траекторий (Эпик B1) — устранит гонку P-1 на корне, а не обходом.

### 2.3 Record-replay: rr / Microsoft TTD / replay.io

- **Mozilla rr** — детерминированный record всего процесса, reverse-execution. Недостижимо для RDBG (нет CPU-record).
- **Достижимо у нас — «детерминированный event-log replay»**: snapshot.py уже пишет `{ts, target, stack, variables}`. Расширить до **causally-ordered event stream** (BP fires + evaluated invariants + переходы состояния РС) → `replay_seek` навигация вперёд/назад по *логическим* событиям, а не только по индексу. Это «poor-man's TTD» — достаточно для post-mortem «какая регистрация фейлила первой».

### 2.4 LLM-driven autonomous debugging (главный источник для Эпика A)

> **Сквозной вывод свежих работ (2025-2026): агенту нужны высокоуровневые, богатые состоянием примитивы (frame-bundle, trace-variable, run-diff), а НЕ тонкие DAP-атомы (`step`/`variables` по одному).** Каждая атомарная команда = целый inference-цикл ради осколка состояния → агент выжигает бюджет в бесплодных петлях. Это и есть главный рычаг автономности при том же RDBG-транспорте.

- **ADI — Agent-centric Debugging Interface** ([arxiv 2604.24212](https://arxiv.org/html/2604.24212)): функционально-уровневые команды поверх **Frame Lifetime Trace** — аргументы + возврат + все изменения состояния функции одним богатым бандлом; on-demand инструментирование только текущего фрейма.
- **InspectCoder** ([arxiv 2510.18327](https://arxiv.org/html/2510.18327v1)): 4 примитива `set_breakpoint / control_execution / interact_code / propose_repair`; агент трассирует подозрительную переменную **вместе с её upstream-переменными** и **модифицирует состояние на паузе для проверки гипотез без правки файлов** (обратимый эксперимент). Middleware `InspectWare` абстрагирует 5 режимов сессии и **фильтрует шумный вывод**. **1.67–2.24× эффективнее** базового REPL-степпинга.
- **SWE-Doctor** ([arxiv 2607.00990](https://arxiv.org/html/2607.00990)): «runtime-grounding» — диагноз принимается **только** если подтверждён исполнением/отладчиком; текстовые догадки из кода отвергаются. Структурированный diagnosis-record (fault location, runtime symptom, propagation path, observed values). **+8.9 п.п.** на SWE-bench Pro. Прямо перекликается с нашим ADR-035 «live BP-trace mandatory».
- **AutoSD / scientific debugging**, **debug-gym** ([arxiv 2503.21557](https://arxiv.org/pdf/2503.21557)), **AgentStepper** ([arxiv 2602.06593](https://arxiv.org/html/2602.06593v1)) — циклы «гипотеза → эксперимент отладчиком → верификация».

**Применимо к нам:** это ядро Эпика A. Frame-bundle (`debug_inspect_frame`) заменяет цепочку `stack_trace`→`variables`→N×`evaluate`; trace-variable = InspectCoder-паттерн поверх наших logpoints+coverage; runtime hypothesis-test = evaluate-присваивание (у нас `valueModified`/`setValue` есть в RDBG-enum, но **запись значений НЕ реализована** — код-агент подтвердил, ветка `_handle_command` просто `Skipping`).

### 2.5 1С-специфика: yukon39/bsl-debug-server + Coverage41C

- **yukon39** (Java DAP для 1С) — reference RDBG wire-protocol; подтверждает: нет attach-by-PID, `BreakpointsManager` пассивен. Мы уже опережаем его (drain-window, silent-arm).
- **Coverage41C** (1c-syntax) — тот же RDBG, genericCoverage.xml. Мы реализовали native-аналог. Возможна интеграция precise callCount (block coverage) — Эпик C.

### 2.6 Надёжность debug-адаптеров

- **Session recovery**: у нас `.active.json` + UI+ escalation — сильно. Добавить heartbeat-детект «dbgs умер» и авто-reconnect.
- **Ephemeral-target handling**: CDP/DAP держат paused-on-entry; наш JOB умирает за 1-2с (P-1). Root-fix — Эпик B1.

---

## §3. Дорожная карта улучшений

> Приоритет: **A (автономность) > B (root-fixes) > C (DAP-gaps)**. A и B дают наибольший leverage: A убирает ручную оркестрацию (P-5), B устраняет хронические гонки (P-1/P-2/P-3).

**Легенда статуса (обновлено 2026-07-09):** ✅ реализовано · 🟡 частично · ⬜ не начато. Детали выполненного - в статус-блоке вверху карты (W1 + W2 B5.a/b).

### ЭПИК A — Autonomy Orchestration Layer 🎯 (главная новизна)

Цель: свернуть «реальное чтение кода с реальным получением результата» в автономные meta-tools. Агент задаёт *намерение*, wrapper исполняет весь цикл и возвращает **готовый вердикт**, а не сырой JSON для ручного разбора.

| ID | Инструмент | Что делает | Усилие | Риск | Ценность |
|---|---|---|---|---|---|
| ✅ **A0** | `debug_inspect_frame(target_id?, stack_level=0, context_radius=3)` | **Топ-идея обоих агентов (ADI/InspectCoder frame-bundle).** Один вызов = богатый бандл: фрейм + `resolved_source` + все локали (auto-discovery через `bsl_locals`+batch-`evaluate`) + аргументы + исходник строки ±`context_radius`. Заменяет дорогую цепочку `stack_trace`→`variables`→N×`evaluate` одним ответом | ~3ч | low (композиция) | ★★★★★ №1 по ценности×применимости |
| ✅ **A1** | `debug_autotrace(object_id, line, module_type, trigger, expect?)` | Один вызов: set_bp(+calibrate) → arm_next_rphost → исполняет `trigger` → ping-loop до fire → `inspect_frame` (A0) → (опц.) сверка с `expect` → **Continue** (release). **Контракт возврата — `verdict` + `raw` (см. дизайн-ноту ниже).** Сворачивает Шаблоны 5/5a/6 в atomic-операцию | ~4ч | low | ★★★★★ убирает P-5 |
| **A2** | `debug_root_cause(trigger, exception_filter?)` | На unhandled exception авто-собирает: полный стек + локали **каждого** фрейма + `resolved_source` + значение виновника + JSONL-снимок → структурированный **diagnosis-record** (SWE-Doctor: fault location, runtime symptom, propagation path, observed values). ⚠ Зависимость: полный обход фреймов на **эфемерном JOB** не влезает в halt-окно 1-2с → до B1 деградирует до top-N фреймов (wrapper собирает inline в момент halt, как logpoint); полный обход — после B1 (W2<W3 ✓) | ~3ч | low | ★★★★★ инцидент-разбор |
| **A3** | `debug_trace_variable(name, object_id, method, trigger)` | **InspectCoder-паттерн.** Авто-logpoint'ы на все строки-присваивания `name` + upstream-переменные → прогон → таймлайн значений `[{line, value, ts}]`. База (logpoints+coverage) готова | ~4ч | low | ★★★★ «откуда взялось это значение» |
| **A4** | `debug_diff_runs(trigger_ok, trigger_fail, watch[])` | Differential debugging поверх `session_record`+`session_diff`: два прогона, на общих точках снимает `watch`, возвращает **первую точку расхождения** (bisect по состоянию). «Работало вчера — сегодня нет» | ~4ч | medium | ★★★★ регрессии |
| **A5** | `debug_hypothesis(assertions[])` | Батч гипотез `{object_id,line,expr,expected}` → условные BP → прогон → per-assertion PASS/FAIL с actual. Runtime-grounded verify-цикл в один вызов | ~3ч | low | ★★★★ verify-этап pipeline |
| **A6** | Session-режимы + «валидные следующие действия» | InspectWare-enum (Start/Runtime-State/Runtime-Error/Post-Mortem/Done) в каждом ответе tool'а + `correlation_id` через всю сессию (переиспользовать CloudEvents/traceparent контур фреймворка) → агент реже дёргает невалидные команды на эфемерных targets; полный аудит-трейл | ~2ч | low | ★★★ |

**Дизайн-нота A1 — контракт возврата (`verdict` + `raw`)** (решение §5.2, 2026-07-08):
Все autonomy-tools (A1/A2/A5) возвращают **и** машинный вердикт, **и** сырое состояние — агент не заперт в решении wrapper'а, но и не обязан парсить сырьё, когда `expect` дан:
```jsonc
{
  "verdict": {                    // null, если expect не передан
    "status": "PASS|FAIL|NO_HIT|INCONCLUSIVE",
    "reason": "expected line 70, got 70; Итог=Ложь ≠ expect Истина",
    "checked": [{"expr": "Итог", "expected": "Истина", "actual": "Ложь", "ok": false}]
  },
  "raw": {                        // ВСЕГДА присутствует — источник истины для агента
    "hit": true, "line": 70, "frame": {...resolved_source...},
    "variables": {...}, "stack": [...], "target_id": "..."
  }
}
```
Принцип (InspectWare/SWE-Doctor): wrapper даёт **готовое суждение по явному `expect`**, но `raw` — единственный источник истины; при `verdict.status ∈ {INCONCLUSIVE, NO_HIT}` или отсутствии `expect` агент судит сам по `raw`. Wrapper НЕ скрывает состояние за вердиктом.

**Acceptance A:** BP-верификация одной точки = **1 tool-call** (`debug_autotrace`) вместо 6-10. Инспекция остановленного фрейма = **1 tool-call** (`debug_inspect_frame`) вместо 3+N. Root-cause упавшего проведения = **1 tool-call** (`debug_root_cause`).

**Интеграция:** `implement-1c-task` Этап 5.x (8-шаговый протокол) → заменяется на `debug_autotrace` per точка; `analyze-1c-task --trace` Phase 2.5 → `debug_hypothesis`.

### ЭПИК B — Root-fixes надёжности

| ID | Задача | Корень | Подход | Усилие | Риск |
|---|---|---|---|---|---|
| **B1** | Persistent JOB-контекст (P-1, **оба окна**) | (a) lifetime rphost **<100ms** — гонка attach/BP; (b) halt-окно 1-2с — платформа force-resume'ит | Спавнить **долгоживущий** debug-worker `mcp_ОтладкаВыполненияКода.ВыполнитьКодСУдержанием` **в расширении `MCP_Сервер`** ([ADR-049](../../.claude/skills/architecture-research/adr/049-debug-worker-in-mcp-server-extension.md)) — после исполнения держит контекст через ожидание сигнала (флаг в РС/врем.хранилище), пока агент читает/шагает; освобождение по `debug_step(Continue)`. Убирает гонку на корне (CDP-модель paused-on-entry). Заодно оформить существующий `debug_capture_mode` (sticky re-arm) как дефолт-политику в начале записи сессии | ~5ч | medium (BSL в расширении + dump-live-first деплой) |
| ✅ **B2** | Sync deployed↔src строк (P-2) | git отстаёт от развёрнутого; `calibrate` — ручной per-module workaround | (a) auto-`calibrate` встроить в `set_breakpoint` по умолчанию (offset применяется молча); (b) preflight-детект «dump живой конфы новее git» → предупреждение; (c) кэш offset per-module в `.active.json`. **Синергия с C1 (function BP устойчив к сдвигу вообще)** | ~3ч | low |
| ✅ **B3** | Long-poll ping (P-3) | синхронный event-pull, латентность = ping-sleep (2с idle) | ✅ **РЕАЛИЗОВАНО 2026-07-10:** `debug_autotrace` collect ждёт `asyncio.Event` (`_await_bp_stop`), не 0.3s sleep-loop; предикат старого цикла сохранён (reason="breakpoint"+debounce); Event взводится в `_handle_command` на user-visible BP-стоп; ≤1s cap = eventual-guarantee. Контракт A1 не тронут (§7.6 порядок соблюдён). Adaptive ping-каденс (260603, active=0.1s) уже закрыл 6с→<1с; B3 убрал остаточную poll-гранулярность collect-фазы | ~3ч | medium (event-loop) |
| **B4** | dbgs heartbeat + auto-reattach recovery | dbgs может умереть; **UI+ revocation root-cause неизвестен** (RDBG произвольно отзывает UI+ между операциями) | Health-probe в ping-loop: при потере :1550 или UI+ — авто-reconnect + `_reapply_bp_workspace` (метод есть) + replay `.active.json`, surface в статусе | ~2ч | low |
| 🟡 **B5** | Переносимость + housekeeping (техдолг код-агента) | `uuid_index.py:66-69` **hardcoded** `C:\1С-Framework\ИБTransportManagementDevelop\…` → блокер на др. ИБ (SVETLY/MFM); UUID-cache invalidation по mtime **корня** src (coarse — вложенный `.mdo` не инвалидирует); ~30 `test_rdbg*` + `.log` в корне; неиспользуемые Java-артефакты (jar 12МБ + vsix 11МБ + `src/`) | **(a) ✅** config-path через env `BSL_DEBUG_CONFIG_SRC_MAP` per-alias + per-alias `UUIDIndex`-реестр (сабмодуль `91e89a8`); **(b) ✅** рекурсивный fingerprint `{max_mtime,count,total_size}` для cache-invalidation; **(c) ⬜** убрать test_rdbg* в `archive/` или удалить; **(d) ⬜** вынести Java-артефакты | ~3ч | low |

**Acceptance B:** B1 → интерактивный step по JOB-таргету работает (сейчас невозможно из-за <100ms окна). B2 → BP по git-строке fire'ит без ручной калибровки в 95% случаев. B3 → trap-latency с ~6с (3×2с) до <1с. B5 → отладчик работает на `SVETLY`/`MFM` без правки кода.

### ЭПИК C — Remaining DAP-gaps (после A/B)

| ID | Фича | Реализуемость в RDBG | Усилие | Приоритет |
|---|---|---|---|---|
| ✅ **C0** | **Variables paging (`indexedVariables`/`namedVariables`)** | **Оба агента: критично именно для 1С.** `ТаблицаЗначений`/`Массив`/`Соответствие`/`РезультатЗапроса` бывают огромными — сейчас агент получает обрезку ИЛИ взрывает контекст. Ленивый доступ `variables(ref, start, count)` | ~2ч | ★★★★★ (узкое место, DAP-канон) |
| **C1** | `setVariable`/`setExpression` через evaluate-присваивание | Разрешить `evaluate` **мутирующих** выражений (`Перем = Значение`) на паузе → runtime hypothesis-test без правки BSL (InspectCoder reversible experiment). `valueModified`/`setValue` в enum есть, но не задействованы. **Предпосылка для C5 drop-frame-эмуляции.** ⚠ Guard: перед мутацией сохранять старое значение (`{old, new}` в ответе) — обратимость эксперимента; та же security-нота, что у logpoints (BSL исполняется в rphost) | ~2ч | ★★★★ |
| **C2** | Function BP (по имени метода) | Резолв метод→строка через `uuid_index`+`bsl_locals` (парсим `Процедура/Функция`), обычный BP на первую исполняемую. **Устойчив к P-2 сдвигу строк** | ~3ч | ★★★★ (синергия с B2) |
| **C3** | `breakpointLocations` + AST-усиление calibrate | Вернуть валидные исполняемые строки модуля (закрывает класс «BP на не-исполняемой строке»); усилить `bsl_locals` regex → полноценный AST из BSL Language Server (границы процедур, локали) | ~4ч | ★★★ |
| **C4** | Data BP / watchpoint | RDBG нет native; эмуляция C1+A3: условный BP на присваиваниях + сравнение с прошлым значением (polling watch) | ~4ч | ★★★ |
| **C5** | Drop-frame / goto | **Split-defer (§5.3).** Истинный goto отсутствует в RDBG enum (Step/StepIn/StepOut/Continue) → **defer до vendor**. 80% ценности закрывает C1 `setExpression`; оставшиеся 20% (перезапуск метода) — композицией B1+C1+StepOut, не новым примитивом. Выделенный goto НЕ реализуем в текущем RDBG | — | ⏸ defer |
| **C6** | Precise coverage (callCount) + семантический replay-seek | Block-level счётчики → genericCoverage `count=`; индекс по replay-логу (TTD-timeline-стиль) → `replay_seek("первый halt где Итог<0")` вместо числового индекса | ~4ч | ★★★ |
| **C7** | Perf-профилирование через `measureResultProcessing` | RDBG **нативно** умеет замеры производительности — событие в enum, сейчас no-op ветка (`_handle_command` → Skipping). Задействовать: `debug_profile_start/stop` → per-method времена → hotspot-отчёт. Закрывает perf-hunting сценарий (260511 BP-4) без массовых logpoint'ов | ~4ч (research 1ч: формат события) | ★★★ (backlog W5+) |

**Операционные ноты реализации (уроки прошлых итераций):**
1. **HMR watch-list:** каждый новый модуль (`autonomy.py` и т.п.) добавлять в `--watch` аргументы `.mcp.json`, иначе wrapper не перезагрузится при правке (урок P0.D: `system_stops.py` не был в watch-list → фикс «не работал» до `/mcp reconnect`). Новые **параметры** существующих tools всё равно требуют `/mcp reconnect` (harness кеширует JSON-schema).
2. **Безопасность:** `trigger` в A1/A2/A3 и присваивания C1 исполняют произвольный BSL в rphost — та же security-нота, что у logpoints (не передавать untrusted, `security_note` в ответе при мутациях).
3. **Измеримость acceptance:** autonomy-tools логируют в существующий контур `data/tool-effectiveness.jsonl` (`tool_calls_saved` = сколько ручных вызовов заменил один meta-call) — подтверждаем «12→1» фактическими данными, не декларацией.
4. **Тесты:** каждый A/B/C-инструмент — unit (mock RDBGClient, как 222 существующих) + 1 live-smoke на `ИБTransportManagementDevelop`; интеграция в `implement-1c-task` Этап 5.x — только после live-smoke PASS.

---

## §4. Последовательность и оценки

| Волна | Состав | Усилие | Результат |
|---|---|---|---|
| ✅ **W1** (автономность-ядро) | **W1.0 (рефактор-фундамент)** + A0 + A1 + C0 + B2 | ~13.5–14.5ч (декомпозиция §7.7) | Frame-bundle в 1 вызов; autotrace (two-phase, one-call как enhancement); paging больших коллекций; BP fire'ит без ручной калибровки |
| 🟡 **W2** (надёжность) | B1 + **B3 ✅** + B5 (**B5.a/b ✅**, B5.c/d ⬜) | ~11ч | Интерактивный JOB-step (B1 pending); **sub-second trap ✅** (B3); **переносимость на SVETLY/MFM ✅** (B5) |
| **W3** (диагностика) | A2 + A3 + C1 + B4 | ~11ч | Root-cause diagnosis-record; trace-variable; runtime hypothesis-test; auto-reattach |
| **W4** (глубина) | A4 + C2 + A6 | ~9ч | Differential debug; function BP; session-режимы + correlation_id |
| **W5** (nice-to-have) | A5 + C3 + C4 + C6 | ~15ч | Verify-батч; breakpointLocations; watchpoint; precise coverage + семантический replay |
| **Defer** | C5 (истинный goto/drop-frame) | — | **до vendor-расширения RDBG** (решение §5.3); 80% ценности закрывает C1 (W3), остаток — композиция B1+C1+StepOut |

**ROI:** W1 (~12ч) даёт наибольший leverage — `debug_inspect_frame`+`debug_autotrace`+paging убирают P-5 (ручная оркестрация, 6-10 tool-calls → 1) и P-2 (сдвиг строк). W1+W2+W3 (~34ч) закрывают ≥80% боли автономной отладки. По данным InspectCoder — высокоуровневые примитивы дают **1.67–2.24× эффективности** vs атомарный степпинг.

## §5. Открытые вопросы (для approve)

1. ~~**B1 требует BSL-модуль в БД** — деплоить во все ИБ или только dev?~~ **✅ РЕШЕНО ([ADR-049](../../.claude/skills/architecture-research/adr/049-debug-worker-in-mcp-server-extension.md)):** модуль `mcp_ОтладкаВыполненияКода` идёт в **расширение `MCP_Сервер`** (`external/1c_mcp/`, префикс `mcp_`, dump-live-first деплой) — не трогаем типовую конфигурацию, деплой существующим пайплайном расширения, доступен везде, где расширение установлено. Рекомендация: позже консолидировать туда же существующий `гкс_ОтладкаВыполненияКода` (Шаблон 6, сейчас в основной конфе) — единый дом debug-хелперов.
2. ~~**A1 verdict-семантика:** wrapper судит или агент?~~ **✅ РЕШЕНО (§3 дизайн-нота A1):** возвращать **оба** — `verdict` (машинное суждение по явному `expect`, может быть `null`) + `raw` (всегда, единственный источник истины). Wrapper не прячет состояние за вердиктом; при `INCONCLUSIVE`/`NO_HIT`/без-`expect` судит агент.
3. ~~**C5 drop-frame:** research feasibility или defer?~~ **✅ РЕШЕНО (split-defer):** расщепить на две возможности. **`setExpression` (C1) — делать** (~2ч): даёт ~80% ценности drop-frame (runtime-гипотеза без redeploy — InspectCoder «обратимый эксперимент»). Research = тайм-бокс **≤30 мин**: принимает ли RDBG `evalExpr` side-effecting присваивание в scope фрейма, ЛИБО пишет ли `valueModified`/`setValue` (в enum есть). **Истинный goto/drop-frame — defer до vendor** (нет в `DebugStepAction` enum = Step/StepIn/StepOut/Continue). Оставшиеся 20% (перезапуск метода с начала) достигаются **композицией** B1(hold-контекст)+C1(правка входов)+StepOut/re-entry — не новым RDBG-примитивом. Реальный кейс: GKSTCPLK-2468 v1→v2 (`гкс_ДокументРегистрации` runtime=ФНП≠статик-РегистрацияПЛК) — цикл проверки гипотезы 1-2 мин×5 → 10-15 сек.
4. ~~**Приоритет автономности vs parity:** A важнее C?~~ **✅ РЕШЕНО (A — множитель, C — аддитив):** Эпик A приоритетнее, потому что A **снижает стоимость каждой** отладочной сессии (12 tool-calls → 1), а C добавляет по одной возможности, не трогая стоимость оркестрации. Реальный кейс GKSTCPLK-2634 (верификация отката транзакции): ручной Этап 5.x = ~12 вызовов с ручным парсингом JSON → `debug_autotrace` = 1 вызов. Фичи C ценнее **после** A (композируются внутри A0/A1). **Исключение:** `C0` variable paging — со-приоритет с A (жёсткий блокер данных: без paging большая `ТаблицаЗначений` обрезается/взрывает контекст → `inspect_frame` бесполезен), поэтому **уже в W1**.

---

## §6. Верификация «реального чтения кода с реальным результатом» (доказательство работоспособности контура)

Живой health-check 2026-07-08 подтвердил готовность контура к реальной отладке:
- `dbgs.exe` слушает `localhost:1550`, `ragent -debug -http`, `rac.exe`+кластер `fb88a5c5…` — всё ✅
- 5 инфобаз доступно; сессия чистая
- ⚠ pre-existing rphost `[48144]` (17 conns) → для чистого BP нужен `force_recycle` или JOB-путь (Шаблон 6)

Следующий шаг для end-to-end демонстрации (по approve): `debug_connect` → `debug_autotrace` (после реализации A1) на реальном методе в `ИБTransportManagementDevelop` с чтением фактических значений переменных в рантайме.

---

## §7. Точная декомпозиция W1–W3 (по анализу кода, 2026-07-08)

> Якоря — `tools/bsl-debug-server/mcp_debug_server.py` (4083 стр). Анализ вскрыл **3 факта, меняющих дизайн**, и дал пошаговую разбивку.

### 7.0 Три факта из кода, меняющих дизайн

**Ф-1. A1-`trigger` — межсерверная граница (главный дизайн-вопрос W1).** `trigger` в Шаблонах 5/6 исполняется через `mcp__1c-mcp-crud__execute_code` — это **другой MCP-сервер**; `mcp_debug_server.py` не может вызвать его tool. Варианты:
- **(a) Прямой HTTP-POST из wrapper'а** к тому же HTTP-сервису `/hs/mcp/rpc`, который питает 1c-mcp-crud (httpx уже есть; креды из env `MCP_ONEC_*`, как у 1c-mcp-crud в `.mcp.json`). Полный one-call.
- **(b) Двухфазный режим** `debug_autotrace(phase="arm", ...)` → агент сам триггерит execute_code → `debug_autotrace(phase="collect")`. Без новых кредов/зависимостей, но 3 вызова вместо 1.
- **Решение W1:** реализовать **(b) сразу** (нулевой риск, уже 3 вызова vs 12) + **(a) как enhancement** в той же волне, если env-креды доступны (fallback на (b) при их отсутствии).

**Ф-2. RDBG отдаёт стек outermost-first — фрейм BP ПОСЛЕДНИЙ.** Подтверждено `coverage.py:31-35` (скан стека с конца: «RDBG отдаёт outermost-first»). Значит verdict-логика A1 сравнивает **`stack[-1].lineNo`** (innermost), НЕ `frames[0]`. ⚠ Шаблон 5 в SKILL (`assert frames[0].lineNo`) — проверить/поправить при реализации (возможный давний баг протокола верификации).

**Ф-3. 4× дублирование резолв-паттернов** — перед A0/A1 обязателен рефактор-шаг:
- `property_id`-резолв (`MODULE_PROPERTY_IDS` + `ConfigModule`-подмена) продублирован в `debug_set_breakpoint:3176-3180`, `debug_set_logpoint:3229-3233`, `debug_coverage_register`, `debug_calibrate_lines`;
- `stopped_target`-резолв (`last_stopped_target_id → _find_stopped_target`) продублирован в `debug_stack_trace:3018-3025`, `debug_variables:3074-3081`, `debug_evaluate:3122-3129`, `debug_step`;
- enrich-loop `resolved_source` инлайн в `debug_stack_trace:3028-3038`.

### 7.1 ✅ W1.0 — Рефактор-фундамент (~1.5ч, НОВЫЙ шаг)

| Шаг | Что | Якорь |
|---|---|---|
| W1.0.1 | Хелпер `_resolve_property_id(module_type, property_id) -> (xml_module_type, property_id)` — заменить 4 дубля | `:3176`, `:3229`, coverage, calibrate |
| W1.0.2 | Хелпер `_resolve_stopped_target(client, target_id) -> str \| None` (async) — заменить 4 дубля | `:3018`, `:3074`, `:3122`, step |
| W1.0.3 | Хелпер `_enrich_stack(stack) -> list` (resolved_source loop) — вынести из stack_trace | `:3028-3038` |
| W1.0.4 | Новый модуль `autonomy.py` (по традиции `bp_conditions`/`logpoints`/`system_stops`) + **добавить в `--watch` `.mcp.json`** (урок P0.D) | `.mcp.json` |
| Тест | Существующие 222 unit зелёные (рефактор behavior-preserving) | `tests/test_mcp_debug_server.py` |

### 7.2 ✅ A0 `debug_inspect_frame` (~2.5ч после W1.0)

| Шаг | Что | Якорь |
|---|---|---|
| A0.1 | Композиция в `autonomy.py::build_frame_bundle(client, target_id, stack_level, context_radius)`: стек из кэша `_last_stack_by_target` (как `eval_locals_auto:1276-1279`) + `_enrich_stack` | `:1276`, `:1151` |
| A0.2 | Локали: `client.eval_locals_auto(:1261)` — уже batch через `_pending_evals` futures (`:1204-1256`); при пустом результате (нет src) — деградация `{locals_mode:"unavailable"}` | `:1261-1310` |
| A0.3 | Исходник ±radius: `uuid_index.resolve_uuid(:1292)` → path → read lines `[line-r, line+r]` с маркером `→` на текущей | `uuid_index.py` |
| A0.4 | Разделение args/locals: v1 БЕЗ разделения (в `bsl_locals.extract_locals_at_line` категории не тегированы); тегирование — отдельный мини-шаг в C3 (AST) | `bsl_locals.py` |
| A0.5 | MCP-tool `debug_inspect_frame` (после `debug_variables:3105`) — тонкая обёртка над `autonomy.build_frame_bundle` + `_error_json`-envelope | `:3105` |
| Тест | `tests/test_autonomy.py`: mock client (паттерн 222 существующих), кейсы: полный бандл / нет src / нет stopped target; live-smoke на ИБTransport | — |

### 7.3 ✅ A1 `debug_autotrace` (~4ч)

| Шаг | Что | Якорь |
|---|---|---|
| A1.1 | Фаза `arm`: `_resolve_property_id` → `client.set_breakpoints(:1490)` (+offset из B2-кэша) → `debug_arm_next_rphost(:3382)`-механика → вернуть `{armed:true, bp:{...}}` | `:1490`, `:3382` |
| A1.2 | Ожидание fire: `asyncio.Event` per-session (`client._stop_event`), взводится в `_handle_command(callStackFormed)` (`:680-755`, ПОСЛЕ фильтров system_stops/coverage/logpoint — только user-visible stop); wait с timeout (default 20с) вместо ping×3 | `:680` |
| A1.3 | Фаза `collect`: wait event → `build_frame_bundle` (A0) → verdict по `expect` — **сравнение `stack[-1]` (Ф-2!)** → `debug_step("Continue")` в `finally` (release даже при FAIL — контракт Шаблона 5 шаг 8) | `:1397` |
| A1.4 | Verdict-движок: `checked[]` через `client.eval_expression(:1312)` по каждому `expect`-выражению; статусы PASS/FAIL/NO_HIT(timeout)/INCONCLUSIVE(eval-error) | `:1312` |
| A1.5 | (enhancement, если env-креды) transport (a): httpx POST BSL-фрагмента на `/hs/mcp/rpc` — обёртка `ФоновыеЗадания.Выполнить` как в Шаблоне 6; graceful fallback на two-phase | Ф-1 |
| Тест | unit: arm→fire(mock event)→verdict PASS/FAIL/NO_HIT + Continue-в-finally; live: реальный метод, реальный verdict | — |

### 7.4 ✅ C0 variables paging (~2.5ч)

RDBG не имеет «expand»-вызова — paging строится wrapper-side поверх batch-механики `eval_local_variables:1204-1256` (уникальный `expressionResultID` per item — уже готовый конвейер):

| Шаг | Что | Якорь |
|---|---|---|
| C0.1 | `debug_collection_info(expression)`: eval `ТипЗнч(X)` + `X.Количество()` → `{type, count}` | `:1312` |
| C0.2 | `debug_collection_page(expression, start, count, columns?)`: генерация batch-выражений `X[i]` / `X.Получить(i)` / `X[i].Колонка` (по типу из C0.1) → один `evalLocalVariables`-POST | `:1204-1256` |
| C0.3 | Интеграция в A0: если `resultValueInfo` коллекции содержит признак большого размера → в бандле `{paged:true, preview:первые 10, page_hint}` вместо обрезки | A0.2 |
| Тест | unit на генерацию выражений по типам (Массив/ТЗ/Соответствие/РезультатЗапроса-выгрузка); live на ТЗ 1000+ строк | — |

### 7.5 ✅ B2 auto-calibrate (~3ч)

| Шаг | Что | Якорь |
|---|---|---|
| B2.1 | Offset-кэш `client._line_offsets: dict[(object_id,property_id), int]` + персист в `.active.json` (`_persist_active_session:2603` / `_load_active_session:2630`) | `:2603` |
| B2.2 | Применение в `set_breakpoints`-обёртках (set_breakpoint/set_logpoint/coverage_register): `line += offset` при наличии ключа; в ответе `{applied_offset}` | `:3181` |
| B2.3 | Заполнение кэша из `debug_calibrate_result` (`offset` уже вычисляется: `nearest_fired - requested`) — просто записать в кэш | `:3593-3680` |
| B2.4 | Fallback-цепочка в A1 при NO_HIT: авто-`calibrate_lines`-веер → повтор trigger → повтор collect (1 итерация, потом честный NO_HIT) | A1.3 |
| Тест | unit: offset применён/персистирован/восстановлен после рестарта; live: BP по git-строке со сдвигом +3 fire'ит без ручной калибровки | — |

### 7.6 Якоря W2/W3 (кратко)

| ID | Якоря кода | Ключевой шаг |
|---|---|---|
| B1 | `capture_mode:3407` (sticky re-arm), `targetQuit:785-804`; BSL: новый `mcp_ОтладкаВыполненияКода` в расширении (ADR-049) | Worker: цикл ожидания сигнала (временное хранилище/РС) после исполнения; wrapper: `debug_step(Continue)` пишет сигнал освобождения через тот же HTTP-канал Ф-1(a) |
| ✅ B3 | `_ping_loop` (`PING_INTERVAL_IDLE=2.0/ACTIVE=0.1`), `_handle_command` (`_signal_bp_stop` в блоке метрик BP-стопа), `_await_bp_stop` (module-level), `debug_autotrace` collect | ✅ **done 2026-07-10:** `client._get_stop_event()` (lazy loop-bound Event) + `_await_bp_stop` заменил poll-loop; контракт A1 не тронут. Реализация оказалась «дособрать event-driven wait поверх adaptive ping» — самого `_stop_event` в A1 не было (A1 стартовал на 0.3s poll), B3 его и добавил |
| B5 | `uuid_index.py:66-69` (`DEFAULT_CONFIG_SRC` hardcoded), cache-invalidation `:95-107` (mtime корня) | Map `alias → config_src` (env `BSL_DEBUG_CONFIG_SRC_MAP` или per-alias в `.active.json`); infobase_alias уже известен клиенту |
| C1 | `eval_expression:1312` (`evalExpr`), enum `setValue:624` (`_handle_command → Skipping:834-838`) | Research-зонд ≤30мин: `evalExpr` с `X = 42` в scope фрейма → проверить side-effect повторным чтением; guard `{old,new}` |
| A2 | `rteProcessing:757-783` + `exception_bps.py`; стек-обход = A0-бандл per frame | До B1: top-N фреймов inline в `_handle_command` (как `logpoints.fire_logpoint` — внутри halt-окна) |

### 7.7 Уточнённые оценки W1 (после декомпозиции)

| Позиция | Было | Стало | Дельта |
|---|---|---|---|
| W1.0 рефактор-фундамент | — | 1.5ч | +1.5ч (снижает риск всех A-шагов) |
| A0 | 3ч | 2.5ч | −0.5ч (реюз хелперов W1.0) |
| A1 | 4ч | 4ч (two-phase) +1ч (transport (a), опц.) | Ф-1 учтён |
| C0 | 2ч | 2.5ч | +0.5ч (два tool'а вместо одного) |
| B2 | 3ч | 3ч | = |
| **W1 итого** | ~12ч | **~13.5–14.5ч** | честнее за счёт Ф-1/Ф-3 |

**Порядок исполнения W1:** W1.0 → A0 → B2 → A1 (A1 зависит от A0-бандла и B2-offset-кэша) → C0 (независим, можно параллельно с A1). Ф-2 (`stack[-1]`) — проверить Шаблон 5 SKILL при реализации A1 и поправить, если баг подтверждается live.
