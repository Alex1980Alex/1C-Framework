# Этап 1 — Планирование архитектуры

**Задача:** сделать 4-этапный пайплайн (ADR-017) обязательной self-driven парадигмой работы Claude.

## Проблема
ADR-017 — пайплайн opt-in (человек запускает `/pl-plan…`). Нужно: Claude **сам** ведёт этапы,
mandatory, enforced; охват — все задачи; жёсткость — hard-block (выбор пользователя 2026-06-13).

## Исследование `[exp]`
- Прецедент mandatory-инъекции + Write-gate: `task-protocol-enforcer` (инъектит «TASK PROTOCOL»).
- Прецедент hard-Stop-block: `approval-gate.py`, `task-enforcer.py`, `docs-change-enforcer.py`.
- Сигнал «была задача»: `data/hook-invocations.jsonl` пишет `tool`+`session` на каждый хук-вызов
  → Write/Edit за сессию = факт правки. `SessionState` хранит classification.

## Рекомендация
Два хука: **UPS-инъектор** (mandatory-инструкция) + **Stop-enforcer** (hard-block, если были
Write/Edit без использования пайплайна за сессию). Глубина артефактов масштабируется
(trivial→`pipeline.md`; medium/complex→`01..04`+approval). Обязательный carve-out: чистые
вопросы без Write — exempt (иначе deadlock). Safety: opt-out env + graceful degradation.

## Риски / Откат
Риск ложных блокировок (hard с 1-го дня) → митигирован Write-gating + opt-out + достижимым
выходом. Откат = снять 2 записи из `settings.json`.

## ADR
[ADR-018](../../.claude/skills/architecture-research/adr/018-mandatory-auto-pipeline-protocol.md)
(расширяет ADR-017). Решение принято и одобрено пользователем (выбор охвата/жёсткости).
