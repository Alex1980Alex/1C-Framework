# ADR-019: Приведение 1С-команд (/analyze-1c-task, /implement-1c-task) к generic 4-этапному пайплайну

**Дата:** 2026-06-14
**Статус:** proposed (план в roadmap, код не писался)
**Исследование:** ../cache/sdlc-pipeline-orchestration-patterns.md
**Расширяет/корректирует:** [ADR-017](017-generic-4stage-pipeline-slash-state.md) (которое объявляло 1С-цепочку «не трогаем»), [ADR-018](018-mandatory-auto-pipeline-protocol.md) (обязательная парадигма)
**Roadmap:** ../../../docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md
**Шаг SDLC:** сквозной (оркестрация 1С-домена)

## Контекст
Во фреймворке две staged-SDLC реализации, взаимно «слепые»: generic 4-этапный пайплайн
(Планирование→Дизайн→Кодирование→Тестирование, `pipeline/<slug>/.pipeline-state.json`, ADR-017/018,
**обязательный** через Stop-хук) и доменная 1С-цепочка (`/analyze-1c-task → /implement-1c-task →
/write-1c-tests → /run-1c-tests`, артефакты `ANALYSIS-REPORT.md`/`IMPLEMENTATION-PROGRESS.md`,
state `features/<task>/.run-state.json`). ADR-017 явно вынес 1С-цепочку из периметра. Пользователь
запросил обратное: 1С-команды должны выражать ту же 4-этапную концепцию. Главная боль — **G3**:
`/implement-1c-task` правит BSL, но не обновляет `.pipeline-state.json`, поэтому ADR-018
`pipeline-protocol-stop.py` hard-блокирует завершение сессии (двойная бухгалтерия). Полный разрыв-анализ
(G1–G5) и маппинг — в roadmap. [own]

## Решение
**Вариант B — мост через pipeline-state + переименовательная часть варианта A.** [own]
- В [`pipeline_state.py`](../../../../.claude/hooks/shared/pipeline_state.py) ввести **профили**:
  `default` (текущие STAGES) и `1c` (4 канонических этапа с 1С-делегатами и 1С-артефактами). `init --profile 1c`
  пишет профиль в state; gate/status/delegates его читают. Default-профиль — без изменений (дефолты == хардкод). [own]
- 1С-команды становятся первоклассным экземпляром 4-этапного пайплайна, **проводя** тот же
  `.pipeline-state.json`, НЕ переписывая богатую методику:
  - Этап 1 Планирование ← analyze Фазы 1–3; Этап 2 Дизайн ← analyze Фазы 4–5 (+опц. OpenSpec);
    Этап 3 Кодирование ← implement Этапы 0–3; Этап 4 Тестирование ← implement Этапы 4–6 + write/run-1c-tests.
  - `artifact` каждого этапа указывает на существующие `ANALYSIS-REPORT.md`/`IMPLEMENTATION-PROGRESS.md`.
- **Гейт «Дизайн→Кодирование»** для всех 1С-задач (не только SDD): Этап 2 должен быть `approved` перед
  `/implement-1c-task`. Переиспользовать паттерн [`approval-gate.py`](../../../../.claude/hooks/approval-gate.py)
  (OpenSpec-approve = одно из достаточных условий approve этапа 2). [exp]
- `.run-state.json` остаётся для детального прогона VA BDD внутри Этапа 4 (две шкалы: макро-этап vs сценарии). [own]

## Последствия
**Положительные:** снимается G3 (1С-задача проходит Stop-хук ADR-018 без ручного второго пайплайна);
единый словарь и audit-trail для 1С и не-1С задач; тривиальный 1С-маршрут получает чекпоинт одобрения дизайна
(G4); методика 1С не переписывается → низкий риск; обратимо.
**Отрицательные:** два state-файла на 1С-задачу (`.pipeline-state.json` + `.run-state.json`) — требует чёткой
доки границ ответственности; небольшой overhead проводки в 2 командах; нужно держать профиль `1c` в синхроне
с реальными фазами скиллов при их эволюции.

## Альтернативы
- **A — только документация/relabel:** дёшево, но не снимает G3/G4 (главную боль) → недостаточно, поглощено как часть B.
- **C — полный сплит команд** (analyze→2, implement→2 команды как pl-*): максимально канонично, но ломает UX,
  формат ANALYSIS-REPORT, `.run-state.json`, SDD-маршрут, доку 17.5 — высокий риск, низкая доп.ценность над B → отклонён.
- **Оставить как есть** (ADR-017 «не трогаем»): отклонён прямым запросом пользователя.

## Связанные файлы
`.claude/hooks/shared/pipeline_state.py` (профили), `.claude/commands/analyze-1c-task.md`,
`.claude/commands/implement-1c-task.md`, `.claude/skills/analyze-1c-task-v2/SKILL.md`,
`.claude/skills/implement-1c-task/SKILL.md`, `.claude/hooks/pipeline-protocol-stop.py` (ADR-018),
`.claude/hooks/approval-gate.py`, `docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md`,
`CLAUDE.md` (1С Pipeline), `docs/framework documentation/17_ТЕСТИРОВАНИЕ_1С/17.5_КОМАНДЫ_ПАЙПЛАЙНА.md`.
