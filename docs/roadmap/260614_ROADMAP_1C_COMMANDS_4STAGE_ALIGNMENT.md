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

## Дополнительный анализ (2026-06-14): полный ландшафт реализации 1С-задач

> Расширение по запросу пользователя («возможно есть ещё команды и другие решения») — параллельное
> исследование (4 субагента) всего surface'а 1С-автоматизации. Объективная инвентаризация фактов —
> в кеше [1c-task-implementation-landscape.md](../../.claude/skills/architecture-research/cache/1c-task-implementation-landscape.md).
> Вывод: реализация 1С-задач идёт по **трём путям** + **двум слоям тестирования**; выравнивание к 4 этапам
> должно покрыть ВСЕ их, а не только `/analyze-1c-task`+`/implement-1c-task`.

### A. Три пути реализации (а не один)

| Путь | Цепочка | Когда (критерий analyze-1c-task-v2 §11) | Кто кодирует | Гейт |
|---|---|---|---|---|
| **1. Прямой** | analyze → implement (8 этапов) → write/run-tests | тривиальная (нет `[ADDED]` метаданных) | `implement-1c-task` (validate_query→execute_query→EDT write→get_project_errors→BP-verify) | preflight `debug_health_check` (выбор режима), НЕ межэтапный |
| **2. SDD/OpenSpec** | analyze → opsx:propose → opsx:approve → opsx:apply → brownfield-validate → opsx:archive | средняя/сложная (`[ADDED]` объекты ИЛИ 3+ `[MODIFIED]`) | `openspec-apply-change` — **кодит напрямую**, минуя 8-этапный pipeline | `approval-gate.py` (hard: `.openspec.yaml approval=approved`) |
| **3. Автономный** | analyze-1c-research (Executor→Reviewer→Comparator, score→85) / Ralph (`1c-analysis`, `1c-study`) | headless/итеративный анализ; код всё равно уходит в путь 1/2 | — (только анализ) | Ralph Stop-хук (маркер `RALPH_DONE`) |

Тестирование — **два независимых слоя**: VA BDD (Vanessa, E2E/UI, `/write-1c-tests`+`/run-1c-tests`, `.run-state.json`) и YaXUnit (unit, `mcp-onec-test-runner` + реактивный `auto-test-after-write`). Вместе не оркестрируются.

### B. Полная карта (кратко; детали — в кеше)
- **Команды (5 профильных + 4 SDD):** `/analyze-1c-task`, `/implement-1c-task`, `/write-1c-tests`, `/run-1c-tests`, `/activate-project` (деградировал) + `/opsx:propose|approve|apply|archive` (доменно-агностичны, используются для 1С).
- **BSL-инструменты (Кодирование):** EDT-MCP (write), 1c-mcp-crud (data), bsl-debugger (статлинт), bsl-semantic-search (refactor), 1c-debug-hmr (live BP-verify Этап 5.x) + скиллы bsl-development / bsl-refactoring-workflow / bsl-symbol-editing.
- **1С-хуки:** bsl-tool-router, analyze/implement-preflight, implement-smoke-stop-alert, submodule-status-check, post-commit BSL-reindex (`bsl_code_v4_late`).

### C. Расширенный gap-анализ (G6–G15) — сверх G1–G5

| # | Разрыв | Источник | Влияние |
|---|---|---|---|
| G6 | `opsx:apply` (`openspec-apply-change`) кодит **напрямую**, минуя 8-этапные проверки `implement-1c-task` (validate_query/execute_query/get_project_errors/BP-verify) | `openspec-apply-change/SKILL.md` | SDD-путь теряет 1С-качество → «Кодирование» неэквивалентно между путями |
| G7 | `approval-gate.py` блокирует `implement-1c-task` (и `opsx:apply`) при ЛЮБОМ неодобренном active change — не различает «мой change» | `approval-gate.py:_IMPLEMENTATION_SKILLS` | чужой неодобренный change зажимает даже тривиальный прямой маршрут |
| G8 | G3 шире: `pipeline-protocol-stop` видит только `pipeline-state`, не `tasks.md`/`.openspec.yaml`/`data/analyze-1c-research/` | `pipeline-protocol-stop.py:_pipeline_used_since` | hard-block завершения при честно выполненной SDD/автономной задаче |
| G9 | `brownfield-validate` информационный (не enforced; «зуб» — Stop-reminder с cooldown) | `brownfield-validate/SKILL.md` | «Тестирование» в SDD де-факто опционально |
| G10 | `TEST-PLAN-DETAILED.md` — orphan: его **читает** `/write-1c-tests`, но ни одна команда не **порождает** | инвентаризация команд | разрыв Дизайн↔Тестирование |
| G11 | VA BDD и YaXUnit не оркестрируются вместе; тест-состояние размазано (`.run-state.json` / METR / `data/analyze-1c-research/`) | агент тестирования | нет единой точки «вердикт Этапа 4» |
| G12 | **Tooling drift:** `bsl-tool-router.py`, `bsl-development/SKILL.md`, `auto-test-after-write/SKILL.md` ссылаются на отключённые/переименованные инструменты (serena, mcp-reasoner, `mcp__metr__*`/`run_tests`, late-chunking pooling) | агент BSL-инструментов | выравнивание ляжет на сломанные ссылки → нужен prerequisite-cleanup |
| G13 | `/activate-project` деградировал (Serena LSP мёртв на BSL, `serena-index-checker.py` удалён) | `activate-project.md` | мёртвая команда в 1С-lifecycle → вывести |
| G14 | Path-drift после миграции на C:: `run-bdd.ps1` (glob `D:\1*-Framework`), METR-конфиг (`D:\1С-Framework`), VA-харнесс в `D:\va-test` | агент тестирования | тест-слой может не найти framework root на C: |
| G15 | Нет файла профиля `openspec/profiles/1c-bsl.yaml` (правила 1С размазаны по `openspec-propose`) | агент SDD | дефолтный профиль `1c-bsl` без централизованных правил |

### D. Пересмотр рекомендации (расширение Варианта B)

База (Вариант B, мост pipeline-state) сохраняется, но расширяется на весь ландшафт:
1. Профиль `1c` в `pipeline_state.py` покрывает **все три пути** (direct/SDD/autonomous) — каждый `done`/`approve` единый `.pipeline-state.json`.
2. **Унифицировать гейты:** `pipeline-gate` (этап 2 approved) и `approval-gate` (openspec approved) → один stage-2-гейт (OpenSpec-approve = достаточное условие approve этапа 2); сузить `approval-gate` до «своего» change (G7).
3. **Решить дивергенцию Кодирования (G6):** `opsx:apply` для 1С должен делегировать `implement-1c-task` (сохранить 8-этапные проверки) ЛИБО явно задокументировать осознанный trade-off.
4. **Расширить `pipeline-protocol-stop`:** считать «pipeline used» также при обновлённом OpenSpec change / autonomous state (или обязать все пути писать `pipeline-state`) — закрывает G8.
5. **Этап 4 (Тестирование):** свести VA + YaXUnit + brownfield под единый «вердикт Этапа 4», обязательный для закрытия (G9, G11).

### E. Обновлённый план фаз (надстройка над Phase 0–6)

- **Phase 0.5 (NEW, prerequisite) — Drift cleanup:** актуализировать `bsl-tool-router.py`, `bsl-development/SKILL.md`, `auto-test-after-write/SKILL.md` под реальный стек (1c-debug-hmr, mcp-onec-test-runner; без serena/reasoner); починить path-drift C:/D: (G12, G14); вывести/починить `/activate-project` (G13). Без этого выравнивание опирается на сломанные ссылки.
- **Phase 1–6** — как раньше (профили + проводка analyze/implement + тестирование + сведение с ADR-018 + e2e).
- **Phase 7 (NEW) — SDD-путь под 4 этапа:** проводка opsx-цепочки в `pipeline-state` (профиль `1c`); унификация гейтов (G7); решение по G6 (opsx:apply→implement); профиль `1c-bsl.yaml` (G15).
- **Phase 8 (NEW) — Автономный путь + единый Этап 4:** интеграция analyze-1c-research/Ralph state в pipeline-state; orphan `TEST-PLAN` (G10); единый вердикт тестирования (G9, G11).

> Эти фазы — расширение, не замена. ADR-019 покрывает ядро (Вариант B); дивергенция кодирования и гейтов
> (G6/G7) при реализации Phase 7 вероятно потребует отдельного **ADR-021** (ADR-020 занят Phase 9 tooling-adoption).

## Глубокий разбор Варианта C (по запросу) + C-vs-B по индустрии

> Максимально-глубокий ре-анализ Варианта C (полный сплит: analyze→`pl-plan-1c`/`pl-design-1c`,
> implement→`pl-code-1c`/`pl-test-1c`). Отдельное 4-агентное исследование (внутреннее + GitHub/web).
> Внешние факты — в кеше [1c-bsl-tooling-ecosystem-2026.md](../../.claude/skills/architecture-research/cache/1c-bsl-tooling-ecosystem-2026.md).

### C.1 Спорные границы (методика не режется чисто)
- **D1** Фаза 5 (Верификация): тест-**план** = Дизайн, тест-**прогон** = Тестирование → §7 пишется в дизайне, читается в тестировании (усугубляет G10 orphan `TEST-PLAN`).
- **D2** Этап 0 Preflight (capability matrix) нужен И Кодированию, И Тестированию → при сплите гоняется дважды или прокидывается через state.
- **D3** Этап 5.x BP-verify валидирует только что написанный код (`frames[0].lineNo==MODIFIED_LINE`) и блокирует Этап 6 — это «проверка кодирования», не приёмка; любое отнесение к code/test спорно + рвёт debug-session (footer `debug_session_id` пишет code-команда, читает test).
- **D4** Этап 8 Git (3-уровневый сабмодульный коммит). **D5** Фаза 2.5 Runtime Trace дублирует debug-стек с code/test.
- Итог: Планирование↔Дизайн и Кодирование↔Тестирование **не имеют чистого разреза** — корневая причина выбора B (макро-этап в state поверх неразрезанной методики).

### C.2 Что сломается — ~26 точек (C1–C26, grep-аудит), сгруппировано
- **Имена команд (CODE):** `analyze-1c-task-preflight`/`implement-1c-task-preflight`/`smoke-stop-alert` (привязка к `TARGET_COMMAND`), `settings.json`, фильтры по токену `slash:<name>`.
- **Формат `ANALYSIS-REPORT` (CODE/DATA):** `score-analysis-report.py` (главный потребитель — парсит §1/§4/§6, точки, `[REQ-N]`), `eval-analysis-scorer.py`, implement Этап 1 (контракт чтения точек), Reviewer/Comparator scoring-маркеры, ~18 живых отчётов + шаблон.
- **SDD (CODE):** `opsx:propose` populate'ит из секций ANALYSIS-REPORT → сплит ломает populate.
- **Ralph/autoresearch (CODE):** шаблоны `1c-analysis-{executor,reviewer,comparator}` опираются на 5-фазную analyze как целое.
- **Generic-пайплайн (CODE):** `pipeline_state.py` `_BY_COMMAND`/STAGES хардкодит `pl-*`; `pipeline-gate.py` `PIPELINE_COMMANDS`; **`pipeline-protocol-stop.py` (= G3) снимается ТОЛЬКО записью `.pipeline-state.json` — сам сплит этого НЕ даёт**.
- **Docs/UX:** 17.5, КОМАНДЫ_CLAUDE_CODE, ~10 doc/wiki, CLAUDE.md, память; UX-путаница `pl-plan` vs `pl-plan-1c`.
- Объём: **~20–30 файлов, сотни строк, высокий регресс-риск** (B: ~5–8 файлов, низкий, методика не тронута).

### C.3 Гибрид C+B (ключевой результат)
Тонкие команды-обёртки `pl-*-1c`, делегирующие в существующие скиллы analyze/implement/va-bdd-testing поверх B-проводки (профиль `1c`), **БЕЗ дробления `ANALYSIS-REPORT`**:
- Устраняет главные риски C: scorer, миграция артефактов, SDD-populate, контракт implement — всё работает as-is (отчёт единый).
- Остаётся поверх B: 4 команды + правка preflight (target/алиасы) + доки + UX-развязка имён; частично D2/D3.
- Профит над B: ровно **канонические имена команд** (UX), функциональности не добавляет.

### C.4 C vs B — вердикт индустрии (rewrite vs incremental)
- **Strangler Fig** (Fowler/Azure/Thoughtworks): новая реализация за стабильным фасадом, переключение постепенно, лёгкий rollback [web].
- **Branch by Abstraction** (Fowler/Confluent): внутрипроцессная миграция — абстракция → инкрементальная замена → удаление старого [web].
- **Spolsky** «никогда не переписывай с нуля» (теряются «закодированные» edge-cases); **Brooks** second-system effect [web].
- Наш случай: 1С-команды — **наш видимый код** с накопленными edge-cases (pre-scenario TestDB check, resume, BP-trace) → аргумент «нет видимости → rewrite» НЕ применим.

### C.5 Финальный вердикт по C (усилён)
**Чистый Вариант C — отклонён** с количественным + индустриальным обоснованием: ≈4–6× стоимости B, ~26 точек поломки, near-zero доп.функциональность; G3/G4 решаются тем же кодом, что в B; индустрия против rewrite видимой рабочей системы.
**Рекомендация:** B как strangler-фасад (Phase 1–6) → при ценности канонических имён добавить **гибридные обёртки `pl-*-1c` опциональной фазой B.1** (Branch by Abstraction внутри; `/analyze-1c-task`/`/implement-1c-task` — алиасы для preflight/Ralph/SDD/памяти). Путь к фактическому C **без** его риска: «Strangler снаружи + Branch by Abstraction внутри».

## Инструменты: используемые / неиспользуемые + внешние кандидаты

### T.1 Drift: собранные, но НЕ подключённые (конкретизирует G12)
4 готовых 1С-инструмента физически есть и **декларируются в скиллах**, но ОТСУТСТВУЮТ в активном `.mcp.json` (только в stale `D:\`-профилях + `registry.yaml`) → скиллы зовут неподключённые серверы (фантом-вызовы):

| Инструмент | Статус | Фантомно зовётся в | Действие |
|---|---|---|---|
| `ast-grep-mcp` | собран, disabled | bsl-refactoring-workflow (fallback rename), bsl-symbol-editing, va-bdd-testing | вернуть в `.mcp.json` ИЛИ убрать из fallback |
| `mcp-reasoner` | собран, disabled, но «ОБЯЗАТЕЛЬНЫЙ» в bsl-development | `mcp__reasoner__processThought` | вернуть ИЛИ снять «обязательность» |
| `serena` | dead на BSL (LSP невалиден), откачен | bsl-development, auto-test-after-write | убрать фантом-вызовы |
| `bsl-semantic-diff` | dormant | — (registry) | опц. подключить для diff-ревью |

Плюс: `auto-test-after-write` зовёт `mcp__metr__*`/`run_tests`, сервер — `mcp-onec-test-runner`/`run_module_tests` (авто-тест после записи, вероятно, не срабатывает); `va-bdd-testing` allow-list зовёт `mcp__1c-mcp-server__*` вместо `mcp__1c-mcp-crud__*`; `coverage41c.jar` в CI — 9-байтовый stub `Not Found` (покрытие skip); Vanessa `.epf/.cfe` в `tools/vanessa/` — байтовые плейсхолдеры. → всё это наполняет **Phase 0.5 drift-cleanup**.

### T.2 Внешние кандидаты (GitHub, чего у нас нет; ★/версии — снимок 2026-06-14, сверить)

| Инструмент | Источник | Закрывает | Ценность |
|---|---|---|---|
| **claude-code-bsl-lsp** | `github.com/1c-syntax/claude-code-bsl-lsp` (офиц., MIT) | inline BSL LSP в Claude Code (диагностики/go-to-def/refs/format) — у нас BSL-LS только batch/CI | **High** |
| **mcp-bsl-lsp-bridge** | `github.com/SteelMorgan/mcp-bsl-lsp-bridge` | 100+ BSL-LS проверок как MCP-tool в агентном цикле (без CI-петли) | **High** |
| **Coverage41C** | `github.com/1c-syntax/Coverage41C` (~108★) | покрытие BSL-тестами через dbgs:1550 → genericCoverage.xml (наш SonarQube читает) | **High** |
| **1c-templates-mcp** | `yellowmcp.com/.../1c-templates-mcp` | 2200+ BSL-шаблонов (few-shot для генерации) | **High** |
| **1c-mcp-metacode** | `github.com/ROCTUP/1c-mcp-metacode` | Neo4j call-graph из коробки → закрывает баг `neo4j_service=None` ([[reference_bsl_search_architecture_gap]]) | **High** |
| **comol/cursor_rules_1c** | `github.com/comol/cursor_rules_1c` | референс: 11–13 ролевых 1С-агентов (planner/architect/developer/tester) на 4 этапа + OpenSpec | **High** |
| **vanessa-runner** | `github.com/vanessa-opensource/vanessa-runner` (~110★) | оркестратор CI 1С (init-db/load/dump/test/bdd одной командой) | Med-High |
| **precommit1c** | `github.com/xDrivenDevelopment/precommit1c` (~187★) | .epf/.erf ↔ текст для git-diff/review (у нас .epf бинарно) | Med-High |
| **edt-test-runner** | `github.com/bia-technologies/edt-test-runner` | YAxUnit-тесты в EDT-UI с отладкой падающего теста | Med |
| **1c-ai-sandbox** | `github.com/SteelMorgan/1c-ai-sandbox-client-server` | изолированный 1С-sandbox → закрывает pending `sandbox-execution` | Med |

Каталог MCP для 1С: `github.com/Untru/1c-mcp`. **DEPRECATED (не брать):** ring CLI (→ EDT CLI), deployka (→ vrunner), xUnitFor1C (→ YAxUnit). **Сверить версии своих:** bsl-language-server v0.29.0 (128+ диагностик), sonar-bsl-plugin v1.11.0.

### T.3 SDLC-практики (подтверждают курс)
- **OpenSpec** — официально для brownfield + approval-gate; уже в стеке (analyze-1c-task-v2 v4.0) → носитель Планирование+Дизайн, не строить параллель.
- **GitHub Spec Kit** — `specify→plan→tasks→implement` + «constitution» (свод инвариантов на все этапы — у нас нет; для 1С = БСП-правила); перф OpenSpec 12мин/Spec Kit 90мин/BMAD 5.5ч → подтверждает «trivial→компактный pipeline.md» (ADR-018).
- Ниша «авто-генератор YAxUnit-тестов» в индустрии пуста → наша ниша (LLM, у нас уже `autotestplan`).

### T.4 Новые фазы (надстройка)
- **Phase 9 — Adoption candidates → РЕАЛИЗОВАНО** ([ADR-020](../../.claude/skills/architecture-research/adr/020-phase9-1c-tooling-adoption-verified.md), verified 2026-06-14). Верификация скорректировала оптимистичные «High»: **Coverage41C ADOPT** (fix 9-байт stub→`Coverage41C-2.7.3/bin`), **bsl-ls 0.22.0→0.29.0 ADOPT** (bump, +~14 диагностик), **mcp-bsl-lsp-bridge EVAL** (Apache-2.0, но дубль bsl-semantic-search; gap=completion/hover), **sonar 1.16.1→1.18.1 DEFER** (нужен SonarQube ≥2025.4) + **fix** `config_manager.py` drift 1.0.0→1.16.1 (сделано), **claude-code-bsl-lsp SKIP** (плагин ⟂ SKIP-marketplace), **1c-mcp-metacode SKIP** (license:null + дубль GraphRAG), **1c-templates-mcp DEFER** (license:null). Adopt-исполнение (Coverage41C wiring, bsl-ls 94MB bump) — отложено до CI-runner/go-ahead.
- **B.1 (опц.)** — гибридные обёртки `pl-*-1c` (C.3/C.5), если нужны канонические имена.

## §18 Progress log

| Дата | Phase | Событие | Артефакт/PR |
|---|---|---|---|
| 2026-06-14 | Phase 0 | Research + roadmap + ADR-019 (proposed) | этот файл, [ADR-019](../../.claude/skills/architecture-research/adr/019-1c-commands-4stage-pipeline-alignment.md) |
| 2026-06-14 | Phase 0+ | Доп. анализ: 3 пути реализации + 2 слоя тестов; gaps G6–G15; Phases 0.5/7/8; кеш landscape (4-агентное исследование) | секция «Дополнительный анализ» + [кеш](../../.claude/skills/architecture-research/cache/1c-task-implementation-landscape.md) |
| 2026-06-14 | Phase 0++ | Глубокий разбор Варианта C (D1–D5, 26 точек C1–C26, гибрид C+B, индустрия C-vs-B) + tool-census (drift T.1) + внешние кандидаты (T.2) + Phase 9; кеш ecosystem (4-агентное вн/внеш исследование) | секции «Глубокий разбор Варианта C» + «Инструменты» + [кеш ecosystem](../../.claude/skills/architecture-research/cache/1c-bsl-tooling-ecosystem-2026.md) |
| 2026-06-14 | Phase 9 | РЕАЛИЗОВАНО: verified adopt/skip 5 кандидатов + версии (bsl-ls 0.22→0.29, sonar 1.16.1→1.18.1, Coverage41C 2.7.3 stub); fix config_manager.py drift; ADOPT-исполнение отложено до инфры | [ADR-020](../../.claude/skills/architecture-research/adr/020-phase9-1c-tooling-adoption-verified.md) + `config_manager.py` |

> Триггеры обновления §18 (memory `feedback-roadmap-progress-log-protocol`): PR merge, завершение фазы, ADR,
> снятый блокер. После каждого — обновить таблицу + коммит `docs(roadmap):`.
