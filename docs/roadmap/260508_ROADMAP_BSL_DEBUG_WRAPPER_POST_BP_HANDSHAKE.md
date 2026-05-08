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
