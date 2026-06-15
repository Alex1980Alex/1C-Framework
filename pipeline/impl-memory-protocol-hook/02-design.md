# Дизайн

**`memory-protocol-stop.py`** (Stop, timeout 8s, opt-out `MEMORY_PROTOCOL_DISABLE=1`):
1. `_session_start(sid)` — ранний ts сессии из invocation-лога.
2. `_onec_task_this_session(start)` — pipeline с title `startswith("1С-задача (")`, updated_at ≥ start.
   start=None / нет → False (conservative, без ложного блока).
3. `_memory_signals(transcript)` — по фактическим tool_use (рекурсивный `_iter_tool_uses`):
   recall = `unified_search` / `search_patterns` / `list_patterns`; capture = `capture_pattern` /
   `batch_capture` / `route_and_save` ИЛИ Write/Edit в `memory/*.md`.
4. Если 1С-задача И (recall или capture отсутствует) → **block** с actionable-сообщением (что вызвать) + opt-out.
   Иначе/не-1С/ошибка → allow (graceful, exit 0).

**Регистрация:** Stop-цепочка в `settings.json` сразу ПОСЛЕ `pipeline-protocol-stop` (тот сперва форсит пайплайн).
**Реверс:** удалить запись из settings.json + файл хука.
**Анти-deadlock:** opt-out env; 1C-сигнал keyed на текущую сессию; graceful exit 0 на ошибке; выход достижим
(вызвать unified_search + capture_pattern). Паттерн зеркалит проверенный roadmap-progress-enforcer.

**Статус: approved (оператор).**
