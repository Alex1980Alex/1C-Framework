# W5′ «Наблюдение состояния» — дизайн (C4 + C6 + A6 + A4)

Роадмап [260708 §8.4-8.7](../../docs/roadmap/260708_ROADMAP_AUTONOMOUS_1C_DEBUGGING.md). Порядок: C4 → C6 → A6 → A4 (A4 собирает C6.2 + A6.3).

Якорь: `tools/bsl-debug-server/mcp_debug_server.py` (6326 стр) + модули `snapshot.py`/`coverage.py` + новый `watchpoints.py`.

## C4 — Watchpoint / data BP (§8.4)
Новый модуль **`watchpoints.py`** зеркалит `logpoints.py`/`coverage.py` (standalone, получает `client`).
- `plan_watchpoints(source, name, method?)` → строки `name = ...` через `autonomy.find_assignment_lines` (готово).
- Гейт в `_handle_command` (после system_stops, ДО coverage/logpoint): `if getattr(self,'_watchpoints',None):` (пусто по умолчанию → 0 изменений поведения). На watch-line → `watchpoints.fire_watchpoint` (deferred create_task как logpoint): eval `{name}` → сравнить с `client._watch_last[name]` → record `{line,old,new,ts,changed}` в JSONL → решение:
  - `record_only`: всегда Continue (таймлайн изменений).
  - `break_on_first_change` / `break_when`: при changed(+predicate) — НЕ Continue, промоут в `_user_visible_stops` + `_signal_bp_stop()` (halt виден агенту); иначе Continue.
- `match_predicate(value, op, literal)` — общий компаратор (`=,<>,<,>,<=,>=`; число/строка/Истина/Ложь/Неопределено).
- Tools: `debug_set_watchpoint(name, object_id, method?, module_type, mode, break_when?)` (arm) + `debug_watchpoint_result(clear=True)` (таймлайн + teardown).
- Cap fires/line (default 200, как coverage) → `capped` в ответе.
- Гоча: bounded — halt-окно 1-2с; на held-JOB (B1) окно шире.

## C6 — Precise coverage counts + семантический replay-seek (§8.5)
- **C6.1** `coverage.export_counts_sidecar(client, xml_path)` → `<session>.counts.json` `[{file,line,count}]` + `hot_lines` top-N; `debug_coverage_export` возвращает `counts_path`+`hot_lines`. XML не трогаем.
- **C6.2** `debug_session_record(enable, capture_variables=False)` → `client._capture_variables`; `snapshot.record` при флаге дописывает bounded top-K локалей (через `client.eval_locals_auto`, cap 12) в entry. Сигнатура `record(...)` расширена опц. `variables`.
- **C6.3** `snapshot.parse_seek_query(q)` → `(name, op, literal)`; `snapshot.match_entry(entry, pred)` по variables + спец-именам `line/reason/module`; `debug_replay_seek(index=-1, query="")` — при query ищет первый match (числовой index сохранён, перегрузка).

## A6 — Session-режимы (InspectWare) + correlation_id (§8.6)
- **A6.1** `_session_state(client)` → enum `Start/Runtime-State/Runtime-Error/Post-Mortem/Done` + `_VALID_NEXT` карта имён tools; `_state_hint(client)` → `{session_state, valid_next}`.
- **A6.2** врезка `_state_hint` в ответы `connect/ping/targets/step/target_state` (остальные не трогаем).
- **A6.3** `debug_connect(correlation_id="")` (дефолт uuid4) → `client._correlation_id` → persist в `.active.json` (в `_persist_active_session`) + прошивка в logpoint JSONL / snapshot / coverage export / session_summary. Формат совместим с CloudEvents `correlationid`.

## A4 — debug_diff_runs (§8.7, самый большой)
- **A4.1** формат прогона: `debug_session_record(label=...)` + snapshot с variables (C6.2) + монотонный `stop_seq`.
- **A4.2** managed ×2 внутри tool'а — arm(capture_mode)+trigger по вызывающему НЕ кодим; вместо этого two-phase `arm/collect` для КАЖДОГО прогона: `debug_diff_runs(phase, label, watch[])`. arm ставит coverage-веер? Нет — реюз autotrace-скелета: собирать стопы через snapshot с variables. **Решение**: A4 работает поверх ДВУХ записанных snapshot-сессий (реюз `session_record` + `replay`), tool сравнивает их — вход `ok_session_id`/`fail_session_id` (+ live two-phase как enhancement). Alignment ключ `(module_fqn, line, hit_index)`; `flow_divergence` = первая позиция расхождения последовательностей; `state_diff` по watch-значениям → `first_state_divergence`.
- **A4.5** ответ `{verdict:{first_divergence:{kind:flow|state,...}}, raw:{aligned,diffs}}`; two-infobase — рецепт в SKILL, не кодим.
- Pure-хелперы `autonomy`/новый `diff_runs.py`: `align_stops`, `first_divergence` — тестируемо без RDBG.

## Тесты
`test_c4_watchpoint.py` / `test_c6_counts_seek.py` / `test_a6_session_state.py` / `test_a4_diff_runs.py` — mock client (паттерн 222 существующих). Live-harness на held-JOB (B1) — при доступном dbgs; иначе PENDING (как W1-W4 gating).

## Общие правила (§8.8): two-phase `{verdict,raw}`, teardown в finally, bounded top-N с явным усечением, новые модули → `--watch` в `.mcp.json`, code-verify субагентом.
