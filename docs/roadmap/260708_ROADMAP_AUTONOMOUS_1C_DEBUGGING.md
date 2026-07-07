# Roadmap 260708 — Autonomous 1C Debugging: от DAP-parity к agent-driven root-cause

> **Дата:** 2026-07-08
> **Автор запроса:** пользователь — «глубокий анализ 1c-debug-hmr, лучшие практики отладки с GitHub, отладка с максимальной автономностью — реальное чтение кода с реальным получением результата, дорожная карта улучшений»
> **Связано:** [260511 Deep Analysis](260511_DEEP_ANALYSIS_DEBUG_HMR_BEST_PRACTICES.md) (реализовано P0.A–G/P1/P2.A/P3.B), [260511 Deficiencies](260511_ROADMAP_1C_DEBUG_HMR_DEFICIENCIES_FROM_GKSTCPLK_2468.md), [260603 Long-poll ping](260603_ROADMAP_DEBUG_LONGPOLL_PING.md), skill [`1c-debug-hmr`](../../.claude/skills/1c-debug-hmr/SKILL.md), cache [`bp_propagation_race_patterns.md`](../../.claude/skills/1c-debug-hmr/cache/bp_propagation_race_patterns.md)
> **Статус:** RESEARCH + ROADMAP (реализация — по approve этапов)

---

## §0. TL;DR

Отладчик `1c-debug-hmr` за roadmap'ы 260508→260511 достиг **DAP-feature-parity 14/19** (conditional/hit-count BP, logpoints, source-mapping, exception BP, coverage, snapshot-replay, warm-pool arming, HMR persistent session). Инструменты **живые и проверены сегодня** (health-check: `dbgs :1550` ✅, `ragent -debug -http` ✅, 5 инфобаз ✅).

**Пробел, который предыдущие карты НЕ закрывали:** всё это — *ручные примитивы*. Агент (Claude) до сих пор оркеструет отладку пошагово: connect → set_bp → trigger → ping×3 → stack → variables → step. Каждый шаг — отдельный tool-call с ручным разбором JSON. **Нет слоя автономности**: агент не формулирует гипотезу, не ставит BP автоматически «где сломается», не читает состояние и не верифицирует гипотезу в одном замкнутом цикле.

Эта карта добавляет **три класса улучшений**:
- **Эпик A — Autonomy Orchestration Layer** (главная новизна): meta-tools, которые сворачивают «гипотеза→точка→запуск→чтение→вердикт» в один автономный проход.
- **Эпик B — Root-fixes надёжности**: корневые фиксы хронических болей (эфемерное окно JOB 1-2с, сдвиг строк src↔deployed, long-poll ping).
- **Эпик C — Remaining DAP gaps**: function BP, data BP (watch), drop-frame alternative, обогащение replay.

---

## §1. Глубокий анализ текущего инструментария (27 tools)

### 1.1 Слои архитектуры

```
Claude (агент-оркестратор)
   │  27 MCP-tools (ручные примитивы)
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
| Управление сессией | connect (5 recycle-стратегий), disconnect, ping (+no_fire_diagnostics), targets, target_state, attach_targets, wait_for_target, launch_thin_client, health_check | ✅ production, live-verified |
| Breakpoints | set_breakpoint (condition + hit_condition), set_logpoint, get_breakpoints, break_on_next, **calibrate_lines/calibrate_result** | ✅ + калибровка (2026-07-07) |
| Warm-pool | arm_warm_rphosts, arm_next_rphost (silent) | ✅ закрывает RC2 через JOB |
| Inspection | stack_trace (+resolved_source per frame), variables (auto-discovery), evaluate (composite types) | ✅ live |
| Execution | step (Continue/Step/StepIn/StepOut) | ✅ |
| Coverage/Artifacts | coverage_register, coverage_export, session_summary(artifacts ZIP) | ✅ SonarQube-compatible |
| Exception BP | set/clear/list_exception_bp (message+module фильтры) | ✅ |
| Replay | session_record, replay_list, replay_seek | ⚠ post-mortem, НЕ true time-travel |
| HMR | persistent session через `.active.json` | ✅ переживает restart |

**DAP-coverage: 14/19 industry-standard features** (было 8/19 до 260511).

### 1.3 Хронические боли (корневые ограничения, НЕ закрытые)

| # | Боль | Симптом | Текущий workaround | Корень |
|---|---|---|---|---|
| **P-1** | Эфемерное окно останова JOB ≈ 1-2 с | `debug_variables`/`evaluate` успевают, `step` — нет; «Предмет отладки не зарегистрирован» | logpoint (inline eval) вместо интерактива; персистентный контекст (тонкий клиент) | Платформа принудительно возобновляет halt server-контекста фонового задания |
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

### ЭПИК A — Autonomy Orchestration Layer 🎯 (главная новизна)

Цель: свернуть «реальное чтение кода с реальным получением результата» в автономные meta-tools. Агент задаёт *намерение*, wrapper исполняет весь цикл и возвращает **готовый вердикт**, а не сырой JSON для ручного разбора.

| ID | Инструмент | Что делает | Усилие | Риск | Ценность |
|---|---|---|---|---|---|
| **A0** | `debug_inspect_frame(target_id?, stack_level=0, context_radius=3)` | **Топ-идея обоих агентов (ADI/InspectCoder frame-bundle).** Один вызов = богатый бандл: фрейм + `resolved_source` + все локали (auto-discovery через `bsl_locals`+batch-`evaluate`) + аргументы + исходник строки ±`context_radius`. Заменяет дорогую цепочку `stack_trace`→`variables`→N×`evaluate` одним ответом | ~3ч | low (композиция) | ★★★★★ №1 по ценности×применимости |
| **A1** | `debug_autotrace(object_id, line, module_type, trigger, expect?)` | Один вызов: set_bp(+calibrate) → arm_next_rphost → исполняет `trigger` → ping-loop до fire → `inspect_frame` (A0) → (опц.) сверка с `expect` → **Continue** (release). **Контракт возврата — `verdict` + `raw` (см. дизайн-ноту ниже).** Сворачивает Шаблоны 5/5a/6 в atomic-операцию | ~4ч | low | ★★★★★ убирает P-5 |
| **A2** | `debug_root_cause(trigger, exception_filter?)` | На unhandled exception авто-собирает: полный стек + локали **каждого** фрейма + `resolved_source` + значение виновника + JSONL-снимок → структурированный **diagnosis-record** (SWE-Doctor: fault location, runtime symptom, propagation path, observed values) | ~3ч | low | ★★★★★ инцидент-разбор |
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
| **B1** | Persistent JOB-контекст (P-1) | JOB-halt эфемерен: rphost фонового задания живёт **<100ms** (spawn→строка→quit до attach+BP) | Спавнить **долгоживущий** debug-worker `mcp_ОтладкаВыполненияКода.ВыполнитьКодСУдержанием` **в расширении `MCP_Сервер`** ([ADR-049](../../.claude/skills/architecture-research/adr/049-debug-worker-in-mcp-server-extension.md)) — после исполнения держит контекст через ожидание сигнала (флаг в РС/врем.хранилище), пока агент читает/шагает; освобождение по `debug_step(Continue)`. Убирает гонку на корне (CDP-модель paused-on-entry). Заодно оформить существующий `debug_capture_mode` (sticky re-arm) как дефолт-политику в начале записи сессии | ~5ч | medium (BSL в расширении + dump-live-first деплой) |
| **B2** | Sync deployed↔src строк (P-2) | git отстаёт от развёрнутого; `calibrate` — ручной per-module workaround | (a) auto-`calibrate` встроить в `set_breakpoint` по умолчанию (offset применяется молча); (b) preflight-детект «dump живой конфы новее git» → предупреждение; (c) кэш offset per-module в `.active.json`. **Синергия с C1 (function BP устойчив к сдвигу вообще)** | ~3ч | low |
| **B3** | Long-poll ping (P-3) | синхронный event-pull, латентность = ping-sleep (2с idle) | Завершить [260603](260603_ROADMAP_DEBUG_LONGPOLL_PING.md): фоновый long-poll с backoff вместо ping×3; `debug_autotrace` ждёт event через asyncio.Event, не sleep-loop | ~3ч | medium (event-loop) |
| **B4** | dbgs heartbeat + auto-reattach recovery | dbgs может умереть; **UI+ revocation root-cause неизвестен** (RDBG произвольно отзывает UI+ между операциями) | Health-probe в ping-loop: при потере :1550 или UI+ — авто-reconnect + `_reapply_bp_workspace` (метод есть) + replay `.active.json`, surface в статусе | ~2ч | low |
| **B5** | Переносимость + housekeeping (техдолг код-агента) | `uuid_index.py:66-69` **hardcoded** `C:\1С-Framework\ИБTransportManagementDevelop\…` → блокер на др. ИБ (SVETLY/MFM); UUID-cache invalidation по mtime **корня** src (coarse — вложенный `.mdo` не инвалидирует); ~30 `test_rdbg*` + `.log` в корне; неиспользуемые Java-артефакты (jar 12МБ + vsix 11МБ + `src/`) | (a) config-path через env/`.active.json` per-alias; (b) рекурсивный mtime/hash для cache-invalidation; (c) убрать test_rdbg* в `archive/` или удалить; (d) вынести Java-артефакты | ~3ч | low |

**Acceptance B:** B1 → интерактивный step по JOB-таргету работает (сейчас невозможно из-за <100ms окна). B2 → BP по git-строке fire'ит без ручной калибровки в 95% случаев. B3 → trap-latency с ~6с (3×2с) до <1с. B5 → отладчик работает на `SVETLY`/`MFM` без правки кода.

### ЭПИК C — Remaining DAP-gaps (после A/B)

| ID | Фича | Реализуемость в RDBG | Усилие | Приоритет |
|---|---|---|---|---|
| **C0** | **Variables paging (`indexedVariables`/`namedVariables`)** | **Оба агента: критично именно для 1С.** `ТаблицаЗначений`/`Массив`/`Соответствие`/`РезультатЗапроса` бывают огромными — сейчас агент получает обрезку ИЛИ взрывает контекст. Ленивый доступ `variables(ref, start, count)` | ~2ч | ★★★★★ (узкое место, DAP-канон) |
| **C1** | `setVariable`/`setExpression` через evaluate-присваивание | Разрешить `evaluate` **мутирующих** выражений (`Перем = Значение`) на паузе → runtime hypothesis-test без правки BSL (InspectCoder reversible experiment). `valueModified`/`setValue` в enum есть, но не задействованы. **Предпосылка для C3 drop-frame** | ~2ч | ★★★★ |
| **C2** | Function BP (по имени метода) | Резолв метод→строка через `uuid_index`+`bsl_locals` (парсим `Процедура/Функция`), обычный BP на первую исполняемую. **Устойчив к P-2 сдвигу строк** | ~3ч | ★★★★ (синергия с B2) |
| **C3** | `breakpointLocations` + AST-усиление calibrate | Вернуть валидные исполняемые строки модуля (закрывает класс «BP на не-исполняемой строке»); усилить `bsl_locals` regex → полноценный AST из BSL Language Server (границы процедур, локали) | ~4ч | ★★★ |
| **C4** | Data BP / watchpoint | RDBG нет native; эмуляция C1+A3: условный BP на присваиваниях + сравнение с прошлым значением (polling watch) | ~4ч | ★★★ |
| **C5** | Drop-frame / goto альтернатива | RDBG enum = Step/StepIn/StepOut/Continue (нет goto). Эмуляция через C1 `setExpression` + повторный trigger. **Research-blocked** (как 260511 P2.B) — сперва подтвердить feasibility записи переменной в RDBG XSD | ~5-8ч | ★★ (defer) |
| **C6** | Precise coverage (callCount) + семантический replay-seek | Block-level счётчики → genericCoverage `count=`; индекс по replay-логу (TTD-timeline-стиль) → `replay_seek("первый halt где Итог<0")` вместо числового индекса | ~4ч | ★★★ |

---

## §4. Последовательность и оценки

| Волна | Состав | Усилие | Результат |
|---|---|---|---|
| **W1** (автономность-ядро) | **A0** + A1 + C0 + B2 | ~12ч | Frame-bundle в 1 вызов; autotrace в 1 вызов; paging больших коллекций; BP fire'ит без ручной калибровки |
| **W2** (надёжность) | B1 + B3 + B5 | ~11ч | Интерактивный JOB-step; sub-second trap; переносимость на SVETLY/MFM |
| **W3** (диагностика) | A2 + A3 + C1 + B4 | ~11ч | Root-cause diagnosis-record; trace-variable; runtime hypothesis-test; auto-reattach |
| **W4** (глубина) | A4 + C2 + A6 | ~9ч | Differential debug; function BP; session-режимы + correlation_id |
| **W5** (nice-to-have) | A5 + C3 + C4 + C6 | ~13ч | Verify-батч; breakpointLocations; watchpoint; precise coverage + семантический replay |
| **Defer** | C5 (drop-frame) | — | до подтверждения feasibility `setExpression`/записи переменной в RDBG XSD |

**ROI:** W1 (~12ч) даёт наибольший leverage — `debug_inspect_frame`+`debug_autotrace`+paging убирают P-5 (ручная оркестрация, 6-10 tool-calls → 1) и P-2 (сдвиг строк). W1+W2+W3 (~34ч) закрывают ≥80% боли автономной отладки. По данным InspectCoder — высокоуровневые примитивы дают **1.67–2.24× эффективности** vs атомарный степпинг.

## §5. Открытые вопросы (для approve)

1. ~~**B1 требует BSL-модуль в БД** — деплоить во все ИБ или только dev?~~ **✅ РЕШЕНО ([ADR-049](../../.claude/skills/architecture-research/adr/049-debug-worker-in-mcp-server-extension.md)):** модуль `mcp_ОтладкаВыполненияКода` идёт в **расширение `MCP_Сервер`** (`external/1c_mcp/`, префикс `mcp_`, dump-live-first деплой) — не трогаем типовую конфигурацию, деплой существующим пайплайном расширения, доступен везде, где расширение установлено. Рекомендация: позже консолидировать туда же существующий `гкс_ОтладкаВыполненияКода` (Шаблон 6, сейчас в основной конфе) — единый дом debug-хелперов.
2. ~~**A1 verdict-семантика:** wrapper судит или агент?~~ **✅ РЕШЕНО (§3 дизайн-нота A1):** возвращать **оба** — `verdict` (машинное суждение по явному `expect`, может быть `null`) + `raw` (всегда, единственный источник истины). Wrapper не прячет состояние за вердиктом; при `INCONCLUSIVE`/`NO_HIT`/без-`expect` судит агент.
3. **C3 drop-frame:** тратить research-бюджет на `setExpression` feasibility в RDBG XSD, или окончательно defer до vendor?
4. **Приоритет автономности vs parity:** согласен ли пользователь, что Эпик A (автономность) важнее C (DAP-gaps)? Карта исходит из «да» по формулировке запроса.

---

## §6. Верификация «реального чтения кода с реальным результатом» (доказательство работоспособности контура)

Живой health-check 2026-07-08 подтвердил готовность контура к реальной отладке:
- `dbgs.exe` слушает `localhost:1550`, `ragent -debug -http`, `rac.exe`+кластер `fb88a5c5…` — всё ✅
- 5 инфобаз доступно; сессия чистая
- ⚠ pre-existing rphost `[48144]` (17 conns) → для чистого BP нужен `force_recycle` или JOB-путь (Шаблон 6)

Следующий шаг для end-to-end демонстрации (по approve): `debug_connect` → `debug_autotrace` (после реализации A1) на реальном методе в `ИБTransportManagementDevelop` с чтением фактических значений переменных в рантайме.
