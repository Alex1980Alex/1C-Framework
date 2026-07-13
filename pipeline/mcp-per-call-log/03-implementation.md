# 03 Кодирование — P2.3

- `scripts/mcp_call_log.py`: `log_mcp_call` + `track_call` (ротация os.replace, fail-soft, opt-out).
- `memory_orchestrator.py`: защитный импорт `_track_call`, `call_tool`→`_dispatch_tool`, error-ветки метят state.
- `mcp_1c_stdio_launcher.py`: `_instrument_call_tool()` монки-патч (scripts-dir на path, idempotent).
- Регрессия `src`-коллизии внесена и исправлена (см. 02-design), проверено в реальном venv сабмодуля.
