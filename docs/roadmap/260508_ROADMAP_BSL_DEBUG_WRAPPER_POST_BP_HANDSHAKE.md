# Roadmap — Доработка `mcp_debug_server.py` post-BP-fire handshake

**Дата:** 2026-05-08
**Статус:** ✅ P1 acceptance validated 2026-05-10 (thin client scenario, см. §0 «Validation results»). ❌ Phase 1.5 (`debug_break_on_next` для IIS-pre-existing-rphost) FAILED — `setBreakOnNextStatement` применяется только к attached targets, root cause RDBG-протокола (см. §10 + §11 research follow-up).
**Приоритет:** Средний
**Связано:** [`260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md`](260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md), [`16.7_Autonomous_Debug_Workflow.md`](../framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.7_Autonomous_Debug_Workflow.md), [cache `dbgs-rdbg-debug-server.md`](../../.claude/skills/1c-doc-research/cache/dbgs-rdbg-debug-server.md)

---

## 0. Status Dashboard (updated 2026-05-09)

| Phase | Items | Effort | Status | Closure |
|---|---|---|---|---|
| **P0 §2** Reverse-engineering RDBG sequence | 4 sub-items | 3-4ч | ✅ DONE (2.1+2.2 yukon39 source); 2.3+2.4 covered indirectly | submodule `b541b2c` |
| **P1 §3** Implement post-fire handshake | 3 sub-items | 2-3ч | ✅ DONE — _ping_loop + _handle_command + _ensure_target_attached + last_stopped_target_id | submodule `b541b2c` |
| **P2 §4** Stabilize variables/eval/step | 4 sub-items | 2-3ч | ✅ DONE — 4.2 step.Continue resume; 4.3 maxTextSize=4096 + viewInterface; 4.4 3 diagnostic tools (`debug_get_breakpoints`/`debug_attach_targets`/`debug_target_state`) | submodule `b541b2c` + new commit |
| **P3 §5** Tests + docs | 3 sub-items | 1-2ч | ✅ DONE — 74 unit tests (PASS), smoke runner (probe-only validated), 4 doc files updated | submodule `4046c4e` + new commit |
| **§6** Open questions | 4 items | — | 6.1 ✅ version param добавлен; 6.2 ✅ targetStarted auto-attach; 6.3 ✅ stale session cleanup на startup; 6.4 deferred (отдельный roadmap) | new commit |
| **TOTAL** | ~14 sub-items + 4 open Q | 8-12ч | ✅ Code-only closure complete | 1099 lines wrapper (671→1099, +428) |

**Validation results 2026-05-10 (live thin client scenario, ИБTransportManagementDevelop, `Документ.гкс_ЛабораторныйАнализ` ObjectModule:141):**

| P1 Acceptance criterion | Result |
|---|---|
| `debug_variables` returns ≥1 var | ✅ 3 переменных (Отказ=Ложь Булево, РежимПроведения=Неоперативный, ДопПараметры=Неопределено) — auto-discovery через BSL-source parser, mode=`auto`. Explicit mode тоже OK. |
| `debug_stack_trace` returns ≥1 frame | ✅ 1 frame, lineNo=141, moduleID matches BP target |
| `debug_evaluate("ТекущаяДатаСеанса()")` | ✅ `Дата 2026-05-10T15:27:03`, evalResultState=correctly |
| `debug_evaluate("Ссылка")` composite | ✅ `ДокументСсылка.гкс_ЛабораторныйАнализ`, presentation «Лабораторный анализ СоУТ-000001 от 13.03.2025 10:52:26», isExpandable=true |
| `debug_evaluate("ЭтотОбъект.Номер + … + Проведен")` composite Строка | ✅ «СоУТ-000001 / 13.03.2025 10:52:26 / Проведен=Да» |
| `debug_step("Step")` over | ✅ line 141 → 142, потом StopOnNextLine |
| `debug_step("Continue")` resume | ✅ state=Worked, документ провёлся |
| 260510 «UI+ - часть отладки не зарегистрирована» eval-bug | ✅ **НЕ репродьюсится** для thin client сценария |

**Phase 1.5 acceptance (`debug_break_on_next` для pre-existing IIS rphost) — ❌ FAILED 2026-05-10:**

| Шаг | Результат |
|---|---|
| `debug_connect` без 1cv8c.exe (только pre-existing rphost pid 39460) | OK, fully_registered=true, **`targets=[]`** |
| `debug_break_on_next` armed | HTTP 200 |
| Trigger через `1c-mcp-crud post_document(dry_run=true)` | success <1с, `events=[], targets=[]` ❌ |
| Trigger через `1c-mcp-crud execute_code` (50K-iter loop с `Сообщить`) | success ~3с, `events=[], targets=[]` ❌ |

Empirical conclusion: `setBreakOnNextStatement` (yukon39 [HTTPDebugClient.java:262-271](https://github.com/yukon39/bsl-debug-server/blob/master/src/main/java/com/github/yukon39/bsl/debugserver/httpDebug/HTTPDebugClient.java#L262)) применяется RDBG **только к attached targets** — для pre-existing rphost'а chicken-and-egg сохраняется. Root cause + workaround paths — см. §11.

### Real-world finding 2026-05-09 — P1.2 fix insufficient

Live BP-fire validation (`Документ.гкс_ЛабораторныйАнализ:141`) показала что **P1.2 «re-attach в tools перед запросом» НЕ закрывает race window**. После BP fire (`state: StopOnNextLine` confirmed) все eval/step вызовы возвращают HTTP 400 «UI+ - часть отладки не зарегистрирована», даже после force re-attach через `attach_debug_targets`. P2.1 entry-line empty-array — symptom того же registration loss bug, не отдельная проблема.

**Open follow-up:** [`260510_ROADMAP_BSL_DEBUG_RACE_WINDOW_DEEP_FIX.md`](260510_ROADMAP_BSL_DEBUG_RACE_WINDOW_DEEP_FIX.md) — wire capture от EDT для определения missing RDBG calls в post-fire sequence. До его закрытия wrapper полезен только для BP set + target tracking + visual stop indication; для productive eval/step требуется EDT.

---

## 10. Real-world finding 2026-05-10 — pre-existing rphost invisible (Phase 1.5 follow-up)

При попытке P1 acceptance validation через `1c-mcp-crud post_document` (IIS-based scenario) обнаружен **новый failure mode**, более ранний по pipeline чем 260510 eval-registration bug:

### Симптомы
1. ✅ `debug_connect(IBTransportManagementDevelop)` → fully_registered, session_id resolved
2. ✅ `debug_set_breakpoint(ObjectModule, line=141, ...)` → BP successfully registered, `debug_get_breakpoints` подтверждает
3. ✅ `debug_targets()` на момент connect → `[]` (empty, no rphost attached)
4. ✅ `1c-mcp-crud post_document` (через IIS `/hs/mcp/rpc` → rphost) → **HTTP 200 за 0.8с**, документ проведён, **BP НЕ fire**
5. ✅ `debug_ping()` → `events: []` (zero `targetStarted` event для rphost-MCP)
6. ✅ `debug_targets()` после post → всё ещё `[]`

### Root cause
- `getDbgAllTargetStates` (RDBG endpoint) возвращает **только attached к нашей debug UI session targets**
- Pre-existing rphosts (alive ДО `debug_connect`) **не emit'ят `targetStarted`** при subsequent активности — событие фигурирует только при первом spawn'е процесса
- BPs регистрируются на уровне dbgs.exe, но **доставляются ТОЛЬКО attached targets**
- Итог: для типичного IIS-extension сценария (1c-mcp-crud, любая HTTP service публикация в существующем rphost) BP set'ы **молчат**

Это распространяется на **любые long-running rphost'ы**: фоновые задания, регламентные операции, веб-клиентские сессии, активные до debug_connect. По сути, wrapper до сих пор работал только для freshly-spawned rphosts (что бывает редко в production-like окружении).

### Fix (committed 2026-05-10)
- **`RDBGClient.set_break_on_next_statement()`** — yukon39 mirror `HTTPDebugClient.setBreakOnNextStatement` (Java line 262)
- **`debug_break_on_next` MCP tool** — после armed, RDBG ставит «break on next statement» **глобально на всех eligible targets** (включая pre-existing!)
- Workflow:
  1. `debug_connect(...)` + `debug_set_breakpoint(...)` (precise BP)
  2. `debug_break_on_next()` — armed
  3. Trigger any BSL execution на rphost (e.g., post_document)
  4. Wrapper auto-attaches rphost когда тот break'нется на next statement → captured as stopped target
  5. `debug_step("Continue")` — выходит из break point, продолжает execution → достигает precise BP → stops
  6. Standard inspect path: `debug_stack_trace`, `debug_variables`, `debug_evaluate`, `debug_step`

### Acceptance criteria Phase 1.5
- [x] `RDBGClient.set_break_on_next_statement()` реализован
- [x] `debug_break_on_next` MCP tool зарегистрирован
- [x] 78 unit-тестов pass (no regression)
- [x] **Real validation 2026-05-10:** ❌ **FAILED** — `setBreakOnNextStatement` НЕ catches pre-existing IIS rphost. Подтверждено двумя триггерами: `post_document(dry_run=true)` <1с success без events; `execute_code` 50K-iter loop ~3с success без events. Wrapper continues to see `targets=[], events=[]` после armed break_on_next.

### Affects
- Phase 1.5 fix технически реализован, но НЕ закрывает заявленную цель (§10 «pre-existing rphost invisible» для IIS-сценария). Wrapper полезен для thin-client workflow (валидирован — см. §0), но не для 1c-mcp-crud / IIS HTTP-service triggers.
- Roadmap 260510 «UI+ eval-registration bug» — на thin client сценарии 2026-05-10 НЕ воспроизвёлся; eval/variables/step возвращают `correctly`. До отдельного контр-примера 260510 можно считать closed (см. §0 validation results).
- Полный набор кандидатных решений для §10 — добавлен в §11 ниже (research follow-up 2026-05-10).

---

## 1. Контекст

### 1.1 Что есть (текущее состояние, 2026-05-08)

| Компонент wrapper'а | Status | Источник правки |
|---|---|---|
| `MODULE_PROPERTY_IDS` magic UUIDs (CommonModule, ManagerModule, ObjectModule, FormModule, CommandModule, RecordSetModule) | ✅ | reverse-engineered из [yukon39 ModulePropertyId.java](https://github.com/yukon39/bsl-debug-server/blob/master/src/main/java/com/github/yukon39/bsl/debugserver/context/ModulePropertyId.java) |
| Auto-resolve propertyID при пустом/zero value в `debug_set_breakpoint` | ✅ | session 2026-05-08 |
| `attach_debug_targets` для **всех** running targets в `debug_connect` | ✅ | критично — без этого BPs не доставляются |
| Background `_ping_loop` каждые 2с, отмена в `detach()` | ✅ | предотвращает RDBG session GC после ~30-60с idle |
| 400-error body logging в `_post()` | ✅ | surfacing RDBG-сообщений в exception |

**Окружение настроено:**
- 1С Server Agent service `binPath` содержит `-debug -http` (через [`enable-1c-server-debug-http.cmd`](../../scripts/enable-1c-server-debug-http.cmd))
- `dbgs.exe` слушает `:1550` (auto-spawn ragent'ом)
- 1cv8c.exe запускается с `/Debug /DebuggerURL "http://localhost:1550"` через [`start-onec-autonomous-debug.ps1`](../../scripts/start-onec-autonomous-debug.ps1)

**Доказательства работающей части (3 успешных воспроизведения 2026-05-08):**
- ✅ `debug_connect` → `result: registered`, `fully_registered: true`
- ✅ `debug_set_breakpoint` с magic UUID — RDBG возвращает 200 OK, BP регистрируется
- ✅ Trigger BP-fire через провести ЛА → target → `state: StopOnNextLine`, окно 1С зависает
- ✅ `debug_targets` возвращает `stopped_target` UUID
- ✅ `debug_step("Continue")` на **running** target отвечает корректно

### 1.2 Что НЕ работает (задача данного roadmap)

После того как BP fired и target в `StopOnNextLine`:

| Tool | Симптом | RDBG-ошибка |
|---|---|---|
| `debug_stack_trace` | Тихо падает / возвращает stale stack от первого hit | `getCallStack` 400 / target_id mismatch |
| `debug_variables(stack_level=0)` | Возвращает `variables: []` или 400 | `evalLocalVariables` 400 «UI+ - часть отладки не зарегистрирована» / «Предмет отладки не зарегистрирован» |
| `debug_evaluate(expression)` | Сразу 400 | `evalExpr` 400 «UI+ не зарегистрирована» |
| `debug_step("Continue")` после BP-fire | 400 | `step` 400 «Предмет отладки не зарегистрирован» |

**Ключевое:** до BP-fire (target Worked) все эти tools работают. После fire — silent detach/state-loss.

### 1.3 Гипотеза (требует подтверждения в P0)

После доставки stop-event RDBG **отсоединяет target от Debug UI session**. Чтобы продолжить, Debug UI должен:
1. Получить notification через `pingDebugUIParams` о состоянии target
2. Заново вызвать `attachDetachDbgTargets` для остановленного target (`attach=true`)
3. Только после этого RDBG позволит `evalLocalVariables` / `evalExpr` / `step`

Точная последовательность в нашем wrapper'е НЕ реализована.

---

## 2. P0 — Reverse-engineering RDBG sequence (3-4ч)

**Цель:** определить точную последовательность RDBG-команд между BP-fire и успешным `evalLocalVariables`.

### 2.1 Изучить yukon39/bsl-debug-server post-BP flow

- Прочитать `DebugAgentService.java` и debug-event handlers в [yukon39 source tree](https://github.com/yukon39/bsl-debug-server)
- Найти где обрабатываются stop-events / breakpoint-hit events
- Определить какие RDBG-команды yukon39 шлёт в ответ на stop-event:
  - `getDbgTargetState`?
  - `attachDetachDbgTargets` с `attach=true`?
  - `onDebugTargetEvent` / `onTargetStarted` / etc.?

**Output:** документ `cache/dbgs-rdbg-debug-server.md` §13 «Post-BP-fire handshake» с точной sequence.

### 2.2 Изучить связанные RDBG requests

В [yukon39 source tree](https://api.github.com/repos/yukon39/bsl-debug-server/git/trees/master?recursive=1) есть:
- `RDBGCheckTerminateAbilityRequest` / Response
- `RDBGGetDbgTargetStateRequest` / Response
- `RDBGGetDbgAllTargetStatesRequest` / Response

Прочитать структуру, понять semantics (когда вызываются, что возвращают).

### 2.3 Захватить реальный wire-traffic от EDT

- Запустить EDT с активной debug-сессией
- mitm-proxy / wireshark / tcpdump на :1550
- Провести документ → захватить XML-запросы EDT → dbgs.exe
- Сравнить с нашей последовательностью

### 2.4 Изучить опубликованные XSD-схемы протокола

Платформа 1С публикует XSD на v8.1c.ru. Проверить:
- `debugRDBGRequestResponse.xsd`
- `debugBaseData.xsd`
- `debugCalculations.xsd`

Из XSD понять обязательные поля в `RDBGEvalLocalVariablesRequest` / `RDBGEvalExprRequest` после stop-event. Особенно `BSLModuleIdInternal.version` (configVersion) — возможно требуется match.

**Acceptance criteria P0:**
- [ ] Известна точная последовательность команд от stop-event до успешного `evalLocalVariables`
- [ ] Зафиксирована в cache/dbgs-rdbg-debug-server.md §13
- [ ] (Опционально) есть captured wire-traffic примеры от EDT

---

## 3. P1 — Implement post-fire handshake (2-3ч)

### 3.1 Добавить event-loop обработчик stop-events

В `RDBGClient` ввести фоновую задачу `_event_loop` (параллельно с `_ping_loop` или интегрированно). Псевдокод:

```python
async def _event_loop(self) -> None:
    """Listen for stop-events via pingDebugUIParams, handle re-attach."""
    while self._attached and self._registered:
        await asyncio.sleep(0.5)
        try:
            events = await self.ping()
            for ev in events:
                if ev.get("type") == "TargetStopped":
                    await self.attach_debug_targets([ev["target_id"]])
                    self._stopped_targets.add(ev["target_id"])
        except Exception as e:
            log.debug("event_loop ping failed: %s", e)
```

Поля:
- `_stopped_targets: set[str]` — отслеживает текущие stopped-targets
- `last_stopped_target_id: Optional[str]` — для tools без явного target_id

### 3.2 Re-attach в tools перед запросом

`debug_variables` / `debug_evaluate` / `debug_step` перед основным запросом:
1. Target в `_stopped_targets`? Если да — `attach_debug_targets([target_id])` (idempotent)
2. Только затем `evalLocalVariables` / `evalExpr` / `step`

Защита от race window если event-loop пропустил stop-event.

### 3.3 Сохранять target_id из последнего fired BP

`last_stopped_target_id` обновляется в event-loop. Tools без явного target_id (`debug_stack_trace()`) используют его вместо `_find_stopped_target` по `state` field (который может lag).

**Acceptance criteria P1:**
- [ ] После BP-fire `debug_variables` возвращает не-пустой массив с локальными переменными
- [ ] `debug_stack_trace` возвращает stack ≥1 frame
- [ ] `debug_evaluate("ТекущаяДата()")` возвращает дату-время

---

## 4. P2 — Stabilize variables/eval/step (2-3ч)

### 4.1 Fix `debug_variables` empty-array bug

При stack_level=0 на entry метода (ОбработкаПроведения) возвращается `variables: []`. Возможные причины:
- Параметры ещё не bound к scope на entry-line — попробовать stack_level=1
- `evalLocalVariables` schema требует обязательное `srcCalcInfo.calcItem` (не только `stackLevel`)
- Нужен правильный `expressionResultID` (UUID, не пустая строка)

Проверить через P0.3 wire-capture.

### 4.2 Fix `debug_step("Continue")` resume семантику

После BP-fire `Continue` должен:
1. Re-attach target (см. §3.2)
2. Отправить `step` action=Continue
3. Дождаться через event-loop события «target Worked»
4. Удалить target из `_stopped_targets`

### 4.3 Fix `debug_evaluate` для composite types

Для сложных типов (СправочникСсылка, ДокументСсылка, Структура) RDBG требует:
- `presOptions` с `maxTextSize` ≥ 4096
- `srcCalcInfo.calcItem.expression` правильно escape'нутая строка
- Возможно `viewInterface` для пользовательских presentation

### 4.4 Add diagnostic tools

Полезные tools для troubleshooting:
- `debug_get_breakpoints()` — `RDBGGetBreakpointsRequest`, читает зарегистрированные BPs (верификация что set_breakpoint реально применился)
- `debug_attach_targets(target_ids: list)` — explicit re-attach
- `debug_target_state(target_id)` — `RDBGGetDbgTargetStateRequest` для одного target

**Acceptance criteria P2:**
- [ ] `debug_step("Continue")` после BP-fire реально продолжает выполнение
- [ ] `debug_evaluate("ЭтотОбъект.Ссылка")` возвращает форматированную ссылку
- [ ] `debug_get_breakpoints()` показывает registered BPs

---

## 5. P3 — Tests + docs (1-2ч)

### 5.1 Unit-тесты wrapper'а

Создать `tools/bsl-debug-server/tests/test_mcp_debug_server.py`:
- Mock RDBG-сервера (httpx_mock или responses)
- Тесты для каждого tool: connect, set_breakpoint, stack_trace, variables, evaluate, step, disconnect
- Edge cases: zero UUID auto-resolve, attach race condition, session GC

### 5.2 Integration smoke test

`scripts/smoke_test_debug_pipeline.py`:
- Запустить dbgs.exe + 1cv8c с /Debug
- debug_connect → set BP → trigger fire → читать variables → step Continue
- exit-code 0 если успех, ≥1 если fail

### 5.3 Update docs

- **SKILL.md `implement-1c-task` Этап 4** — опция использования runtime debug через MCP, когда подходит (циклы / state machine), когда нет (простой SQL)
- **`16.7_Autonomous_Debug_Workflow.md` §16.7.10** — full example post-BP-fire flow с MCP-вызовами + troubleshooting checklist

**Acceptance criteria P3:**
- [ ] Tests pass: `pytest tools/bsl-debug-server/tests/`
- [ ] Smoke test exit 0
- [ ] Документация описывает full post-BP-fire flow

---

## 6. Открытые вопросы

1. **configVersion mismatch.** RDBG может silently дропать BPs если `BSLModuleIdInternal.version` не совпадает с running configVersion. Сейчас wrapper не передаёт `version`. Проверить в P0.4.

2. **Multiple worker rphost'ы.** При posting документа могут spawn'иться JOB targets (фоновые задания), не attached к нашей UI session. Решение: dynamic re-attach в event-loop при появлении новых targets.

3. **Сохранение Debug UI session при /mcp reconnect.** Когда Python wrapper умирает без detach — старая session живёт в dbgs.exe до GC (~60с) → новый wrapper попадает на `ibInDebug`. Workaround сейчас — kill dbgs.exe. Идея: на startup wrapper'а сначала вызвать `getDebugID` + `detachDebugUI` для всех мёртвых session'ов с тем же `infobaseAlias`.

4. **Scenario B автоматизация для CI.** Можно ли в `scripts/run_va_bdd.ps1` интегрировать автоматический fire BP на критичной строке + захват variables в JSON для regression-тестов? Open-ended — отдельный roadmap если будет potreby.

---

## 7. Ссылки

- [yukon39/bsl-debug-server](https://github.com/yukon39/bsl-debug-server) — Java DAP-implementation, эталон XML-форматов
- [yukon39/vsc-bsl-dap](https://github.com/yukon39/vsc-bsl-dap) — VS Code DAP-плагин (примеры event handling)
- [edt.1c.ru — RDBG API reference](https://edt.1c.ru/dev/edt/2022.2/apidocs/com/_1c/g5/v8/dt/debug/model/rdbg/request/response/) — список команд протокола
- [`tools/bsl-debug-server/mcp_debug_server.py`](../../tools/bsl-debug-server/mcp_debug_server.py) — наш wrapper (~700 строк после правок 2026-05-08)
- [`cache/dbgs-rdbg-debug-server.md`](../../.claude/skills/1c-doc-research/cache/dbgs-rdbg-debug-server.md) — research findings (12 разделов, magic UUIDs, scenarios B1/B2/B3)
- [`16.7_Autonomous_Debug_Workflow.md`](../framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.7_Autonomous_Debug_Workflow.md) — operational guide для Scenario B

---

## 8. Решение пользователя

Начинать сейчас или после закрытия GKSTCPLK-2468 через Path B (SQL diagnostic)?

**Рекомендация:** Path B (SQL diagnostic) сначала — даёт ответ по реальной задаче за минуты. Этот roadmap — параллельный track для улучшения dev-tooling, не блокер production-работы.

---

## 11. Research follow-up 2026-05-10 — решения для §10 (IIS pre-existing rphost capture)

После провала Phase 1.5 запущено двойное исследование (GitHub yukon39/EDT/Coverage41C + ITS/Infostart/блоги) для поиска корня и кандидатных решений. Полное содержание агентских отчётов сохранено в conversation log; здесь — синтез.

### 11.1 Root cause (подтверждён двумя независимыми путями)

**RDBG-команды протокола работают по lifecycle модели:**

1. `attachDebugUI` создаёт debug session в dbgs.exe
2. `setAutoAttachSettings(targetTypes=[Server, HTTPService, JOB], areaNames=[<infobase>])` ПУШИТ фильтр в dbgs (yukon39 [HTTPDebugClient.java:174-185](https://github.com/yukon39/bsl-debug-server/blob/master/src/main/java/com/github/yukon39/bsl/debugserver/httpDebug/HTTPDebugClient.java#L174))
3. dbgs распространяет фильтр **только тем rphost'ам, которые зарегистрируются ПОСЛЕ этого момента** (rphost reads filter on startup, не retroactively)
4. Когда новый rphost spawn'ится — он fire'т `DBGUIExtCmdInfoStarted` event → ping-loop wrapper'а ловит → `attachDebugTarget(targetId)` → target attached
5. `setBreakOnNextStatement` ставит break-flag для **уже attached targets** ([HTTPDebugClient.java:262-271](https://github.com/yukon39/bsl-debug-server/blob/master/src/main/java/com/github/yukon39/bsl/debugserver/httpDebug/HTTPDebugClient.java#L262)) — pre-existing rphost не attached, флаг ему не доходит

**Подтверждения root cause:**
- Yukon39 source: `getDbgAllTargetStates` (HTTPDebugClient.java:226-237) возвращает state только для attached targets; `attachDetachDbgTargets` (HTTPDebugClient.java:190-202) принимает explicit IDs (нет wildcard / PID mode)
- ITS / EDT docs: «среда должна сначала подключиться к серверу отладки и получить от него необходимую информацию» — auto-attach работает только для **subsequently-spawned** targets ([its.1c.ru/edtdoc t000068](https://its.1c.ru/db/content/edtdoc/src/topics/t000068.html))
- `[1c-syntax/Coverage41C](https://github.com/1c-syntax/Coverage41C)` flag `--autoconnectTargets` помечен как «not for general use» — даже коммьюнити-проекты избегают надёжного решения через RDBG
- Issue tracker `yukon39/bsl-debug-server` пуст по этой теме (#8, #9 не релевантны) — это не баг wrapper'а, а контрактное ограничение протокола

**Что НЕ работает (опровергнутые попытки):**
- ❌ `setBreakOnNextStatement` без attached targets — silent no-op (наша Phase 1.5)
- ❌ Любая попытка retroactive attach pre-existing rphost'а — RDBG протокол не предоставляет API
- ❌ Wildcard / PID-based attach — не существует в yukon39 / EDT / vsc-bsl-dap

### 11.2 Sanctioned solutions (от вендора и сообщества)

**Solution A — Force-recycle rphost (lowest effort, highest reliability).** ITS-санкционированный путь.
- Запустить wrapper с `setAutoAttachSettings(targetTypes=[HTTPService, BackgroundJob, Server], areaNames=[<alias>])` сразу после `attachDebugUI`
- OS-level kill pre-existing rphost: `taskkill /pid <pre_existing_rphost_pid>` ИЛИ Console кластера → «Выключить» с graceful drain ([efsol.ru](https://efsol.ru/manuals/1c-server-rphost-process-restart/))
- Альтернатива через `rac process shutdown --cluster=<UUID> --process=<UUID>` (сообщество, не в индексированной ITS-доке; через wrapper [arkuznetsov/irac](https://github.com/arkuznetsov/irac))
- Ragent spawn'ит fresh rphost → читает фильтр на регистрации → fire'т `DBGUIExtCmdInfoStarted` → wrapper auto-attach'ит → BPs работают
- **Risk:** active sessions в pre-existing rphost'е разорвутся (но Console кластера передаёт их другому процессу — менее invasive чем taskkill)
- **Effort:** ~4-6ч (Python wrapper для PID detect + taskkill/rac call + integration в `debug_connect`)

**Solution B — Preflight gate (lowest UX surprise).** Вместо тихого падения — явная ошибка.
- В `debug_connect`: detect pre-existing rphosts через `Get-Process rphost`
- Если есть — return error: `"rphost {pid} already running before debug_connect — RDBG protocol cannot retroactively attach. Solutions: (1) restart 1C Server Agent, (2) kill rphost via Console кластера, (3) use --force-restart flag"`
- **Effort:** ~1-2ч
- **Trade-off:** не решает проблему, только говорит правду — но честнее текущего silent failure

**Solution C — Pre-launch thin client workflow (already validated 2026-05-10).** Workflow-level path, без правок wrapper'а.
- `start-onec-autonomous-debug.ps1` запускает 1cv8c.exe с `/Debug /DebuggerURL` ДО любых действий
- Debug session attached к thin client rphost'у автоматически
- Triggers через тонкого клиента (UI: «Провести», открыть форму) → BPs работают
- **Validated empirically сегодня** (см. §0 Validation results table)
- **Limitation:** не решает 1c-mcp-crud / IIS path; но для большинства dev-сценариев достаточно

### 11.3 Recommended path

**Combo A + B:** Solution B (preflight gate) сразу — minimal effort, честный UX. Solution A (auto-recycle) — отдельным roadmap'ом, опционально через флаг `debug_connect(force_recycle_rphost=true)`. Solution C — обновить документацию ([16.7_Autonomous_Debug_Workflow.md](../framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.7_Autonomous_Debug_Workflow.md)) как preferred workflow для dev.

**Не рекомендуется:**
- Coverage41C-style probe loop — fragile, depends on platform internals
- Доработки самого `setBreakOnNextStatement` — не решит проблему, ограничение в RDBG-протоколе

### 11.4 Полный список источников

**GitHub:**
- [yukon39/bsl-debug-server](https://github.com/yukon39/bsl-debug-server) — Java reference impl, эталон XML-форматов
- [yukon39/bsl-debug-server/HTTPDebugClient.java](https://github.com/yukon39/bsl-debug-server/blob/master/src/main/java/com/github/yukon39/bsl/debugserver/httpDebug/HTTPDebugClient.java) — lines 174-185 (setAutoAttachSettings), 190-202 (attachDetachDbgTargets), 226-237 (getDbgAllTargetStates), 262-271 (setBreakOnNextStatement)
- [yukon39/bsl-debug-server/ServerContext.java](https://github.com/yukon39/bsl-debug-server/blob/master/src/main/java/com/github/yukon39/bsl/debugserver/context/ServerContext.java) — lines 230-239 `debugTargetStarted` handler
- [yukon39/vsc-bsl-dap](https://github.com/yukon39/vsc-bsl-dap) — VSCode DAP, тот же базовый стек, та же limitation
- [1c-syntax/Coverage41C](https://github.com/1c-syntax/Coverage41C) — `--autoconnectTargets` flag (fragile, по README)
- [arkuznetsov/irac](https://github.com/arkuznetsov/irac) — OScript wrapper над RAC

**ITS (1С официально):**
- [Подключение предметов отладки — t000068](https://its.1c.ru/db/content/edtdoc/src/topics/t000068.html) — auto-attach фильтры EDT
- [Настройка отладки — 10421](https://its.1c.ru/db/edtdoc/content/10421/hdoc)
- [Подключение к серверу отладки через https — i8105973](https://its.1c.ru/db/content/metod8dev/src/developers/scalability/instructions/i8105973.htm)
- [Создание и отладка HTTP-сервисов — metod8dev/5756](https://its.1c.ru/db/metod8dev/content/5756/hdoc)
- [Глава 32. Отладка — v8321doc TI000001030](https://its.1c.ru/db/v8321doc/bookmark/dev/TI000001030)

**Сообщество и блоги:**
- [Wonderland: новый механизм отладки](https://wonderland.v8.1c.ru/blog/novyy-mekhanizm-otladki/)
- [Перезапуск rphost — efsol.ru](https://efsol.ru/manuals/1c-server-rphost-process-restart/) — Console кластера workflow
- [Отладка по HTTP/TCP-IP — 1c-programmer-blog.ru](https://1c-programmer-blog.ru/platforma/otladka-po-protokolam-http-i-tcp-ip-v-1s.html)
- [Включение отладки веб- и HTTP-сервисов — koderline.ru](https://www.koderline.ru/expert/narabotki/article-vklyuchenie-otladki-dlya-veb-i-http-servisov-v-1s-prosvechivaem-chernyy-yashchik/)
- [Базовые настройки механизма отладки — infostart.ru/1133240](https://infostart.ru/1c/articles/1133240/)
- [Отладка HTTP-сервисов в файловой базе — infostart.ru/1885817](https://infostart.ru/1c/articles/1885817/)
- [Не работает отладка — 1s-on.ru](https://1s-on.ru/ne-rabotaet-otladka-1s/)
- [HTTPService debug — 1c-dn.com forum 2025](https://1c-dn.com/forum/forum1/topic2025/)
- [Отладка тонкий клиент + веб-сервер — forum.infostart.ru/topic292879](https://forum.infostart.ru/forum9/topic292879/)

### 11.5 Open follow-up tasks

- [ ] Создать отдельный roadmap `260511_ROADMAP_BSL_DEBUG_RPHOST_AUTO_RECYCLE.md` для Solution A (force-recycle) с phased plan: preflight gate (B) → флаг force_recycle (A) → docs update (C)
- [ ] Closed: Roadmap [260510_ROADMAP_BSL_DEBUG_RACE_WINDOW_DEEP_FIX.md](260510_ROADMAP_BSL_DEBUG_RACE_WINDOW_DEEP_FIX.md) — сегодняшняя thin-client validation показала что eval-registration bug не воспроизвёлся; либо был артефактом старого scenario, либо фикс P1.2 покрыл. Контекст для possible reopen: документ `гкс_ЛабораторныйАнализ:141` ObjectModule, runID = thin client `d.sokolov@sodru.com` session `e3f71a05-b168-4273-b71d-5bf5caf4c201`
