# Этап 3 — Кодирование

## Что изменено
- **NEW** [`pipeline-protocol.py`](../../.claude/hooks/pipeline-protocol.py) — UPS-инъектор
  (mandatory systemMessage, opt-out, пустой промпт→None).
- **NEW** [`pipeline-protocol-stop.py`](../../.claude/hooks/pipeline-protocol-stop.py) — Stop
  hard-enforcer (`had_write ∧ ¬pipeline_used_since` → block; reuse invocation-лога + `pipeline/`).
- **MOD** `.claude/settings.json` — UPS (+`pipeline-protocol.py`, timeout 3) и Stop
  (+`pipeline-protocol-stop.py`, timeout 8).
- **DOC** ADR-018 + `_index.json` (record 18) + `CLAUDE.md` (Hooks Infrastructure нота).

## Отклонения от дизайна
Нет — реализовано по `02-design.md`. Сигнал Write взят из invocation-лога (как спроектировано),
без чтения file_path (лог его не пишет) → ложные срабатывания на самих pipeline-артефактах
сняты проверкой `pipeline_used_since`.

## Для Этапа 4
Прогнать 6 Stop-кейсов + инъектор + ruff/compile + валидность settings.json + code-verify.
