# Кодирование

- **`.claude/hooks/memory-protocol-stop.py`** (новый) — Stop-энфорсер: `_session_start` (из лога) +
  `_onec_task_this_session` (title `startswith("1С-задача (")`, dt≥start) + `_memory_signals` (recall/capture
  по фактическим tool_use транскрипта; `.md`-write=capture) → block если 1С-задача без recall||capture.
  Graceful (exit 0 на ошибке/не-1С), opt-out `MEMORY_PROTOCOL_DISABLE=1`, no-sentinel by design.
- **`.claude/settings.json`** — регистрация в Stop-цепочке ПОСЛЕ `pipeline-protocol-stop` (timeout 8s).
- **`tests/unit/test_memory_protocol_stop.py`** (новый) — 9 collision-immune тестов.

Откат: снять запись из settings.json + удалить файл хука.
