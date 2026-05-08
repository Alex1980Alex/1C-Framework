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
