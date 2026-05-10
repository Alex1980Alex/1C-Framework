---
name: 1c-debug-hmr
description: "1c-debug-hmr — MCP debug-сервер для 1С:Предприятие с hot-module-reload + persistent session. ИСПОЛЬЗУЙ при отладке BSL-кода (BP, stack, locals, evaluate, step), а так же при разработке самого debug-wrapper'а — изменения подхватываются без /mcp reconnect. 13 tools: connect/disconnect, ping (с unified dispatch), set_breakpoint, get_breakpoints, break_on_next, targets, target_state, stack_trace (cache-first + error envelope), variables (auto-discover BSL locals), evaluate, step, attach_targets, target_state. Сессия RDBG переживает HMR-restart через `data/debug_sessions/.active.json`. Триггеры: 'отладка 1С', 'breakpoint BSL', 'callStack 1С', 'debug rphost', 'debug ManagedClient', 'debug_connect', 'debug_ping', 'debug_set_breakpoint', 'debug_stack_trace', 'debug_variables', 'debug_evaluate', 'force_recycle_rphost', 'StopOnNextLine', 'pre-existing rphost'. НЕ для написания BSL-кода (→ bsl-development), НЕ для запросов к БД (→ 1c-mcp-crud), НЕ для VA BDD UI-тестов (→ va-bdd-testing)."
---

# 1c-debug-hmr — MCP Debug Server для 1С с HMR

## Обзор

MCP-сервер на FastMCP/Python поверх **1С RDBG-протокола** (`dbgs.exe :1550` через HTTP). Реализует Debug UI на стороне Claude Code. Обёрнут в `mcp_hmr_proc.py` для live-reload без потери session к RDBG.

| Аспект | Детали |
|---|---|
| Tool prefix | `mcp__1c-debug-hmr__*` (или `mcp__1c-debug__*` для plain-варианта без HMR) |
| Wrapper | [`tools/bsl-debug-server/mcp_hmr_proc.py`](../../tools/bsl-debug-server/mcp_hmr_proc.py) |
| Inner server | [`tools/bsl-debug-server/mcp_debug_server.py`](../../tools/bsl-debug-server/mcp_debug_server.py) |
| Тестов | 199 unit (test_mcp_debug_server.py) + 13 schema (test_autonomous_debug_test.py) |
| Подробная документация | [docs/framework documentation/36_AUTONOMOUS_DEBUG_CONTROL/](../../docs/framework%20documentation/36_AUTONOMOUS_DEBUG_CONTROL/) |

## Триггеры

- 'отладка 1С', 'BSL debugger', 'remote debug 1С'
- 'breakpoint BSL', 'set BP', 'BP fires', 'callStackFormed'
- 'rphost debug', 'ManagedClient debug', 'StopOnNextLine'
- 'pre-existing rphost', 'force_recycle_rphost'
- 'inspect locals', 'evaluate BSL expression', 'step over BSL'
- 'debug_connect', 'debug_ping', 'debug_set_breakpoint', 'debug_stack_trace', 'debug_variables', 'debug_evaluate', 'debug_step', 'debug_targets', 'debug_break_on_next', 'debug_target_state', 'debug_get_breakpoints', 'debug_attach_targets', 'debug_disconnect'
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

## API tools (13)

### Управление сессией

| Tool | Назначение |
|---|---|
| `debug_connect(debug_url, infobase_alias, force_recycle_rphost?)` | Attach debug UI к dbgs. `force_recycle_rphost=True` убивает pre-existing rphost'ы через `rac process turn-off` (ragent спавнит свежий, который видим в RDBG). Имя кластерной IB (не IIS publication name!) |
| `debug_disconnect()` | Detach + чистит `.active.json` |
| `debug_ping()` | Pull events + **dispatch через `_handle_command`** (заполняет cache, auto-attach новых targets, обрабатывает `callStackFormed`/`quit`). Возвращает raw events для inspection |
| `debug_target_state(target_id?)` | С пустым `target_id` — wrapper-side snapshot (infobase, session_id, attached_known_targets, last_stopped) без RDBG round-trip'а. С `target_id` — resolve через `get_targets()` |
| `debug_targets()` | List active rphost / ManagedClient targets с состоянием (`Worked` / `StopOnNextLine` / etc.) |
| `debug_attach_targets(target_ids[], attach=True)` | Принудительное attach/detach к Debug UI (troubleshooting если ping event-loop пропустил `targetStarted`) |

### Breakpoints

| Tool | Назначение |
|---|---|
| `debug_set_breakpoint(object_id, line, module_type?, property_id?)` | Set BP. `module_type ∈ {CommonModule, ManagerModule, ObjectModule, RecordSetModule, FormModule, CommandModule}` — `propertyID` auto-resolves через MODULE_PROPERTY_IDS. Cache aggregation: multiple BPs одного модуля группируются в один request (RDBG `setBreakpoints` REPLACES workspace per call) |
| `debug_get_breakpoints()` | Client-side cache (RDBG не expose'ит server-side getBreakpoints URL) |
| `debug_break_on_next()` | Global trap — **следующая** BSL-инструкция на ANY rphost для этой infobase'ы остановится. Обходит pre-existing rphost gap (см. §10/§11 roadmap) |

### Inspection

| Tool | Назначение |
|---|---|
| `debug_stack_trace(target_id?)` | Cache-first (через `last_stopped_target_id`), fallback на `getCallStack` HTTP. Error envelope: при exception возвращает `{"error": "<Type>: <repr>", "target_id": ...}` |
| `debug_variables(target_id?, stack_level=0, expressions?)` | **Auto-discovery** (default) — парсит BSL-source на текущей строке через `uuid_index + bsl_locals`, batch-eval'ит params + `Перем` + assignments. **Explicit names** — `expressions=["A","B"]` пропускает source parsing |
| `debug_evaluate(expression, target_id?, stack_level=0)` | Eval любого BSL-выражения. Поддерживает composite types (Структура, ДокументСсылка, ЗначениеПеречисления) |

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

## Связанные скиллы

| Скилл | Связь |
|---|---|
| `1c-mcp-crud` | Триггер BSL execution через HTTP-service для последующего trap'а в debug-wrapper |
| `bsl-development` | Написание BSL-кода, который потом дебажим |
| `va-bdd-testing` | UI-уровень тестов; debug-wrapper — server-side BSL inspection |
| `1c-doc-research` | Спецификация платформы 8.3.27, RDBG-протокол |
| `auto-test-after-write` | Автозапуск синтаксис-чека после write — параллельный pipeline |
| `analyze-1c-task-v2` | 5-фазный анализ задачи; debug может потребоваться на фазе 4 (verification) |

## Источники

- `tools/bsl-debug-server/mcp_debug_server.py` — RDBGClient + 13 MCP tools
- `tools/bsl-debug-server/mcp_hmr_proc.py` — HMR subprocess wrapper
- `tools/bsl-debug-server/tests/test_mcp_debug_server.py` — 199 unit-tests
- `docs/framework documentation/36_AUTONOMOUS_DEBUG_CONTROL/` — полная архитектурная документация (7 глав)
- `docs/roadmap/260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md` — original roadmap (§10/§11/§12/§13)
- `docs/roadmap/260510_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md` — HMR + ping dispatch fixes
- yukon39/bsl-debug-server (Java, 1.1-SNAPSHOT) — reference для RDBG XML wire-protocol
