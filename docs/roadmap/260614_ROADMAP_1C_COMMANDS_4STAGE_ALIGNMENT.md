# 260614 — Приведение /analyze-1c-task и /implement-1c-task к 4-этапной парадигме (roadmap)

> Status: **PROPOSED** (research + план; код не писался). Создан 2026-06-14 по запросу
> пользователя: «команды /analyze-1c-task и /implement-1c-task привести в соответствие
> концепции Планирование архитектуры → Дизайн реализации → Кодирование → Тестирование».
> Решение зафиксировано в [ADR-019](../../.claude/skills/architecture-research/adr/019-1c-commands-4stage-pipeline-alignment.md).
> Исследование: [sdlc-pipeline-orchestration-patterns.md](../../.claude/skills/architecture-research/cache/sdlc-pipeline-orchestration-patterns.md).

## Контекст

Во фреймворке есть **две** разные реализации staged-SDLC, которые сейчас не знают друг о друге:

1. **Generic 4-этапный пайплайн** (ADR-017/018) — домен-агностичный, **обязательный** для всех
   задач с правкой кода:
   - Этапы: **Планирование архитектуры → Дизайн реализации → Кодирование → Тестирование**.
   - Команды [`pl-plan`](../../.claude/commands/pl-plan.md)/[`pl-design`](../../.claude/commands/pl-design.md)/[`pl-code`](../../.claude/commands/pl-code.md)/[`pl-test`](../../.claude/commands/pl-test.md) → артефакты `pipeline/<slug>/0N-*.md`.
   - Состояние: `pipeline/<slug>/.pipeline-state.json` + `pipeline/CURRENT` ([`pipeline_state.py`](../../.claude/hooks/shared/pipeline_state.py), STAGES = единый источник истины).
   - Hard-гейт перед Кодированием: дизайн (02) `done`+`approved`.
   - Enforcement (ADR-018): [`pipeline-protocol.py`](../../.claude/hooks/pipeline-protocol.py) (UPS-инъектор) + [`pipeline-protocol-stop.py`](../../.claude/hooks/pipeline-protocol-stop.py) (Stop **hard-block**, если были правки кода без обновления `.pipeline-state.json` за сессию).

2. **1С-цепочка** (доменная) — [`/analyze-1c-task`](../../.claude/commands/analyze-1c-task.md) → [`/implement-1c-task`](../../.claude/commands/implement-1c-task.md) → `/write-1c-tests` → `/run-1c-tests`:
   - Артефакты: `ANALYSIS-REPORT.md` → BSL/XML + `IMPLEMENTATION-PROGRESS.md` → `.feature` + `TEST-PLAN-DETAILED.md`.
   - Состояние: `features/<task>/.run-state.json` (для VA BDD-прогона).
   - SDD-маршрут (medium/complex): analyze → `/opsx:propose` → `/opsx:approve` (hard-гейт `approval-gate.py`) → `/opsx:apply` → `brownfield-validate` → `/opsx:archive`.

**ADR-017 прямо зафиксировал:** «1С-цепочка — отдельная доменная реализация ... её не трогаем».
Запрос пользователя меняет это решение: 1С-команды должны стать выражением той же 4-этапной парадигмы.

## Текущее состояние (факты исследования)

### `/analyze-1c-task` → skill `analyze-1c-task-v2` (v4.3)
5 фаз: **1 Требования → 2 Объекты (delta-spec `[ADDED]`/`[MODIFIED]`/`[REFACTOR]`) → 2.5 Runtime Trace (опц., 1c-debug-hmr) → 3 Алгоритм → 4 План модификаций (точки `file:line`+код+зависимости) → 5 Верификация (+тест-план)**.
Read-only + единичный Write `ANALYSIS-REPORT.md` (§1–11; §11 = SDD next-steps). [docs: analyze-1c-task-v2/SKILL.md]

### `/implement-1c-task` → skill `implement-1c-task` (v2.7)
8 этапов: **0 Preflight (capability matrix) → 1 Подготовка → 2 Валидация запросов → 3 BSL write (+3R refactor) → 4 Статанализ → 5 Верификация (5.x live BP-verify, 5.y regression diff) → 6 Тест на живых данных (шаг 0 update_database) → 7 Документация → 8 Git (3-уровневые сабмодули)**.
Output `IMPLEMENTATION-PROGRESS.md`. [docs: implement-1c-task/SKILL.md]

### Маппинг «как есть» (границы НЕ совпадают с 4 этапами)

| Канонический этап | Где реализовано сейчас | Внутренние фазы/этапы |
|---|---|---|
| 1. Планирование архитектуры | `/analyze-1c-task` (часть) | Фазы 1–3 (+2.5 Trace) |
| 2. Дизайн реализации | `/analyze-1c-task` (часть) + SDD | Фаза 4 (план модификаций = дизайн) + Фаза 5 (тест-стратегия) + опц. OpenSpec propose/approve |
| 3. Кодирование | `/implement-1c-task` (часть) | Этапы 0–3 |
| 4. Тестирование | `/implement-1c-task` (часть) + `/write-1c-tests` + `/run-1c-tests` | Этапы 4–6 + VA BDD |

То есть **одна команда покрывает два канонических этапа**, а тестирование размазано по двум командам.

## Анализ разрывов (gap analysis)

1. **G1 — Границы этапов смещены.** `analyze` = Этап 1+2, `implement` = Этап 3+4. Нет явной границы
   «Планирование ↔ Дизайн» внутри analyze и «Кодирование ↔ Тестирование» внутри implement.
2. **G2 — Два словаря артефактов.** `01-architecture/02-design/03-implementation/04-testing` (generic)
   vs `ANALYSIS-REPORT/IMPLEMENTATION-PROGRESS/.feature/TEST-PLAN` (1С). Маппинг нигде не задокументирован.
3. **G3 — Нет интеграции с pipeline-state → двойная бухгалтерия (ГЛАВНАЯ боль).** 1С-команды НЕ создают/не
   обновляют `pipeline/<slug>/.pipeline-state.json`. Но ADR-018 `pipeline-protocol-stop.py` **hard-блокирует**
   завершение сессии, если были правки кода без обновлённого state. Итог: `/implement-1c-task` правит BSL →
   Stop-хук блокирует, пока вручную не создашь отдельный `pipeline/<slug>/`. Парадигма и 1С-цепочка
   взаимно «слепы».
4. **G4 — Рассинхрон гейтов одобрения.** Generic: единый hard-гейт «дизайн approved» перед Кодированием.
   1С: гейт `approval-gate.py` только на SDD-маршруте (medium/complex, на уровне спеки). Тривиальный маршрут
   `analyze → implement` **не имеет** чекпоинта одобрения дизайна — противоречит инварианту 4-этапной парадигмы.
5. **G5 — Именование.** 1С-команды говорят «анализ»/«реализация», а не каноническими терминами этапов.

## Варианты решения

- **Вариант A — только документация/переименование.** Добавить в скиллы/команды заголовки 4 этапов +
  таблицу маппинга. Дёшево, но НЕ снимает G3 (двойная бухгалтерия) и G4 (гейт) — главную боль. → недостаточно.
- **Вариант B — мост через pipeline-state (РЕКОМЕНДАЦИЯ).** Сделать 1С-команды первоклассным экземпляром
  4-этапного пайплайна: `pipeline_state.py` получает «профили» (default + `1c`); 1С-команды
  `init`/`done`/`approve` тот же `.pipeline-state.json`, но с 1С-делегатами и 1С-артефактами. Богатую 1С-методику
  НЕ переписываем — только проводим состояние. Снимает G1–G5, низкий риск, обратимо.
- **Вариант C — полный сплит команд.** Разбить analyze→(pl-plan-1c + pl-design-1c), implement→(pl-code-1c +
  pl-test-1c). Максимально «канонично», но ломает существующий UX, формат ANALYSIS-REPORT, `.run-state.json`,
  SDD-маршрут и доку 17.5. Высокий риск, низкая доп.ценность над B. → отклонён как основной.

**Рекомендация: B (мост pipeline-state) + переименовательная часть A**, переиспользуя `approval-gate.py`
как гейт «Дизайн→Кодирование». Обоснование и последствия — [ADR-019](../../.claude/skills/architecture-research/adr/019-1c-commands-4stage-pipeline-alignment.md).

## Целевой маппинг (4 этапа ↔ 1С)

| Этап | 1С-делегат | Артефакт (трекается в state) | Гейт |
|---|---|---|---|
| 1. Планирование архитектуры | `analyze-1c-task-v2` Фазы 1–3 (+2.5) | `ANALYSIS-REPORT.md` §1–3 | — |
| 2. Дизайн реализации | `analyze-1c-task-v2` Фазы 4–5 (+опц. OpenSpec) | `ANALYSIS-REPORT.md` §4–5,11 | **approve** (hard перед Этапом 3) |
| 3. Кодирование | `implement-1c-task` Этапы 0–3 | `IMPLEMENTATION-PROGRESS.md` (код) | требует Этап 2 approved |
| 4. Тестирование | `implement-1c-task` Этапы 4–6 + `/write-1c-tests` + `/run-1c-tests` | `IMPLEMENTATION-PROGRESS.md` (тесты) + `TEST-PLAN`/`.feature` | — |

`.pipeline-state.json` хранит **макро-этап** (1–4) и указывает `artifact` на богатые 1С-отчёты;
`.run-state.json` остаётся для детального VA BDD-прогона внутри Этапа 4 (две шкалы: макро vs прогон сценариев).

## План реализации (фазы)

- **Phase 0 — Research & decision.** Этот roadmap + ADR-019. ✅ (выполнено этой задачей)
- **Phase 1 — Профили в `pipeline_state.py`.** Ввести `PROFILES = {"default": STAGES, "1c": STAGES_1C}`;
  `init <slug> [--profile 1c]` пишет `profile` в state; `gate`/`render_status`/delegates читают профиль.
  Поведение default-профиля без изменений (дефолты == текущий хардкод). Регресс-тест
  `tests/unit/test_pipeline_state_profiles.py`. **DoD:** `init --profile 1c` создаёт state с 1С-этапами;
  default-профиль бит-в-бит как раньше.
- **Phase 2 — Проводка `/analyze-1c-task`.** В начале: `pipeline_state.py init <jira> --profile 1c`.
  По завершении Фаз 1–3 → `done 1`; по завершении Фаз 4–5 → `done 2`. Артефакты этапов 1/2 указывают на
  `ANALYSIS-REPORT.md`. Установить чекпоинт одобрения дизайна после Этапа 2. В skill — заголовки 4 этапов +
  таблица маппинга (часть A). **DoD:** прогон `/analyze-1c-task` оставляет `pipeline/<jira>/` со стадиями 1–2.
- **Phase 3 — Проводка `/implement-1c-task`.** В Preflight: прочитать `pipeline_state.py status`; **гейт** —
  Этап 2 (Дизайн) `approved` (переиспользовать логику `approval-gate.py`/`gate`), иначе STOP с просьбой одобрить
  ANALYSIS-REPORT. По завершении Этапов 0–3 → `done 3`. Заголовки 4 этапов в skill. **DoD:** implement без
  одобренного дизайна блокируется; с одобренным — двигает state до этапа 3.
- **Phase 4 — Проводка Тестирования.** `/implement-1c-task` Этапы 4–6 и/или `/run-1c-tests` → `done 4`.
  Согласовать с `.run-state.json` (он остаётся детализацией прогона). **DoD:** после тестов state = этап 4 done.
- **Phase 5 — Сведение с ADR-018.** Убедиться, что `pipeline-protocol-stop.py` видит 1c-профильный state
  (он уже проверяет любой `*/.pipeline-state.json` — достаточно, что 1С-команды его обновляют). Обновить
  `CLAUDE.md` (1С Pipeline) + [17.5 Команды 1С Pipeline](../framework%20documentation/17_ТЕСТИРОВАНИЕ_1С/17.5_КОМАНДЫ_ПАЙПЛАЙНА.md) единым описанием потока. **DoD:** 1С-задача больше НЕ требует ручного создания второго пайплайна.
- **Phase 6 — Верификация e2e.** Реальная 1С-задача: analyze→approve→implement→tests → один `pipeline/<jira>/`
  со стадиями 1–4 + approval; Stop-хук удовлетворён без ручного пайплайна. **DoD:** зелёный e2e + обновлённая память.

## Риски и митигации

| Риск | Митигация |
|---|---|
| Сломать существующий 1С-workflow | Вариант B не трогает методику; профиль `1c` аддитивен; default-профиль регресс-тестом |
| Двойное состояние (`.run-state.json` + `.pipeline-state.json`) | Чёткое разделение: pipeline-state = макро-этап, run-state = прогон VA BDD; задокументировать |
| Сосуществование с SDD/OpenSpec-маршрутом | Гейт Этапа 2 переиспользует `approval-gate.py`; OpenSpec-approve = одно из условий approve этапа 2 |
| Кириллица/сабмодули в путях артефактов | Артефакты 1С остаются в `features/`/`configuration/<task>/docs/`; state — в `pipeline/<jira>/` (ASCII slug) |
| Откат | Реверс = убрать профиль `1c` + строки проводки из 2 команд; default-пайплайн не затронут |

## Acceptance (definition of done) для всего roadmap

- `pipeline_state.py` поддерживает профиль `1c` (default-профиль без регрессий, тест зелёный).
- `/analyze-1c-task` и `/implement-1c-task` создают/двигают единый `pipeline/<jira>/.pipeline-state.json`
  по 4 каноническим этапам с гейтом одобрения дизайна перед Кодированием.
- 1С-задача проходит Stop-хук ADR-018 **без** ручного создания отдельного пайплайна (G3 закрыт).
- Скиллы/команды содержат заголовки 4 этапов + таблицу маппинга (G2/G5 закрыты).
- `CLAUDE.md` + 17.5 описывают единый поток; ADR-019 accepted.

## §18 Progress log

| Дата | Phase | Событие | Артефакт/PR |
|---|---|---|---|
| 2026-06-14 | Phase 0 | Research + roadmap + ADR-019 (proposed) | этот файл, [ADR-019](../../.claude/skills/architecture-research/adr/019-1c-commands-4stage-pipeline-alignment.md) |

> Триггеры обновления §18 (memory `feedback-roadmap-progress-log-protocol`): PR merge, завершение фазы, ADR,
> снятый блокер. После каждого — обновить таблицу + коммит `docs(roadmap):`.
