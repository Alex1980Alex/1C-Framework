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
