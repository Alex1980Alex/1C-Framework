# Roadmap — Доработка `mcp_debug_server.py` post-BP-fire handshake

**Дата:** 2026-05-08
**Статус:** 🟡 PLANNED
**Приоритет:** Средний
**Связано:** [`260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md`](260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md), [`16.7_Autonomous_Debug_Workflow.md`](../framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.7_Autonomous_Debug_Workflow.md), [cache `dbgs-rdbg-debug-server.md`](../../.claude/skills/1c-doc-research/cache/dbgs-rdbg-debug-server.md)

---

## 0. Status Dashboard

| Phase | Items | Effort | Status |
|---|---|---|---|
| **P0 §2** Reverse-engineering RDBG sequence | 4 sub-items | **3-4ч** | 🟡 PLANNED |
| **P1 §3** Implement post-fire handshake | 3 sub-items | **2-3ч** | 🟡 PLANNED |
| **P2 §4** Stabilize variables/eval/step | 4 sub-items | **2-3ч** | 🟡 PLANNED |
| **P3 §5** Tests + docs | 3 sub-items | **1-2ч** | 🟡 PLANNED |
| **TOTAL** | ~14 sub-items | **8-12ч** | 🟡 PLANNED |

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
