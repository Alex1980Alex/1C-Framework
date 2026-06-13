# ADR-018: Обязательная авто-пайплайн парадигма — self-driven, hard-block для всех задач

**Дата:** 2026-06-13
**Статус:** accepted (реализовано+smoke-verified 2026-06-13)
**Исследование:** ../cache/sdlc-pipeline-orchestration-patterns.md
**Расширяет:** [ADR-017](017-generic-4stage-pipeline-slash-state.md) (human-driven opt-in → auto-mandatory)
**Шаг SDLC:** сквозной (мета — как Claude работает над задачами)

## Контекст
ADR-017 сделал 4-этапный пайплайн **opt-in**: человек вручную запускает `/pl-plan…`.
Пользователь требует, чтобы это была **обязательная парадигма работы самого Claude**: при
решении задач Claude **сам** ведёт этапы (не дожидаясь слэш-команд), в **mandatory**-режиме,
enforced хуком. Явный выбор пользователя (2026-06-13): **охват = ВСЕ задачи (вкл. trivial)**,
**жёсткость = hard-block сразу** (не фазовый rollout).

## Решение
- **UPS-инъектор** [`pipeline-protocol.py`](../../../../.claude/hooks/pipeline-protocol.py): на каждый
  промпт инъектит mandatory-инструкцию вести задачи с правкой кода через `pipeline/<slug>/`. [own]
- **Stop-enforcer** [`pipeline-protocol-stop.py`](../../../../.claude/hooks/pipeline-protocol-stop.py):
  **hard-block** завершения, если в сессии были Write/Edit (сигнал «была задача» из invocation-лога)
  БЕЗ использования пайплайна (ни один `.pipeline-state.json` не обновлён за сессию). Аналог
  `approval-gate.py`/`task-enforcer.py`. [exp]
- **Охват = все задачи с правкой кода, вкл. trivial** (выбор пользователя). Глубина артефактов
  масштабируется: trivial → один компактный `pipeline.md` (дизайн авто-одобрен); medium/complex →
  `01..04` + human approval-гейт перед кодированием (ADR-017).
- **Жёсткость = hard сразу** (выбор пользователя; НЕ фазовый advisory→hard как tdd-guard ADR-015).
- **Обязательный carve-out (не смягчение, а корректность):** чистые вопросы/ответы без Write —
  exempt. Иначе Stop-хук блокировал бы даже обычный ответ и саму возможность себя отключить
  (deadlock). Сигнал «задача» = факт Write/Edit за сессию, а не эвристика текста.
- **Safety / анти-deadlock:** opt-out `PIPELINE_PROTOCOL_DISABLE=1`; graceful degradation
  (исключение/нет session_id/нет данных → allow); выход всегда достижим (создать pipeline-артефакт
  и завершить снова). Реверс = снять 2 записи из `settings.json`.

## Последствия
**Положительные:** обязательная дисциплина «план→дизайн→код→тест» для всех задач; Claude
self-drive (не ждёт команд); постоянный audit-trail каждой задачи в `pipeline/`.
**Отрицательные:** overhead на trivial-правках (минимизирован компактным `pipeline.md`);
hard-block с 1-го дня без недели валидации повышает риск ложных блокировок (митигирован
Write-gating'ом + opt-out + достижимым выходом); отступление от безопасного фазового rollout —
**осознанный выбор пользователя**, зафиксирован здесь.

## Альтернативы
- **Фазовый advisory→hard** (паттерн tdd-guard ADR-015) — **рекомендован мной, отклонён
  пользователем** в пользу hard-immediate.
- **Охват только complex/medium** — рекомендован мной, отклонён в пользу «все вкл. trivial».
- **Advisory-only** (без Stop-block) — отклонён: «обязательность» была бы декларативной.
- **Workflow-оркестратор гонит все этапы автономно** (ADR-017 опция №3) — отложен: ломает
  чекпоинт-ревью артефакта между этапами; остаётся опцией `/pl-run-all`.

## Связанные файлы
`.claude/hooks/pipeline-protocol.py`, `.claude/hooks/pipeline-protocol-stop.py`,
`.claude/settings.json` (UPS + Stop), `.claude/hooks/shared/pipeline_state.py` (ADR-017),
`pipeline/README.md`, `CLAUDE.md` (Hooks Infrastructure).
