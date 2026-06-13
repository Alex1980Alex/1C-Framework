# Этап 2 — Дизайн реализации

## Точки модификации
- **NEW** `.claude/hooks/pipeline-protocol.py` (UserPromptSubmit) — инъектор.
- **NEW** `.claude/hooks/pipeline-protocol-stop.py` (Stop) — hard-enforcer.
- **MOD** `.claude/settings.json` — UPS-цепочка (+injector) и Stop-цепочка (+enforcer).
- **DOC** ADR-018 + `_index.json` + `CLAUDE.md`.

## Контракты
- **Инъектор:** на любой непустой промпт → `systemMessage` с правилами пайплайна; opt-out
  `PIPELINE_PROTOCOL_DISABLE=1`; пустой промпт → None.
- **Stop-enforcer:** `gate = had_write(session) AND NOT pipeline_used_since(session_start)`.
  - `had_write` = в invocation-логе есть `event=PreToolUse, tool∈{Write,Edit,MultiEdit,NotebookEdit}, session=sid`.
  - `session_start` = мин. `ts` для sid в логе.
  - `pipeline_used_since` = любой `pipeline/*/.pipeline-state.json` с `updated_at ≥ session_start`.
  - `gate=True` → `HookOutput().block(reason)`; иначе None.
  - Деградация: нет sid / нет данных / исключение → None (allow).

## Тест-стратегия (для Этапа 4)
6 кейсов Stop: no-writes→allow; writes/no-pipeline→block; writes/pipeline-used→allow;
writes/pipeline-stale→block; opt-out→allow; no-session→allow. Инъектор: prompt→msg, empty→none.
ruff/compile clean; settings.json валиден; оба хука зарегистрированы.

## Соответствие плану
Реализует рекомендацию Этапа 1 (2 хука + carve-out + safety) и выбор пользователя
(все задачи, hard сразу). Одобрено пользователем через выбор опций (= approve).
