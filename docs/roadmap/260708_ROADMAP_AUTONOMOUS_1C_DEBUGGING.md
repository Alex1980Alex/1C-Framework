# Roadmap 260708 — Autonomous 1C Debugging: от DAP-parity к agent-driven root-cause

> **Дата:** 2026-07-08
> **Автор запроса:** пользователь — «глубокий анализ 1c-debug-hmr, лучшие практики отладки с GitHub, отладка с максимальной автономностью — реальное чтение кода с реальным получением результата, дорожная карта улучшений»
> **Связано:** [260511 Deep Analysis](260511_DEEP_ANALYSIS_DEBUG_HMR_BEST_PRACTICES.md) (реализовано P0.A–G/P1/P2.A/P3.B), [260511 Deficiencies](260511_ROADMAP_1C_DEBUG_HMR_DEFICIENCIES_FROM_GKSTCPLK_2468.md), [260603 Long-poll ping](260603_ROADMAP_DEBUG_LONGPOLL_PING.md), skill [`1c-debug-hmr`](../../.claude/skills/1c-debug-hmr/SKILL.md), cache [`bp_propagation_race_patterns.md`](../../.claude/skills/1c-debug-hmr/cache/bp_propagation_race_patterns.md)
> **Статус:** RESEARCH + ROADMAP + **W1 ✅** (2026-07-08, A0/A1/C0/B2/W1.0, live-verified) + **W2 ✅** (2026-07-09/11: B3 event-wait, B5.a/b/c/d, **B1 ✅ 2026-07-11**) + **W3 A2/A3/B4 ✅** (2026-07-10). + **Аудит 260710 + волна W-fix ✅** (все code-side дефекты закрыты, двухпроходное ре-ревью PASS). **462 unit passed** (450 + 12 B1). **B1 ✅ РЕАЛИЗОВАН И ЗАДЕПЛОЕН (2026-07-11):** worker `mcp_ОтладкаВыполненияКода.ВыполнитьКодСУдержанием` в расширении MCP_Сервер (держит rphost живым до release-флага/таймаута через ХранилищеОбщихНастроек), Python-обвязка `held_job.py` + tools `debug_launch_held_job`/`debug_release_held_job` + release-on-Continue; деплой dump-live-first на базу MFM (LoadConfigFromFiles+UpdateDBCfg EXIT 0), verify: execute_code без регрессии + метод резолвится. Осталось (нужен live-зонд RDBG): **C1** (setExpression). Не начато (nice-to-have, не блокеры): W4 (A4/C2/A6), W5 (A5/C3/C4/C6), C7; defer C5.

> **⚙ W1 IMPLEMENTED + LIVE-VERIFIED (2026-07-08):** W1.0 рефактор-фундамент (3 хелпера, дедуп 4+4) + A0 `debug_inspect_frame` + A1 `debug_autotrace` (two-phase) + B2 auto-calibrate offset + C0 `debug_collection_info`/`_page`. 337 unit passed, code-verify PASS. Коммиты сабмодуля: 903f449/9496a2f/b2eb39a/51433c7/ce11644/1af1478/**89fbc5d**.
>
> **Живой E2E (5 прогонов, ИБTransportManagementDevelop):** BP `гкс_ВходнойКонтрольКачества:2333` + trigger `execute_code` → **hit=true, verdict PASS** (`Пакет1` expected=0 actual=0 ✓, `Пакет2` expected=4 actual=4 ✓), frame=2333, `resolved_source` FQN, `locals_mode=auto` (реальные значения рантайма: `ДокументРегистрации=Неопределено`, `Результат=Структура`). **Live-прогон нашёл и починил 3 бага (89fbc5d):** (1) race collect — транзиентный системный spawn-halt принимался за user-hit (фикс: reason="breakpoint"+debounce); (2) `_extract_eval_value` не знал реальную RDBG-форму (`resultValueInfo.valueDecimal` + base64 `pres`); (3) **Ф-2 разрешён**: callStack-массив outermost-first, eval-stackLevel innermost-first → инверсия индексации в bundle И в предсуществующем `eval_locals_auto` (auto-discovery на глубоких стеках парсил внешний фрейм). Плюс порядок: verdict-eval'ы ПЕРЕД bundle (окно halt server-контекста ~1-2с). **Находка окружения:** `гкс_ОтладкаВыполненияКода` ОТСУТСТВУЕТ в живой БД (пересоздана из .dt?) — Шаблон 6 (JOB-harness) сейчас сломан; закроется B1/ADR-049 (worker в расширении MCP_Сервер). Отложено: C0.3 авто-paging в A0, transport (a) HTTP one-call.

> **⚙ W3 A3 IMPLEMENTED (2026-07-10, сабмодуль `d7a173b`):** `debug_trace_variable` — InspectCoder trace-variable: авто-logpoint'ы на строки присваивания `name` (+ upstream RHS-входы) → прогон → таймлайн значений `[{line, value, ts}]`. Two-phase arm/collect; arm статически находит `name = ...` (статемент-старт — не ловит сравнения/member) в области `method`, ставит per-строка logpoint `name={name} u={u}`; collect читает logpoint-JSONL этого трейса, снимает свои logpoint'ы. Pure-хелперы в `autonomy` (find_method_range/find_assignment_lines/_extract_upstream/build_trace_template/read_trace_timeline). Рефактор `_reapply_bp_workspace`→`_push_bp_workspace` (behavior-preserving; пушит пустой workspace для очистки). +27 unit → 425 passed, code-verify PASS 7/7 + hardening (re-arm снимает предыдущий трейс). **W3 остаток: только C1** (setExpression — нужен live-зонд RDBG: принимает ли `evalExpr` side-effecting присваивание).
>
> **⚙ W3 B4 IMPLEMENTED (2026-07-10, сабмодуль `03e7b84`):** dbgs heartbeat + auto-reattach — `_ping_loop` детектит устойчивую потерю связи (3 подряд ping-исключения) → bounded auto-reconnect (`_heartbeat_record`→`_maybe_reconnect` cooldown 30с→`_attempt_reconnect`: detach→new sid→attach→handshake→`_reapply_bp_workspace`); `client._recovery` surfaced в `get_target_state`. **Loop-survival root-fix:** reconnect выполняется ВНУТРИ `_ping_task`, поэтому `detach` получил `cancel_ping=False` — иначе detach отменял бы свой же исполняющийся loop (CancelledError=BaseException, не ловится `except Exception` → heartbeat умирал навсегда). **Адверсариальный code-verify поймал этот дефект (FAIL→fix→PASS 6/6)** — первый тест давал ложный зелёный (мокал detach); регрессия `test_does_not_cancel_live_ping_task` доказанно ловит старый баг. +14 unit → 398 passed. Осталось в W3: A3 (trace-variable) + C1 (setExpression, live-зонд RDBG).
>
> **⚙ W3 A2 IMPLEMENTED (2026-07-10, сабмодуль `acb8ac3`):** `debug_root_cause` — автономный root-cause на unhandled exception → structured diagnosis-record (SWE-Doctor: fault_location/runtime_symptom/propagation_path/frames_inspected). Two-phase arm/collect (как A1), collect ждёт rteProcessing через обобщённый B3-waiter (`_await_bp_stop(reasons=("exception",))`; `_handle_command` сигналит event на не-подавленном исключении). `autonomy.build_diagnosis_record` переиспользует `build_frame_bundle` (A0) per-frame; **bounded top-`max_frames`** (halt-окно 1-2с) с честным `frames_bounded`/`frames_total`. Root-fix `exception_bps._extract_message += info` (фильтр не матчил живую форму). **+18 unit → 384 passed**, code-verify PASS 8/8. Осталось в W3: A3 (trace-variable) + C1 (setExpression, нужен live-зонд RDBG) + B4 (heartbeat auto-reattach).
>
> **⚙ W2 B3 IMPLEMENTED (2026-07-10):** event-driven long-poll wait — `debug_autotrace` collect больше не крутит фиксированный 0.3s poll-loop, а ждёт `asyncio.Event` (`RDBGClient._get_stop_event`, lazy loop-bound, HMR-safe), взводимый в `_handle_command` (`_signal_bp_stop`) ТОЛЬКО на user-visible BP-стоп (`stop_by_bp and not stop_suppressed`). Новый module-level `_await_bp_stop(client, timeout_sec)` сохраняет предикат старого цикла байт-в-байт (reason="breakpoint" + 0.15s debounce + re-check в `_stopped_targets`); Event = wakeup-hint, `_stopped_targets` — source of truth. Инвариант против lost-wakeup: между re-check предиката и `event.wait()` нет `await` (продюсер не вклинится), state обновляется ДО `set()`, `clear()` после пробуждения безопасен; ≤1.0s cap на `wait_for` = eventual-guarantee даже при пропущенном сигнале. Trap-latency: с poll-гранулярности до event-dispatch (~0.1s active ping-каденс). Контракт `debug_autotrace` (`{verdict, raw}`, `raw.hit`/`waited_sec`, Continue в finally) не изменён. **+14 unit (`tests/test_longpoll_b3.py`: Event lifecycle / предикат+debounce / event-driven wakeup <0.5s / safety-net без сигнала / `_handle_command` signals / collect hit+NO_HIT) → 366 passed**, code-verify PASS (behavior-preservation + async race-safety, 7/7). `_AutotraceClient` mock расширен зеркалом event-surface. Осталось в W2: **B1** (persistent JOB-контекст, ADR-049, env-heavy — BSL-worker в расширении MCP_Сервер) + **B5.c/d** (file-cleanup).
>
> **⚙ W2 B5 IMPLEMENTED (2026-07-09, сабмодуль `91e89a8`):** **B5.a portability** - `BSL_DEBUG_CONFIG_SRC_MAP="Alias=path;..."` (alias -> config_src, `=`-сепаратор из-за `:` в Windows-путях) + per-alias `UUIDIndex`-реестр (свой cache-файл на каждый config_src через `_cache_path_for` sha1); `set_active_config` вызывается в `RDBGClient.__init__` (одно live-соединение за раз -> module-global точен); `resolve_uuid`/`get_source_info` получили опц. `alias` (fallback на `_active_alias`). Разблокирует отладку SVETLY/MFM без правки кода. **No-op при незаданном env** - byte-identical маршрут на default singleton (code-verify behavior-preservation PASS; покрыты `_enrich_stack`/`autonomy.read_source_context`/`inspect_frame` - все module-level вызовы полагаются на active alias, выставленный при connect). **B5.b recursive cache-invalidation** - `_src_fingerprint` `{max_mtime,count,total_size}` над `*.mdo` (stat-only, без чтения) вместо coarse top-level dir-mtime, который НЕ ловил вложенные `.mdo`-правки (класс stale-cache); старые `src_mtime`-кэши инвалидируются и ребилдятся. **352 unit passed (+12: парсинг map вкл. Windows-пути, alias-роутинг, active-config, fingerprint-инвалидация на nested edit/add/remove)**, code-verify PASS. **B5.c ✅ (2026-07-10, сабмодуль `d5b16f6`):** 32 gitignored dev-scratch перенесены в `archive/`. **B5.d ✅ b1+ (2026-07-10, сабмодуль `c8abae8`):** анализ вскрыл мёртвый gradle-CI (0 запусков за жизнь форка) + **P0 публичные креды** в tracked `start-1c-debug.bat` (PUBLIC форк) → bat удалён из HEAD, Python CI `ci.yml` (compile-smoke + pytest 366) вместо gradle, jar 12МБ untracked, `src/` yukon39 сохранён как reference (153 цитаты); история не переписывается (rotation-only прецедент) → **ротация `Alex80Alex` за пользователем PENDING** (см. §3 B5 (d) + memory [[project-secret-leak-remediation-260614]]). **B5 закрыт целиком.** **Далее W2:** B1 (persistent JOB-контекст, ADR-049, env-heavy - BSL-worker в расширении MCP_Сервер) + B3 (long-poll ping, event-loop).

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
- ✅ **`valueModified`/`setValue`** — **задействовано (C1, 2026-07-11)** через нативную команду `modifyValue` (`RDBGModifyValueRequest`), НЕ через enum-событие: tool `debug_set_variable` пишет значение переменной фрейма (runtime hypothesis-test). Осталось для C5 drop-frame — композиция B1+C1+StepOut, не новый примитив.
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

**Легенда статуса (обновлено 2026-07-11):** ✅ реализовано · 🟡 частично · ⬜ не начато · ⏸ отложено (live-ИБ / vendor). Сделано: **W1** (A0/A1/C0/B2), **W2** (B1 ✅ + B3/B5.a-d), **W3** (A2/A3/B4 + **C1 ✅**). **W2 и W3 полностью закрыты** — B1 + C1 live-validated 2026-07-11 на MFM (B1: BP-trace-с-удержанием; C1: `debug_set_variable` через нативный `modifyValue`). Осталось только W4′/W5′ (nice-to-have; **полная декомпозиция до шагов 0.5-1ч - §8**, волны пересобраны по зависимостям) + C5 (defer до vendor). Детали — в статус-блоках вверху карты.

### ЭПИК A — Autonomy Orchestration Layer 🎯 (главная новизна)

Цель: свернуть «реальное чтение кода с реальным получением результата» в автономные meta-tools. Агент задаёт *намерение*, wrapper исполняет весь цикл и возвращает **готовый вердикт**, а не сырой JSON для ручного разбора.

| ID | Инструмент | Что делает | Усилие | Риск | Ценность |
|---|---|---|---|---|---|
| ✅ **A0** | `debug_inspect_frame(target_id?, stack_level=0, context_radius=3)` | **Топ-идея обоих агентов (ADI/InspectCoder frame-bundle).** Один вызов = богатый бандл: фрейм + `resolved_source` + все локали (auto-discovery через `bsl_locals`+batch-`evaluate`) + аргументы + исходник строки ±`context_radius`. Заменяет дорогую цепочку `stack_trace`→`variables`→N×`evaluate` одним ответом | ~3ч | low (композиция) | ★★★★★ №1 по ценности×применимости |
| ✅ **A1** | `debug_autotrace(object_id, line, module_type, trigger, expect?)` | Один вызов: set_bp(+calibrate) → arm_next_rphost → исполняет `trigger` → ping-loop до fire → `inspect_frame` (A0) → (опц.) сверка с `expect` → **Continue** (release). **Контракт возврата — `verdict` + `raw` (см. дизайн-ноту ниже).** Сворачивает Шаблоны 5/5a/6 в atomic-операцию | ~4ч | low | ★★★★★ убирает P-5 |
| ✅ **A2** | `debug_root_cause(exception_message?, exception_module?, phase, max_frames)` | ✅ **РЕАЛИЗОВАНО 2026-07-10 (сабмодуль `acb8ac3`):** two-phase (arm=опц.фильтр+silent break-on-next / collect=ждёт rteProcessing event-driven → diagnosis-record → Continue в finally). `autonomy.build_diagnosis_record`: fault_location (innermost), runtime_symptom `{code,message}`, propagation_path (весь стек outermost-first + resolved_source), frames_inspected (top-`max_frames` с локалями). **Bounded top-N** (deep-eval дорог + halt-окно 1-2с), усечение видно в `frames_bounded`/`frames_total` (no silent cap); полный обход — после B1. `_await_bp_stop` обобщён `reasons` (B3 back-compat). **Root-fix:** `exception_bps._extract_message` += `info` (message_pattern-фильтр не матчил живую форму `{code,info}` — подавлял то, что ловил). +18 unit (384 passed), code-verify PASS 8/8 | ~3ч | low | ★★★★★ инцидент-разбор |
| ✅ **A3** | `debug_trace_variable(name, object_id, method?, phase, max_lines, upstream)` | ✅ **РЕАЛИЗОВАНО 2026-07-10 (сабмодуль `d7a173b`):** two-phase (arm читает исходник → находит строки `name = ...` [статемент-старт: не ловит `Если name =` / member `Стр.name =`] в области `method` → per-строка logpoint `name={name} u={u}` [значение + upstream RHS-входы] + silent break-on-next; collect читает logpoint-JSONL этого трейса → таймлайн `[{line, value, ts}]`, снимает свои logpoint'ы). Pure-хелперы `autonomy.find_method_range/find_assignment_lines/_extract_upstream/build_trace_template/read_trace_timeline`. Рефактор `_reapply_bp_workspace`→`_push_bp_workspace` (очистка через пустой workspace). +27 unit (425 passed), code-verify PASS 7/7 | ~4ч | low | ★★★★ «откуда взялось это значение» |
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
| ✅ **B4** | dbgs heartbeat + auto-reattach recovery | dbgs может умереть; **UI+ revocation root-cause неизвестен** (RDBG произвольно отзывает UI+ между операциями) | ✅ **РЕАЛИЗОВАНО 2026-07-10 (сабмодуль `03e7b84`):** `_ping_loop` считает консекутивные ping-фейлы (`_heartbeat_record`); `HEARTBEAT_FAIL_THRESHOLD=3` → degraded → `_maybe_reconnect` (троттл `RECONNECT_COOLDOWN_SEC=30с`) → `_attempt_reconnect` (detach→new sid→attach→handshake→`_reapply_bp_workspace`); состояние в `client._recovery`, surfaced через `get_target_state`. **Инвариант живучести:** reconnect идёт из ВНУТРИ `_ping_task` → `detach` получил `cancel_ping=False` (иначе detach отменял свой же loop — CancelledError убивал heartbeat навсегда; поймано адверсариальным code-verify, FAIL→fix→PASS). ping()=[] на нет-событий (не исключение) → триггер только на реальном transport-фейле. +14 unit (398 passed), re-verify PASS 6/6 | ~2ч | low |
| ✅ **B5** | Переносимость + housekeeping (техдолг код-агента) — **ВСЕ подпункты a/b/c/d готовы** | `uuid_index.py:66-69` **hardcoded** `C:\1С-Framework\ИБTransportManagementDevelop\…` → блокер на др. ИБ (SVETLY/MFM); UUID-cache invalidation по mtime **корня** src (coarse — вложенный `.mdo` не инвалидирует); ~30 `test_rdbg*` + `.log` в корне; неиспользуемые Java-артефакты (jar 12МБ + vsix 11МБ + `src/`) | **(a) ✅** config-path через env `BSL_DEBUG_CONFIG_SRC_MAP` per-alias + per-alias `UUIDIndex`-реестр (сабмодуль `91e89a8`); **(b) ✅** рекурсивный fingerprint `{max_mtime,count,total_size}` для cache-invalidation; **(c) ✅** 32 gitignored dev-scratch (`test_rdbg*`/`test_full*`/`test_quick*`) перенесены в `archive/` (в `.gitignore`), product-код не тронут (сабмодуль `d5b16f6`); **(d) ✅ ИСПОЛНЕН b1+ (2026-07-10, сабмодуль `c8abae8`, выбор пользователя: b1+ / rotation-only)** — анализ вскрыл: gradle-CI `build.yml` = **0 запусков за всю жизнь** (мёртв) и **🔴 P0**: форк `Alex1980Alex/bsl-debug-server` PUBLIC, tracked `start-1c-debug.bat` с живыми кредами (`a.terletskiy@sodru.com`/`Alex80Alex`) в публичном origin/master при 0 ссылок на файл (memory [[project-secret-leak-remediation-260614]]). Сделано: P0 `git rm` bat из HEAD; **Python CI `ci.yml`** (3.12: compile-smoke всех модулей + pytest 366) вместо gradle; jar 12МБ untracked (+gitignore `bsl-debug-server-*.jar`, gradle/wrapper остался); `src/main/java` (yukon39, 153 цитаты) сохранён как офлайн-reference. История форка НЕ переписывается (прецедент rotation-only 2026-06-14) → **ротация пароля `Alex80Alex` — за пользователем, PENDING**; локальный master ahead 12, push сабмодуля = отдельное решение (публикация W1/W2 wrapper-кода). Локальный dry-run CI-шагов зелёный | ~3ч | low (c) / **medium (d) — CI+identity+P0 creds** |

**Acceptance B:** B1 ✅ → интерактивный step/inspect по JOB-таргету работает (**live-validated 2026-07-11**: удержание держит эфемерный rphost 20с вместо <100мс, полный BP-trace стека+локалей на живом dbgs). B2 → BP по git-строке fire'ит без ручной калибровки в 95% случаев. B3 → trap-latency с ~6с (3×2с) до <1с. B5 → отладчик работает на `SVETLY`/`MFM` без правки кода.

### ЭПИК C — Remaining DAP-gaps (после A/B)

| ID | Фича | Реализуемость в RDBG | Усилие | Приоритет |
|---|---|---|---|---|
| ✅ **C0** | **Variables paging (`indexedVariables`/`namedVariables`)** | **Оба агента: критично именно для 1С.** `ТаблицаЗначений`/`Массив`/`Соответствие`/`РезультатЗапроса` бывают огромными — сейчас агент получает обрезку ИЛИ взрывает контекст. Ленивый доступ `variables(ref, start, count)` | ~2ч | ★★★★★ (узкое место, DAP-канон) |
| ✅ **C1** | `setVariable`/`setExpression` — **нативный RDBG `modifyValue`** (НЕ evaluate-присваивание) | ✅ **done + live-validated 2026-07-11.** ⚠ Гипотеза «evaluate-присваивание» **опровергнута зондом**: в BSL `=` в выражении — сравнение (`evalExpr("X=9")`→Булево), `Выполнить("X=9")`→«Ожидается выражение». Настоящий сеттер — команда `modifyValue` (`RDBGModifyValueRequest`: modifyDataPath[=тот же CalculationSourceDataStorage, что evalExpr] + newValueInfo[variant="expr"+valueExpression] + `timeout` в **мс**). Tool `debug_set_variable(name, value_expression, target_id?, stack_level=0, verify=True)` — `value_expression` = произвольный BSL (число/строка/дата/выражение, читает переменные фрейма); guard `{old,new,changed}` (verify); security-нота как у logpoints. Live: ТаймаутСек 120→777, строка := `"key-"+Строка(ТаймаутСек)`→«key-777», негатив `1/0`→errorDescr. 14 unit + code-verify PASS. **Разблокирует C5 drop-frame (80%) = B1+C1+StepOut.** | ~2ч | ★★★★ |
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
| ✅ **W2** (надёжность) | **B1 ✅** + **B3 ✅** + **B5 ✅** (a/b/c/d; d = b1+: Python CI, P0 креды, jar untracked) | ~11ч | **Интерактивный JOB-step ✅** (B1 live-validated 2026-07-11: JOB жив 20с vs <100мс, стек+4 локали, release за <1с); **sub-second trap ✅** (B3); **переносимость на SVETLY/MFM ✅** (B5.a/b); **root declutter + живой CI ✅** (B5.c/d) |
| ✅ **W3** (диагностика) | **A2 ✅** + **A3 ✅** + **C1 ✅** + **B4 ✅** | ~11ч | **Root-cause diagnosis-record ✅** (A2); **trace-variable ✅** (A3); **runtime hypothesis-test ✅** (C1 live-validated 2026-07-11 — `debug_set_variable` через нативный `modifyValue`); **auto-reattach ✅** (B4) |
| **W4′** (строки и гипотезы) | C3 + C2 + A5 | ~10.5ч | **Пересобрано по зависимостям 2026-07-11 - полная декомпозиция до шагов 0.5-1ч в §8.** Классификатор исполняемых строк -> function BP -> verify-батч гипотез. Инвентаризация §8.0: sticky capture-mode, coverage hit-счётчики, logpoint-конвейер, A3-хелперы УЖЕ в коде |
| **W5′** (наблюдение состояния) | C4 + C6 + A6 + A4 | ~14ч | Watchpoint (A3-сканер+C1 готовы) -> counts-экспорт+semantic seek -> correlation -> differential (A4 последним: собирает C6.2+A6.3). Декомпозиция §8.4-8.7 |
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
| ✅ B1 | `held_job.py` (builders + Ф-1(a) HTTP-transport), `mcp_debug_server.py` (`debug_launch_held_job`/`debug_release_held_job` + release-on-Continue); BSL: `mcp_ОтладкаВыполненияКода.ВыполнитьКодСУдержанием` в расширении `MCP_Сервер` (ADR-049) | ✅ **done + live-validated 2026-07-11:** worker исполняет код (BP fire'ит) → busy-poll держит rphost до release-флага (`ХранилищеОбщихНастроек "mcp_debug_hold_release"`) или таймаута; сигнатура 3-параметровая (`ФоновыеЗадания.Выполнить` распаковывает массив). **Live BP-trace-с-удержанием на MFM** (`260507_DEV_ATERLETSKIY_53196`): JOB жив 20с (vs эфемерные <100мс), `break_on_next` ловит busy-poll, `stack_trace`→worker в hold-цикле (стр. 66/97), `variables` читает 4 локали точно, release за <1с (за 5 мин до таймаута), `СтатусФЗ="Задание выполнено"` + флаги вычищены. 20 unit + артефакт `debug_artifacts/<session>.zip`. **Гоча:** BP-halt морозит цикл, не настенные часы → release ставить при busy-poll (не на halt) |
| ✅ B3 | `_ping_loop` (`PING_INTERVAL_IDLE=2.0/ACTIVE=0.1`), `_handle_command` (`_signal_bp_stop` в блоке метрик BP-стопа), `_await_bp_stop` (module-level), `debug_autotrace` collect | ✅ **done 2026-07-10:** `client._get_stop_event()` (lazy loop-bound Event) + `_await_bp_stop` заменил poll-loop; контракт A1 не тронут. Реализация оказалась «дособрать event-driven wait поверх adaptive ping» — самого `_stop_event` в A1 не было (A1 стартовал на 0.3s poll), B3 его и добавил |
| ✅ B5 | `uuid_index.py` (`BSL_DEBUG_CONFIG_SRC_MAP` per-alias реестр), `_src_fingerprint` (recursive `.mdo`), `.github/workflows/ci.yml` (Python), `.gitignore` (archive/, jar) | ✅ **done 2026-07-09/10 (`91e89a8`/`d5b16f6`/`c8abae8`):** a) env alias→config_src map + per-alias UUIDIndex; b) recursive fingerprint; c) scratch→archive/; d) b1+ (Python CI, P0-креды, jar untracked). Ротация пароля Alex80Alex — за пользователем |
| ✅ C1 | `RDBGClient.modify_value` (POST `modifyValue`), `_extract_modify_result`, tool `debug_set_variable`; ref `src/main/java/.../RDBGModifyValueRequest.java` + XSD `debugCalculations.xsd:92` (NewValueInfo) | ✅ **done 2026-07-11:** зонд опроверг evalExpr-присваивание (`=`→сравнение, `Выполнить`→void) → нативный `modifyValue` (modifyDataPath=CalculationSourceDataStorage как evalExpr + newValueInfo[variant=expr+valueExpression], `timeout`=**мс**). guard `{old,new,changed}` через eval до/после. Обе response-shape (success=newValueState/correctly, fail=processed+errorDescr) в `_extract_modify_result`. 14 unit + live (120→777, строка-expr, негатив 1/0) + code-verify PASS |
| ✅ A2 | `rteProcessing` + `exception_bps.py`; `autonomy.build_diagnosis_record` = A0-бандл per frame; `_await_bp_stop(reasons=("exception",))` | ✅ **done 2026-07-10:** two-phase tool; bounded top-`max_frames` (без inline-в-halt — collect делает Continue в finally, локали успевают до force-resume как у autotrace); полный обход всех фреймов — после B1 |
| ✅ B4 | `_ping_loop` (`_heartbeat_record`/`_maybe_reconnect`/`_attempt_reconnect`), `detach(cancel_ping)`, `get_target_state.recovery` | ✅ **done 2026-07-10 (`03e7b84`):** 3 ping-исключения → bounded auto-reconnect (cooldown 30с). Loop-survival: `detach(cancel_ping=False)` из-внутри `_ping_task` (иначе self-cancel → CancelledError убивал loop); поймано code-verify FAIL→fix→PASS |
| ✅ A3 | `autonomy.find_assignment_lines/find_method_range/read_trace_timeline`, `_clear_logpoint_keys`, `_push_bp_workspace` (извлечён), `debug_trace_variable` | ✅ **done 2026-07-10 (`d7a173b`):** two-phase; arm статически находит `name = ...` (статемент-старт) → per-строка logpoint → collect читает JSONL-таймлайн этого трейса + снимает logpoint'ы. Pure-хелперы отдельно от tool |

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

## §8. Точная декомпозиция W4/W5 (по анализу кода, 2026-07-11)

> W1/W2/W3 закрыты (B1+C1 live-validated 2026-07-11). Ниже - полная декомпозиция оставшихся nice-to-have пунктов до шагов 0.5-1ч: инвентаризация уже готового, якоря кода, live-план на held-JOB harness (B1), acceptance. Волны пересобраны по графу зависимостей (§8.8), не по исходной разбивке W4/W5.

### 8.0 Инвентаризация: что УЖЕ в коде (повторно не строить)

| Готовый примитив | Якорь | Фундамент для |
|---|---|---|
| Sticky capture-mode (re-arm после каждого дрейна - каждый новый JOB BP-receptive детерминированно) | `debug_capture_mode:5129`, `client._capture_mode` | A5, C4, A4 (пункт B1 «заодно оформить capture_mode» фактически закрыт отдельным tool'ом ещё 2026-06-03) |
| Coverage silent-BP + **hit-счётчики уже трекаются** | `_hit_counters:314` (dict `(oid,pid,line)->count`), инкремент `:2008`, `debug_coverage_register:5174` | A5, C6 (осталось ЭКСПОРТИРОВАТЬ счётчики - сбор готов) |
| Session summary + **metric-diff** (`regression_indicators`) | `debug_session_summary:3561`, `debug_session_diff:3523`, `_diff_summaries` | A4 (каркас диффа сводок есть; НЕТ variable-level state-diff) |
| Replay-снапшоты стопов (JSONL `{ts, target, reason, stack, exception?}` - **переменных НЕТ**) | `snapshot.py` (P2.A), `debug_session_record`, `data/debug_replays/<session>.jsonl` | A4, C6.2/C6.3 |
| Autotrace-скелет: two-phase arm/collect + verdict-контракт `{verdict, raw}` + capture-бандл | `debug_autotrace`, `autonomy.build_frame_bundle`, `_await_bp_stop` | A5, A4 |
| Logpoint-конвейер: eval `{expr}` на fire + JSONL + auto-Continue (без halt) + подавление стопа | `logpoints.py` (P0.B), suppress-gate в `_handle_command`, `_user_visible_stops` (M-1) | A5 (механика оценки expr), C4 (точка врезки компаратора) |
| A3-хелперы: метод по ИМЕНИ + строки присваиваний + upstream RHS | `autonomy.find_method_range`, `find_assignment_lines:569`, `_extract_upstream:537` | C2 (половина резолва готова), C4 (скан присваиваний готов) |
| Парс BSL-исходника: span по строке, локали, LHS-регекс | `bsl_locals._function_span_at:108`, `extract_locals_at_line:146`, `:61` | C3 (стартовая regex-инфраструктура) |
| B2 offset-кэш repo↔deployed (авто-применение в BP-обёртках) | `client._line_offsets` + persist `.active.json` (`:2603/:2630`), применение `:3181` | C2, C3 |
| Калибровка веером (реально исполняемые строки постфактум) | `debug_calibrate_lines:5253`, `debug_calibrate_result:3593-3680` | C2 fallback, C3.6 live-выверка классификатора |
| uuid→fqn резолв (per-alias) | `uuid_index.get_source_info:360`, `get_index_for_alias:334` | C2 (**обратного fqn→uuid НЕТ** - это C2.1) |
| B1 held-JOB + C1 set_variable | `held_job.py`, `debug_set_variable` | live-harness ВСЕХ пунктов; C4-инъекция изменений |

### 8.1 ✅ C3 - breakpointLocations + классификатор исполняемых строк (~4ч ядро, +1.5ч AST-стретч)

> ✅ **DONE 2026-07-11 (сабмодуль `f373c57`):** C3.1 `bsl_locals.classify_line/classify_lines/nearest_executable` (9 классов, header/structural=uncertain) + C3.2 tool `debug_breakpoint_locations` + C3.3 врезка `debug_set_breakpoint` (поле `location` + `_classify_bp_line` helper, SRC-координата до B2-offset, utf-8-sig BOM-fix) + C3.5 22 unit + C3.6 live-verify (совпал с B1-эмпирикой: стр.66 executable/fired, 68/69/75 structural). **Отложено:** C3.4 (фильтр веера calibrate по executable - минорная оптимизация), C3.7 (AST-апгрейд через tree-sitter-bsl - стретч). code-verify PASS (нашёл+пофикшен BOM-баг чтения).

Первым: его классификатор поднимает качество C2 (first-executable), A5/C4 (не ставить точки на мусор) и calibrate.

| Шаг | Что | Оценка |
|---|---|---|
| C3.1 | `bsl_locals.classify_lines(source_lines, from, to) -> {line: class}`: `comment` (`//`) / `blank` / `declaration` (`Перем`) / `directive` (`&НаСервере`...) / `preprocessor` (`#Если/#Область`) / `structural` (`КонецЕсли\|КонецЦикла\|КонецПопытки\|Иначе\|КонецПроцедуры\|КонецФункции\|Попытка`) / `string_continuation` (строка начинается `\|` - многострочный литерал) / `header` (`Процедура\|Функция`) / `executable`. Классы `structural`/`header` пометить `uncertain=True` до live-выверки C3.6 | 1ч |
| C3.2 | Tool `debug_breakpoint_locations(object_id, from_line, to_line, module_type, property_id)` - резолв исходника через `uuid_index` + классификатор + нота о B2-offset | 0.5ч |
| C3.3 | Врезка в `debug_set_breakpoint`: целевая строка не-executable -> **warning + `nearest_executable`** в ответе (НЕ блокировать - эвристика может ошибаться) | 0.5ч |
| C3.4 | Врезка в `debug_calibrate_lines`: веер только по executable-строкам (меньше BP-мусора, эффективно шире radius при том же лимите) | 0.5ч |
| C3.5 | Unit ×10: все классы, однострочный `Если X Тогда Y; КонецЕсли;`, `\|`-литералы, кириллица/`гкс_`, границы диапазона | 1ч |
| C3.6 | Live-выверка: coverage-веер на весь `mcp_ОтладкаВыполненияКода` (стр. 39-75) -> сверить фактические fired vs классы (факты B1 уже есть: 66/97 fired). По результату снять `uncertain` | 0.5ч |
| C3.7 | Стретч (опц., отдельно): AST-апгрейд через tree-sitter-bsl (`ast-grep-mcp` уже парсит BSL) - точные границы стейтментов; эвристика остаётся fallback | +1.5ч |

Риск: эвристика ≠ парсер - потому advisory-warning, не блок. Acceptance: BP на `КонецЕсли` даёт warning+nearest; calibrate не тратит BP на комменты.

### 8.2 C2 - Function BP по имени метода (~3ч)

| Шаг | Что | Оценка |
|---|---|---|
| C2.1 | Обратный резолв `uuid_index.find_by_fqn("ОбщийМодуль.X" / "Документ.Y.МодульОбъекта") -> (object_id, property_id, file_path)`: fqn-строитель уже есть внутри `get_source_info:247-273` - вынести, построить reverse-dict при загрузке индекса; нормализация ru/en типов | 0.5ч |
| C2.2 | `first_executable_line(source_lines, start, end)`: `find_method_range` (A3, по ИМЕНИ) даёт span -> первая executable по C3.1-классификатору (без C3 - мини-скип комментов/`Перем`, деградация) | 0.5ч |
| C2.3 | Tool `debug_set_function_breakpoint(method_fqn, condition="", hit_condition="", auto_calibrate=False)`: парс `<Объект>.<Метод>` -> C2.1 -> Read src -> C2.2 -> `set_breakpoint` (B2-offset применится сам `:3181`). Ответ `{resolved: {object_id, line, module}, bp}` | 0.5ч |
| C2.4 | `auto_calibrate=True` fallback: BP молчит после триггера -> веер calibrate по executable-строкам метода -> повтор (1 итерация, потом честный NO_HIT; реюз цепочки B2.4/A1.3) | 0.5ч |
| C2.5 | Unit ×6: fqn ru/en, метод не найден (error envelope), дубль имени в модуле (первый + warning), директива/`Экспорт`, многострочные параметры, offset-интеграция | 0.5ч |
| C2.6 | Live MFM: `debug_set_function_breakpoint("ОбщийМодуль.mcp_ОтладкаВыполненияКода.ВыполнитьКодСУдержанием")` -> held-JOB -> fired на first-executable БЕЗ указания строки | 0.5ч |

Acceptance: BP по имени метода fire'ит на живой базе без номера строки и без ручной калибровки (устойчив к P-2 сдвигу: имя не сдвигается).

### 8.3 A5 - `debug_hypothesis(assertions[])` verify-батч (~3.5ч)

Механика - **logpoint-based** (обобщение A3, НЕ новый примитив): assertion = logpoint с eval нужного `expr` на fire (без halt), collect читает JSONL и судит. Контракт `{verdict, raw}` (§3 дизайн-нота: A5 в списке).

| Шаг | Что | Оценка |
|---|---|---|
| A5.1 | Схема `assertions: [{object_id, line, module_type?, property_id?, expr, expected?, label?}]` + валидация (cap 50, label дефолт `#i@line`); нормализация `expected`-литералов (число/строка/Истина/Ложь/Неопределено) - реюз verdict-нормализации A1 | 0.5ч |
| A5.2 | arm: per assertion - logpoint с template `A5:<run_id>:<i>={expr}` (B2-offset в `set_logpoint`-обёртке сам) + `debug_capture_mode(on=True)` для эфемерных JOB; state `client._hypothesis_runs[run_id]` | 1ч |
| A5.3 | collect: ждать quiet-период по росту JSONL (logpoints не дают user-visible halt - `_await_bp_stop` не нужен), прочитать записи run'а (реюз паттерна `read_trace_timeline` A3), сгруппировать по `#i`: `fired/hits/actual` -> verdict per assertion `PASS/FAIL/NO_HIT/INCONCLUSIVE` | 1ч |
| A5.4 | Tool `debug_hypothesis(assertions, phase="arm"\|"collect", timeout_sec=30)` two-phase; снятие своих logpoint'ов в finally collect (реюз `_clear_logpoint_keys` A3). Ответ: `{verdict: {passed, failed, no_hit, per_assertion[]}, raw}` | 0.5ч |
| A5.5 | Unit ×7 (схема/cap, группировка, вердикты вкл. INCONCLUSIVE на eval-error, идемпотентный повторный collect, снятие logpoint'ов) + live MFM: 8-10 assertions по строкам worker'а за ОДИН прогон held-JOB (часть PASS, часть FAIL с actual, часть NO_HIT на недостижимых) | 0.5ч |

Acceptance: 10 гипотез «эти строки исполнятся с такими значениями» за 1 прогон -> полная таблица PASS/FAIL/actual. Интеграция: `analyze-1c-task --trace` Phase 2.5 (§3).

### 8.4 C4 - Watchpoint / data BP (эмуляция C1+A3) (~4ч)

| Шаг | Что | Оценка |
|---|---|---|
| C4.1 | План точек: реюз `find_assignment_lines:569` (A3) - строки `Имя = ...` в области метода; обёртка `plan_watchpoints(source, name, method?)` | 0.5ч |
| C4.2 | arm + компаратор: per строка - механика logpoint с eval `{name}`; в точке решения подавить/показать halt (suppress-gate `_handle_command`, `_user_visible_stops` M-1): значение == `client._watch_last[name]` -> подавить+Continue; изменилось -> record `{line, old, new, ts}` и по режиму held-halt | 1ч |
| C4.3 | Режимы: `record_only` (таймлайн изменений, всегда Continue) / `break_on_first_change` / `break_when` (предикат по new: `= 0`, `<> Истина` - сравнение через `_extract_eval_value`) | 0.5ч |
| C4.4 | Tools `debug_set_watchpoint(name, object_id, method?, mode, break_when?)` + `debug_watchpoint_result(clear=True)`; формат таймлайна как A3 | 0.5ч |
| C4.5 | Unit ×6: скан, компаратор (число/строка/Неопределено), 3 режима, подавление vs halt, clear | 0.5ч |
| C4.6 | Live MFM ×2: (а) worker-код `Ответ=1;Ответ=1;Ответ=2;` -> halt ТОЛЬКО на 3-й строке (1-я запись old=None, 2-я подавлена - не изменилось); (б) C1-инъекция: на held-halt `debug_set_variable("Ответ","99")` -> следующий fire ловит 99->N | 1ч |

Риск: eval на каждом fire горячей строки в цикле - дорого -> cap fires per line (default 200, как coverage) + предупреждение в ответе при достижении. Acceptance: кейс «где из 15 присваиваний СуммаДокумента обнуляется» = 1 arm + 1 триггер -> halt ровно на строке первого обнуления (`break_when "= 0"`).

### 8.5 C6 - Precise coverage (hit counts) + семантический replay-seek (~3ч)

| Шаг | Что | Оценка |
|---|---|---|
| C6.1 | Экспорт счётчиков (сбор УЖЕ есть `_hit_counters:314`): sidecar `<session>.counts.json` `{file, line, count}` рядом с genericCoverage.xml (сам generic-формат counts НЕ поддерживает - XML не трогаем) + `hot_lines` top-N в ответ `debug_coverage_export:5232`; опц. LCOV `DA:<line>,<count>` | 1ч |
| C6.2 | Снапшоты с переменными: `debug_session_record(capture_variables=False)` opt-in - на user-visible stop дописывать bounded top-K локалей (реюз A0 auto-discovery, cap как A2 halt-окно) в snapshot-entry (`snapshot.py`) | 0.5ч |
| C6.3 | Семантический seek: `debug_replay_seek(query="Итог < 0")` - парсер предиката `<имя> <оп> <литерал>` (`=,<>,<,>,<=,>=`; литералы число/строка/Истина/Ложь/Неопределено; спец-имена `line/reason/module`) по variables снапшота; числовой `index` продолжает работать (перегрузка аргумента) | 1ч |
| C6.4 | Unit ×6 (парсер, seek по переменной/спец-имени, снапшот без переменной -> skip, обратная совместимость index) + live: replay held-JOB с capture_variables -> `seek('КлючУдержания = "hold-c1b"')` | 0.5ч |

Acceptance: «первый halt где Итог < 0» - одним вызовом; горячие циклы видны в `hot_lines`.

### 8.6 A6 - Session-режимы (InspectWare) + correlation_id (~2ч)

| Шаг | Что | Оценка |
|---|---|---|
| A6.1 | Session-state enum (вычисляемый): `Start` (connected, targets нет) / `Runtime-State` (есть stopped) / `Runtime-Error` (stop reason=exception) / `Post-Mortem` (record включён, живых нет) / `Done` (disconnected) + статическая карта `valid_next` (имена tools, валидных в состоянии) | 0.5ч |
| A6.2 | Врезка `{session_state, valid_next}` в ответы КЛЮЧЕВЫХ tools (connect/ping/targets/step/target_state) одним хелпером `_state_hint()`; остальные не трогаем (шум) | 0.5ч |
| A6.3 | `debug_connect(correlation_id="")` (дефолт uuid4) -> persist `.active.json` (переживает HMR) -> прошить в артефакты: logpoint JSONL, snapshot-entry, coverage export, session_summary/ZIP. Формат совместим с CloudEvents `correlationid` фреймворка (`shared/invocation_logger`) | 0.5ч |
| A6.4 | Unit ×5: enum-переходы, valid_next, persist/restore HMR, метка в 3 артефактах | 0.5ч |

Acceptance: по correlation_id грепается вся цепочка артефактов задачи; агент на эфемерном target видит `valid_next` вместо тыка в 400. Делать ПЕРЕД A4 (label/correlation прогонов нужны диффу).

### 8.7 A4 - `debug_diff_runs(trigger_ok, trigger_fail, watch[])` differential (~5ч, самый большой)

Инвентаризация: `debug_session_diff:3523` уже диффит СВОДКИ (метрики BP/eval/timeline -> `regression_indicators`). НЕ хватает **state-level**: «на строке 200 в ok `Скидка=10`, в fail `Скидка=0`». Предпосылки: C6.2 (variables в снапшотах), A6.3 (label/correlation).

| Шаг | Что | Оценка |
|---|---|---|
| A4.1 | Формат прогона: `debug_session_record(label="ok"\|"fail")` + snapshot-entries с variables (C6.2) + монотонный `stop_seq` | 0.5ч |
| A4.2 | Managed-прогон ×2 внутри tool'а: arm (BP/capture_mode) -> исполнить `trigger_ok` -> собрать стопы с eval `watch[]` на каждом -> то же для `trigger_fail` (реюз autotrace-скелета, два подряд) | 1ч |
| A4.3 | Alignment: ключ `(module_fqn, line, hit_index_per_location)`; `flow_divergence` = первая позиция расхождения ПОСЛЕДОВАТЕЛЬНОСТЕЙ (в ok стоп есть, в fail нет / наоборот) - часто это и есть баг (ветка не выполнилась) | 1ч |
| A4.4 | State-diff по выровненным стопам: сравнение watch-значений (pres-строки) -> `first_state_divergence {location, watch, ok, fail}` + полный `diffs[]` (cap `max_stops=200`); `ignore_names`-паттерны (даты/GUID шумят) | 1ч |
| A4.5 | Ответ `{verdict: {first_divergence: {kind: flow\|state, ...}}, raw: {aligned, diffs}}`; two-infobase режим НЕ кодить - рецепт «два прогона против разных alias = два session_id» в SKILL | 0.5ч |
| A4.6 | Unit ×6 (alignment, hit_index, flow-div, state-div, ignore, cap) + live MFM: два held-JOB (`Ответ=42` vs `Ответ=0`), `watch=["Ответ"]` -> `first_state_divergence` | 1ч |

Acceptance: «работало вчера - сегодня нет» = 1 вызов -> первая точка расхождения (flow или state) без ручного сравнения глаз.

### 8.8 Сводка: волны по зависимостям, итоги

| Порядок | Пункт | Ядро | Зависит от | Live-harness |
|---|---|---|---|---|
| 1 | C3 breakpointLocations | 4ч (+1.5ч AST-стретч) | - | веер по worker-модулю + факты B1 |
| 2 | C2 Function BP | 3ч | C3.1 (или деградация) | FBP на `ВыполнитьКодСУдержанием` |
| 3 | A5 debug_hypothesis | 3.5ч | logpoints/capture_mode (есть), C3.1 желателен | 10 assertions / 1 прогон held-JOB |
| 4 | C4 Watchpoint | 4ч | A3-сканер (есть), C1 (есть) | 3 присваивания + C1-инъекция |
| 5 | C6 counts + semantic seek | 3ч | replay (есть) | replay held-JOB + seek |
| 6 | A6 režимы + correlation | 2ч | - | смоук + HMR-restore |
| 7 | A4 debug_diff_runs | 5ч | C6.2, A6.3 | два прогона ok/fail |
| | **Итого** | **~24.5ч** (+1.5ч стретч) | | ≈ исходная оценка W4 9ч + W5 15ч |

Пересобранные волны: **W4′ «строки и гипотезы»** = C3+C2+A5 (~10.5ч, взаимные пред-реквизиты) -> **W5′ «наблюдение состояния»** = C4+C6+A6+A4 (~14ч, A4 последним - собирает C6.2+A6.3).

**Общие правила реализации (уроки B1/C1, обязательны для каждого пункта):**
1. Unit-тесты билдеров/парсеров НЕ ловят рантайм-семантику RDBG (сигнатура `ФоновыеЗадания.Выполнить`, `timeout` в мс, success-shape без `processed`) -> **live-зонд на held-JOB harness ДО фиксации дизайна**, спорную семантику зондировать первой.
2. Всё, что ждёт триггера, - two-phase `arm/collect` + контракт `{verdict, raw}` (§3); Continue/снятие своих точек - в `finally`.
3. Захваты bounded (halt-окно 1-2с): top-N с явными полями усечения (`frames_bounded`-паттерн A2).
4. Новые модули -> `--watch` в `.mcp.json` (урок P0.D); новые ПАРАМЕТРЫ существующих tools -> `/mcp reconnect` (harness кеширует schema).
5. Каждый пункт = отдельный 4-этапный pipeline (план/дизайн/код/тест) + code-verify субагентом + прогресс в этом роадмапе.
