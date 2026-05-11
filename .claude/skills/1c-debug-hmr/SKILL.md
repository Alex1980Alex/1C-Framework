---
name: 1c-debug-hmr
description: "1c-debug-hmr — MCP debug-сервер для 1С:Предприятие с hot-module-reload + persistent session. ИСПОЛЬЗУЙ при отладке BSL-кода (BP, stack, locals, evaluate, step), а так же при разработке самого debug-wrapper'а — изменения подхватываются без /mcp reconnect. 20 tools (включая P0.A-G + P1.A-B batch 2026-05-11): connect/disconnect, ping (unified dispatch + no_fire_diagnostics), set_breakpoint (+ condition + hit_condition), set_logpoint (tracepoint с {expr} placeholders → JSONL), get_breakpoints, break_on_next, arm_warm_rphosts (P0.F), arm_next_rphost (P0.G silent arm warm pool), targets, target_state, stack_trace (+resolved_source FQN+file_path per frame), variables (auto-discover BSL locals), evaluate, step, attach_targets, wait_for_target, launch_thin_client. Cascade auto-Continue (P0.D) + BP-propagation drain (P0.E) встроены. Сессия RDBG переживает HMR-restart через `data/debug_sessions/.active.json`. Триггеры: 'отладка 1С', 'breakpoint BSL', 'callStack 1С', 'debug rphost', 'debug ManagedClient', 'debug_connect', 'debug_ping', 'debug_set_breakpoint', 'debug_set_logpoint', 'debug_stack_trace', 'debug_variables', 'debug_evaluate', 'debug_arm_warm_rphosts', 'debug_arm_next_rphost', 'force_recycle_rphost', 'StopOnNextLine', 'pre-existing rphost', 'warm pool', 'conditional BP', 'hit_condition', 'logpoint', 'tracepoint', 'resolved_source', 'cascade halt'. НЕ для написания BSL-кода (→ bsl-development), НЕ для запросов к БД (→ 1c-mcp-crud), НЕ для VA BDD UI-тестов (→ va-bdd-testing)."
---

# 1c-debug-hmr — MCP Debug Server для 1С с HMR

## Обзор

MCP-сервер на FastMCP/Python поверх **1С RDBG-протокола** (`dbgs.exe :1550` через HTTP). Реализует Debug UI на стороне Claude Code. Обёрнут в `mcp_hmr_proc.py` для live-reload без потери session к RDBG.

| Аспект | Детали |
|---|---|
| Tool prefix | `mcp__1c-debug-hmr__*` (или `mcp__1c-debug__*` для plain-варианта без HMR) |
| Wrapper | [`tools/bsl-debug-server/mcp_hmr_proc.py`](../../tools/bsl-debug-server/mcp_hmr_proc.py) |
| Inner server | [`tools/bsl-debug-server/mcp_debug_server.py`](../../tools/bsl-debug-server/mcp_debug_server.py) |
| Тестов | 213+ unit (test_mcp_debug_server.py) + 13 schema (test_autonomous_debug_test.py) |
| Подробная документация | [docs/framework documentation/36_AUTONOMOUS_DEBUG_CONTROL/](../../docs/framework%20documentation/36_AUTONOMOUS_DEBUG_CONTROL/) |

## Триггеры

- 'отладка 1С', 'BSL debugger', 'remote debug 1С'
- 'breakpoint BSL', 'set BP', 'BP fires', 'callStackFormed'
- 'rphost debug', 'ManagedClient debug', 'StopOnNextLine'
- 'pre-existing rphost', 'force_recycle_rphost'
- 'inspect locals', 'evaluate BSL expression', 'step over BSL'
- 'debug_connect', 'debug_ping', 'debug_set_breakpoint', 'debug_stack_trace', 'debug_variables', 'debug_evaluate', 'debug_step', 'debug_targets', 'debug_break_on_next', 'debug_target_state', 'debug_get_breakpoints', 'debug_attach_targets', 'debug_disconnect'
- 'debug_set_logpoint', 'logpoint', 'tracepoint', 'conditional BP', 'hit count', 'hit_condition', 'message_template', 'resolved_source'
- 'debug_arm_warm_rphosts', 'debug_arm_next_rphost', 'warm pool', 'silent arm', 'suspendedByOther'
- 'cascade halt', 'BP propagation', 'attached_pending', 'break_on_next_silent_arm'
- 'debug_coverage_register', 'debug_coverage_export', 'code coverage', 'genericCoverage.xml', 'SonarQube coverage', 'lineToCover', 'covered=true'
- 'debug_session_summary artifacts', 'CI artifact', 'PR ZIP bundle', 'session ZIP'
- 'HMR debug wrapper', '.active.json', 'session restoration'

НЕ для написания BSL-кода — используй `bsl-development`.
НЕ для запросов / data-access — используй `1c-mcp-crud`.
НЕ для VA BDD UI-тестов — используй `va-bdd-testing`.
НЕ для документации платформы 8.3.27 — используй `1c-doc-research`.

## Архитектура

```
┌──────────────┐  stdio  ┌──────────────────┐  stdio  ┌──────────────────────┐
│ Claude Code  │ ──────► │ mcp_hmr_proc.py  │ ──────► │ mcp_debug_server.py  │
│ MCP harness  │ ◄────── │ (HMR wrapper)    │ ◄────── │ (RDBGClient)         │
└──────────────┘         └─────────┬────────┘         └──────────┬───────────┘
                                   │ watchfiles                  │ HTTP
                                   ▼                              ▼
                         ┌──────────────────┐        ┌──────────────────────┐
                         │ source files     │        │ dbgs.exe :1550       │
                         │ (auto-reload)    │        │ (1С debug agent)     │
                         └──────────────────┘        └──────────────────────┘
                                                                 │
                                                                 ▼
                                                    ┌──────────────────────┐
                                                    │ rphost / ManagedCl.  │
                                                    │ (debug targets)      │
                                                    └──────────────────────┘
```

**HMR-flow**: edit `*.py` → `watchfiles` → wrapper kills child → spawns new → replays cached `initialize` → emits `notifications/{tools,resources,prompts}/list_changed` → harness re-fetches list. Session к RDBG переживает через `.active.json`.

## Конфигурация (`.mcp.json`)

```json
"1c-debug-hmr": {
  "command": "C:\\1С-Framework\\.venv\\Scripts\\python.exe",
  "args": [
    "C:\\1С-Framework\\tools\\bsl-debug-server\\mcp_hmr_proc.py",
    "C:\\1С-Framework\\tools\\bsl-debug-server\\mcp_debug_server.py",
    "--watch", "C:\\1С-Framework\\tools\\bsl-debug-server\\bsl_locals.py",
    "--watch", "C:\\1С-Framework\\tools\\bsl-debug-server\\uuid_index.py"
  ],
  "cwd": "C:\\1С-Framework\\tools\\bsl-debug-server",
  "env": { "PYTHONIOENCODING": "utf-8" },
  "timeout": 60000
}
```

Параллельно живёт `1c-debug` (без HMR) — те же tools, без watchfiles overhead'а.

## API tools (25)

> **Roadmap 260511 P2.A + P3.B (2026-05-11, post-P1):** +5 tools — `debug_set_exception_bp` / `debug_clear_exception_bps` / `debug_list_exception_bps` (P3.B filtered exception BPs), `debug_session_record` / `debug_replay_list` / `debug_replay_seek` (P2.A snapshot replay).

> **Roadmap 260511 P1 batch (2026-05-11, P0 follow-up):** +2 tools — `debug_coverage_register` + `debug_coverage_export` (P1.A SonarQube genericCoverage.xml). Extended `debug_session_summary(format="artifacts")` produces ZIP bundle for PR/CI (P1.B). Полная документация: [§36.8](../../docs/framework%20documentation/36_AUTONOMOUS_DEBUG_CONTROL/36.8_Advanced_Debug_Features.md).

> **Roadmap 260511 P0.A–G batch (2026-05-11, later same day):** добавлены 3 новых tools — `debug_set_logpoint` (P0.B), `debug_arm_warm_rphosts` (P0.F), `debug_arm_next_rphost` (P0.G). Расширены `debug_set_breakpoint(condition, hit_condition)` (P0.A) и `debug_stack_trace` с `resolved_source` per frame (P0.C). Cascade auto-Continue (P0.D) + BP-propagation drain (P0.E) встроены в `_handle_command`. Полная документация: [§36.8 Advanced Debug Features](../../docs/framework%20documentation/36_AUTONOMOUS_DEBUG_CONTROL/36.8_Advanced_Debug_Features.md).
>
> **Roadmap 260511 update (2026-05-11):** добавлены `debug_wait_for_target` (§3.4) и `debug_launch_thin_client` (§3.5). `debug_connect` расширен `recycle_strategy` параметром (§3.2, backward-compat для `force_recycle_rphost=True`). `debug_ping` теперь surface'ит `no_fire_diagnostics` после 3 consecutive empty pings (§3.6). `_validate_infobase_alias` cross-check'ает alias через `rac infobase list` ПЕРЕД attach (§3.1, closes RC1 из GKSTCPLK-2468).

### Управление сессией

| Tool | Назначение |
|---|---|
| `debug_connect(debug_url, infobase_alias, force_recycle_rphost?, recycle_strategy?)` | Attach debug UI к dbgs. **Alias validation (§3.1 P0):** fail-fast если alias не в `rac infobase list`. **`recycle_strategy` (§3.2 P0):** `auto`/`none`/`pre_existing`/`all_rphosts_of_ib`/`all_rphosts_of_cluster`. `force_recycle_rphost=True` → resolves к `pre_existing` (backward-compat). Use `all_rphosts_of_ib` для HTTP-service triggers (closes RC2) |
| `debug_launch_thin_client(infobase_alias, user?, password?, ...)` | **(§3.5 P1)** Запуск 1cv8c.exe с правильными `/Debug -http /DebuggerURL=http://localhost:1550`. Auto-detect platform path. Закрывает RC3 (protocol mismatch). После launch — waits up to `wait_target_timeout_sec` для регистрации target'а |
| `debug_wait_for_target(timeout_sec, poll_interval_sec)` | **(§3.4 P1)** Block until ≥1 target в `debug_targets`. Sync primitive для гарантированного attach после `debug_connect` / `launch_thin_client` перед `set_breakpoint` |
| `debug_disconnect()` | Detach + чистит `.active.json` |
| `debug_ping()` | Pull events + **dispatch через `_handle_command`**. **(§3.6 P2)** После 3 consecutive empty pings — surface `no_fire_diagnostics` с auto-detected RC1/RC2 root causes и actionable suggestions |
| `debug_target_state(target_id?)` | С пустым `target_id` — wrapper-side snapshot (infobase, session_id, attached_known_targets, last_stopped) без RDBG round-trip'а. С `target_id` — resolve через `get_targets()` |
| `debug_targets()` | List active rphost / ManagedClient targets с состоянием (`Worked` / `StopOnNextLine` / etc.) |
| `debug_attach_targets(target_ids[], attach=True)` | Принудительное attach/detach к Debug UI (troubleshooting если ping event-loop пропустил `targetStarted`) |
| `debug_arm_warm_rphosts(target_types=["HTTPService","JOB","Server"])` | **(P0.F roadmap 260511)** Attach all visible targets matching filter, mark as `_attached_pending` (P0.E drain on next halt), re-apply BP workspace. Returns `armed_targets[]` + `bp_workspace_reapplied`. Pass `[]` to arm without filter |
| `debug_arm_next_rphost()` | **(P0.G roadmap 260511)** Silent-arm next halting rphost via `setBreakOnNextStatement(silent=True)`. Wrapper auto-attaches + drains + Continues — no user-visible stop. Полезно для warm-pool HTTPService rphost'ов невидимых через getDbgAllTargetStates |

### Breakpoints

| Tool | Назначение |
|---|---|
| `debug_set_breakpoint(object_id, line, module_type?, property_id?, condition?, hit_condition?)` | Set BP. `module_type ∈ {CommonModule, ManagerModule, ObjectModule, RecordSetModule, FormModule, CommandModule}` — `propertyID` auto-resolves. Cache aggregation: multiple BPs одного модуля группируются в один request. **(P0.A roadmap 260511)** `condition` — BSL-выражение, RDBG-native filter. `hit_condition` — VS Code DAP syntax (`>N`/`>=N`/`<N`/`<=N`/`=N`/`%N`), wrapper-level counter |
| `debug_set_logpoint(object_id, line, message_template, module_type?, property_id?)` | **(P0.B roadmap 260511)** Tracepoint без halt: на каждом fire render'ит `{expr}` placeholders в template через `client.evaluate`, append'ит JSONL entry в `data/debug_logs/<session>.jsonl`, auto-Continue. SECURITY: placeholders execute as BSL в running rphost — не передавай untrusted templates |
| `debug_get_breakpoints()` | Client-side cache (RDBG не expose'ит server-side getBreakpoints URL) |
| `debug_break_on_next()` | Global trap — **следующая** BSL-инструкция на ANY rphost для этой infobase'ы остановится. Обходит pre-existing rphost gap (см. §10/§11 roadmap) |

### Inspection

| Tool | Назначение |
|---|---|
| `debug_stack_trace(target_id?)` | Cache-first (через `last_stopped_target_id`), fallback на `getCallStack` HTTP. Error envelope: при exception возвращает `{"error": "<Type>: <repr>", "target_id": ...}`. **(P0.C roadmap 260511)** Каждый frame обогащён полем `resolved_source: {fqn, file_path, exists}` через `uuid_index.get_source_info` (UUID → `Документ.<name>.МодульМенеджера` + file path) |
| `debug_variables(target_id?, stack_level=0, expressions?)` | **Auto-discovery** (default) — парсит BSL-source на текущей строке через `uuid_index + bsl_locals`, batch-eval'ит params + `Перем` + assignments. **Explicit names** — `expressions=["A","B"]` пропускает source parsing |
| `debug_evaluate(expression, target_id?, stack_level=0)` | Eval любого BSL-выражения. Поддерживает composite types (Структура, ДокументСсылка, ЗначениеПеречисления) |

### Coverage & Artifacts (P1 batch)

| Tool | Назначение |
|---|---|
| `debug_coverage_register(lines: list[dict])` | **(P1.A roadmap 260511)** Register BSL lines for code coverage. Each entry: `{object_id, line, module_type?, property_id?, file_path?}`. Зарегистрированные BPs работают как silent counter — на fire wrapper инкрементит hit + auto-Continue (без JSONL noise) |
| `debug_coverage_export(output_path="")` | **(P1.A roadmap 260511)** Emit SonarQube `genericCoverage.xml` со всеми tracked lines (`covered=true` если hit, `false` иначе). Default path: `data/debug_coverage/<session>.xml`. Returns `{path, files_count, lines_total, lines_covered, coverage_pct}` |
| `debug_session_summary(format="artifacts")` | **(P1.B roadmap 260511)** Существующий tool, новый format. Packages session в ZIP bundle: `summary.json` + `summary.md` + `breakpoints_cache.json` + `stop_events.json` + `logpoint_log.jsonl` (если есть) + `stack_snapshots/<tid>.json`. Returns `{path, size_bytes, files[]}`. Для PR upload как artifact |

### Управление выполнением

| Tool | Назначение |
|---|---|
| `debug_step(action, target_id?)` | `Continue` / `Step` (over) / `StepIn` / `StepOut` |

## HMR Persistent Session

### Что переживает HMR-restart

| State | Сохраняется через |
|---|---|
| `session_id` (RDBG dbgui) | `.active.json` → `_get_client()` cold-start restore |
| `debug_url`, `infobase_alias` | то же |
| `_attached`, `_registered` | устанавливаются в `True` при restore |
| Background `_ping_task` | пересоздаётся в `_get_client()` через `asyncio.create_task(_ping_loop())` |

### Что НЕ переживает (приемлемо)

- BP cache (`_set_breakpoints_cache`) — пользователю надо re-set BPs
- Stop-state cache (`_stopped_targets`, `_last_stack_by_target`) — заполнится из ping events
- Async eval futures (`_pending_evals`) — in-flight evals теряются, retry клиентом

### `.active.json` shape

```json
{
  "session_id": "fed35b9e-0269-472b-9605-3a7c5dbd9874",
  "debug_url": "http://localhost:1550",
  "infobase_alias": "ИБTransportManagementDevelop",
  "persisted_at": 1778433327.7219038
}
```

Атомарная запись через `tmp + os.replace`. Файл живёт в `tools/bsl-debug-server/data/debug_sessions/.active.json`. Без TTL — stale state self-correctится через UI+ recovery escalation.

## Типичные шаблоны

### Шаблон 1: Single-BP debug (через thin client)

```
1. debug_health_check  ──→  ready=true; pre_existing_rphosts=[…]
2. debug_connect(infobase_alias="ИБTransport…", force_recycle_rphost=True)  если warning
3. debug_break_on_next  ──→  status=ok
4. (запустить thin client с /Debug — спавнит ManagedClient + Server target)
5. debug_ping  ──→  callStackFormed event; cache populated
6. debug_stack_trace  ──→  full stack JSON, depth=N
7. debug_variables  ──→  auto-discovered BSL locals
8. debug_evaluate("Контрагент.ИНН")  ──→  resultValueInfo
9. debug_step("Continue")  ──→  state Worked
10. debug_disconnect  ──→  чистит .active.json
```

### Шаблон 2: Precise BP на конкретный модуль

```
1. (через mcp__1c-mcp-crud__get_metadata_details получить objectID + propertyID)
2. debug_connect(infobase_alias=...)
3. debug_set_breakpoint(object_id="<UUID>", line=42, module_type="CommonModule")
4. debug_get_breakpoints  ──→  verify в client cache
5. (триггер выполнения BSL — UI / HTTP-service / scheduled job)
6. debug_ping  ──→  callStackFormed на нашей строке
7. inspect / step как выше
```

### Шаблон 3: HMR live-development debug-wrapper'а

```
1. debug_connect → arm tools, run baseline scenario
2. (edit mcp_debug_server.py — fix bug или add feature)
3. watchfiles детектирует → wrapper restartit subprocess
4. .active.json восстанавливает session_id
5. debug_ping → events:[] (не 400!), cache работает
6. Проверить fix через те же tools
7. (никаких /mcp reconnect, никакого re-attach к dbgs)
```

### Шаблон 4: Pre-existing rphost через force-recycle

```
debug_connect(infobase_alias="…")
  ──→  preflight_warning: pre_existing_pids=[45632]
  ──→  recommended: Solution A (force_recycle_rphost=True)

debug_disconnect  + debug_connect(force_recycle_rphost=True)
  Если schema MCP-tool НЕ имеет force_recycle (harness кеш) — workaround через PowerShell:
    & "C:\Program Files (x86)\1cv8\8.3.27.1936\bin\rac.exe" \
        process turn-off --cluster=<UUID> --process=<proc-UUID> localhost:1545
```

### Шаблон 5: BP-verification в /implement-1c-task pipeline (Этап 5.x)

8-шаговый протокол, исполняемый skill'ом `implement-1c-task` v2.7.0+ для КАЖДОЙ `[ADDED]`/`[MODIFIED]` точки модификации из ANALYSIS-REPORT. Mock-test reference: [`scripts/test_implement_1c_task_bp_verification.py`](../../../scripts/test_implement_1c_task_bp_verification.py) (5 сценариев).

```
1. debug_connect(infobase_alias=<ИБ>)
     если не connected — attach как Debug UI; иначе reuse сессию
2. debug_set_breakpoint(object_id=<UUID>, line=<MODIFIED_LINE>, module_type=<TYPE>)
     propertyID auto-resolves
3. debug_get_breakpoints
     verify BP в client cache (enabled=True, lineNo совпадает)
4. (trigger) mcp__1c-mcp-crud__execute_code "<минимальный harness вызывающий MODIFIED процедуру>"
     OR HTTP-сервис trigger через execute_query
     ВАЖНО: убедиться что update_database выполнен ДО trigger (иначе rphost на старой компиляции)
5. debug_ping  ──→  callStackFormed (max 3 iterations)
     если no stop ──→ fallback (a) debug_break_on_next + retry trigger
                  ──→ fallback (b) debug_connect(force_recycle_rphost=True) + retry
                  ──→ если оба fallback'а не сработали ──→ SKIP с обоснованием, block перехода на Этап 6
6. debug_stack_trace  ──→  assert frames[0].lineNo == MODIFIED_LINE
     если mismatch ──→ FAIL с error «expected line N in <module>, got M in <other>»
                   ──→ still call debug_step(Continue) чтобы release rphost
7. (опц.) debug_variables  ──→  state assertion против invariants из ANALYSIS-REPORT
8. debug_step(action="Continue")  ──→  release rphost; обязательно даже на FAIL
```

**Регистрация результата** в IMPLEMENTATION-PROGRESS.md (Этап 7):

```markdown
### Точка N — BP verification
- Module: <FQN>:<lineNo>
- BP set: ✓ (propertyID=<auto>, enabled=true)
- Trigger: execute_code "<краткое описание harness>"
- Stack hit: frames[0].lineNo=<actual>, moduleName=<actual> — assert PASS / FAIL
- Variables (если проверялись): <name=value@stack_level>
- Step Continue: ✓ released rphost
```

**Опционально (Этап 5.y Regression diff)** — если в footer'е IMPLEMENTATION-PROGRESS.md есть `<!-- debug_session_id: <UUID> -->`:

```
debug_session_diff(prev_session_id=<UUID-из-footer>, curr_session_id=<current>)
  ──→  verdict ∈ {NO_REGRESSION, IMPROVEMENT, NEUTRAL, REGRESSION}
  если REGRESSION ──→ block перехода на Этап 6, вывод markdown-таблицы метрик
```

Footer обновляется на текущий `session_id` ТОЛЬКО при успешном завершении всего pipeline (Этап 5.x PASS + Этап 6 PASS), чтобы baseline сохранялся для следующей попытки исправления.

## Диагностика

| Симптом | Причина | Решение |
|---|---|---|
| `400 «UI+ часть отладки не зарегистрирована»` после HMR-restart | Pre-fix: cache не заполнен manual ping'ом. Post-fix (commit 1872dff): не должно встречаться. Если встретился — `.active.json` устарел → существующий UI+ recovery escalation сделает re-attach автоматически за 1 round-trip | Игнорировать, retry следующий tool — wrapper сам отрегенерит |
| `debug_targets returns []`, клиент запущен | Клиент стартанул БЕЗ `/Debug` flag → не зарегистрирован в RDBG | Запустить с `/Debug /DebuggerURL=tcp://localhost:1550`. Альтернатива: `debug_break_on_next` поймает на любом rphost после первой BSL-инструкции |
| `BPs не fire'ят` на pre-existing rphost | RDBG не attach'ит retroactively (DBGUIExtCmdInfoStarted only on spawn) | `force_recycle_rphost=True` в `debug_connect` ИЛИ rac.exe `process turn-off` ИЛИ trigger через UI запущенный ПОСЛЕ connect (Solution C) |
| Curl на IIS HTTP-service не trap'ится | IIS COM-cache держит соединение со старым rphost даже после ragent recycle | Trigger через thin client (минует IIS-tier) ИЛИ `iisreset` (кроет всех users) |
| `debug_stack_trace` пустой error | Pre-fix: silent fail на cache-miss + httpx error с empty body. Post-fix (6376354 + 1872dff): error envelope `{"error": "<Type>: <repr>"}` | Прочитать error message, обычно `RuntimeError` или `httpx.HTTPStatusError` |
| Long Russian path mid-untracked-stash | Windows MAX_PATH (~260) при `git stash --include-untracked` | `git -c core.longpaths=true stash …` |
| Schema cache в harness'е после edit'а MCP-tool параметров | `notifications/tools/list_changed` не обновляет JSON-schema параметров | `/mcp` reconnect в Claude Code (полный teardown) |

## Антипаттерны

| Антипаттерн | Почему плохо | Как правильно |
|---|---|---|
| Запускать `1c-debug-hmr` в production CI | Watchfiles overhead, лишний subprocess layer | Использовать plain `1c-debug` для CI/non-dev |
| Использовать IIS publication name как `infobase_alias` | RDBG различает cluster IB name (`ИБ…`), не IIS-publication (`transport`) | `infobase_alias` = name из `rac infobase list` ИЛИ из `Srvr=…;Ref=…` строки подключения |
| Игнорировать `pre_existing_rphost_warning` | BPs на этих rphost'ах никогда не fire'ят silent | `force_recycle_rphost=True` ИЛИ `debug_break_on_next` ИЛИ Solution C (UI после connect) |
| Manual `debug_ping` в надежде что cache не заполнится | Post-fix `ping()` ВСЕГДА dispatch'ит — manual и background равноправны | Просто использовать `debug_stack_trace` напрямую, cache уже заполнен |
| Полагаться на schema MCP-tool после edit'а | Harness кеширует initial-handshake schema | `/mcp` reconnect ИЛИ workaround через прямой инструмент (rac.exe вместо `force_recycle_rphost`) |
| Хранить session_id где-то ещё кроме `.active.json` | Дублирование state, race window | Только `.active.json`, single source of truth |
| Использовать произвольный `infobase_alias` (e.g. `TestDB`) | До roadmap 260511 §3.1 (P0) RDBG silently возвращал registered=true; filter повисал на несуществующее имя → BPs не fire | Alias = имя из `rac infobase summary list --cluster=<UUID>`. Для коротких имён — env `DEBUG_INFOBASE_ALIASES="Short:Long;..."` (§3.7 P2). Validation теперь fail-fast |
| `/DebuggerURL="tcp://..."` в thin client launch | 1С debug agent работает в http-mode (`-debug -http`) → protocol mismatch → "Неверно указан протокол отладки" | Use `http://localhost:1550` + `-http` flag. Лучше: `debug_launch_thin_client` (§3.5 P1) — auto-flagged |
| `recycle_strategy="none"` при HTTP-service triggers | HTTP-service (`1c-mcp-crud:execute_code`) spawn'ит новый rphost вне pre-existing snapshot → 0 BP fire (RC2 из GKSTCPLK-2468) | Use `recycle_strategy="all_rphosts_of_ib"` (§3.2 P0) для HTTP-service workflow, либо Solution C (UI re-post после thin client launch) |
| Только static analysis для BSL код-flow | Composite types / runtime branching могут отличаться от static prediction (e.g. `гкс_ДокументРегистрации` оказывается ФНП, не РегистрацияПЛК) | После Phase 2 в analyze-1c-task — обязательный Phase 2.5 Runtime Trace через 1c-debug-hmr: set BP + variables + evaluate ДО реализации |
| Игнорировать `no_fire_diagnostics` в `debug_ping` | После 3 consecutive empty pings wrapper auto-detect'ит RC1/RC2 и suggestions; pre-§3.6 это требовало 5+ ручных проверок | Прочитать `no_fire_diagnostics.suggestions` — там готовые actionable hints |
| Передавать `/P <password>` в `debug_launch_thin_client` на shared/production машине | 1cv8c.exe CLI argv виден всем юзерам через `Get-Process \| Select CommandLine` (Win32 process metadata). Пароль logged'ится в audit, попадает в WMI cache, exposed в Task Manager / Process Explorer всем сессиям | Только personal dev-машина с одним user account. В shared контекстах — Windows-auth (`/WA` flag) или сохранённые credentials в 1С client storage. Wrapper surface'ит `security_note` в response при наличии password — НЕ игнорировать |

## Связанные скиллы

| Скилл | Связь |
|---|---|
| **`implement-1c-task`** | **Used by /implement-1c-task Этап 5.x BP-verification** — 8-шаговый протокол (Шаблон 5 выше) исполняется автоматически для каждой `[ADDED]`/`[MODIFIED]` точки в режиме Full. Также Этап 0 Preflight (`debug_health_check`) и Этап 5.y Regression diff (`debug_session_diff`). v2.7.0+ (2026-05-11). |
| **`analyze-1c-task-v2`** | **Used by /analyze-1c-task --trace Phase 2.5 Runtime Trace** — live BP-trace для алгоритмов с ≥3 runtime-ветвлений (`Пользователи.ТекущийПользователь()`, `ПолучитьФункциональнуюОпцию`, `Тип(Параметр)`). Output: секция «3.Y Runtime Trace» в ANALYSIS-REPORT с Discrepancies (static vs runtime). v4.2.0+ (2026-05-11). |
| `1c-mcp-crud` | Триггер BSL execution через HTTP-service для последующего trap'а в debug-wrapper |
| `bsl-development` | Написание BSL-кода, который потом дебажим |
| `va-bdd-testing` | UI-уровень тестов; debug-wrapper — server-side BSL inspection |
| `1c-doc-research` | Спецификация платформы 8.3.27, RDBG-протокол |
| `auto-test-after-write` | Автозапуск синтаксис-чека после write — параллельный pipeline |

**Production integration:** Phase 1+2 roadmap [260510](../../../docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md) закрыт 2026-05-11. Mock-acceptance тесты: [`test_implement_1c_task_bp_verification.py`](../../../scripts/test_implement_1c_task_bp_verification.py) (5 сценариев) + [`test_analyze_1c_task_runtime_trace.py`](../../../scripts/test_analyze_1c_task_runtime_trace.py) (5 сценариев).

## Источники

- `tools/bsl-debug-server/mcp_debug_server.py` — RDBGClient + 13 MCP tools
- `tools/bsl-debug-server/mcp_hmr_proc.py` — HMR subprocess wrapper
- `tools/bsl-debug-server/tests/test_mcp_debug_server.py` — 199 unit-tests
- `docs/framework documentation/36_AUTONOMOUS_DEBUG_CONTROL/` — полная архитектурная документация (7 глав)
- `docs/roadmap/260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md` — original roadmap (§10/§11/§12/§13)
- `docs/roadmap/260510_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md` — HMR + ping dispatch fixes
- yukon39/bsl-debug-server (Java, 1.1-SNAPSHOT) — reference для RDBG XML wire-protocol
