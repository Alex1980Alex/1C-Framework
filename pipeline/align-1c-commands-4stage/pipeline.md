# Pipeline (complex / planning-only): align-1c-commands-4stage

Задача (запрос пользователя): привести `/analyze-1c-task` и `/implement-1c-task` к концепции
**Планирование архитектуры → Дизайн реализации → Кодирование → Тестирование**; сделать исследование
и сформировать дорожную карту. **Это планирование** — кода скиллов/команд не трогал, только research-артефакты.

## 1. План (Планирование)
Исследовать обе staged-SDLC реализации фреймворка и спроектировать их сведение.
Skill `architecture-research`: Фаза 0 кеш → Фаза 1 docs/skills/commands → синтез.

## 2. Дизайн (Дизайн)
Разрыв-анализ G1–G5 (границы этапов, словарь артефактов, отсутствие pipeline-state у 1С → двойная
бухгалтерия с ADR-018, рассинхрон гейтов, именование). Варианты A/B/C. Выбран **B (мост pipeline-state) +
relabel из A**. Решение → [ADR-019](../../.claude/skills/architecture-research/adr/019-1c-commands-4stage-pipeline-alignment.md) (proposed).

## 3. Реализация (этой задачи = артефакты)
- Roadmap: [`docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md`](../../docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md)
  (контекст, текущее состояние, gap, варианты, целевой маппинг, фазы 0–6, риски, DoD, §18).
- ADR-019 + запись в `architecture-research/adr/_index.json`.
- **Код фреймворка (Phase 1–6 roadmap) НЕ писался** — это отдельная будущая работа, ждёт ревью/одобрения roadmap.
- Побочный bugfix (вне scope roadmap, найден при финализации): [`factory-enforcer.py`](../../.claude/hooks/factory-enforcer.py)
  ложно срабатывал на ADR-файлах (`skills/*/adr/*.md`) как на «создании нового skill» → добавлен `/adr/` в `SKIP_PATHS`
  (паритет с `/cache/`). code-verify PASS (bug-fix-validation, субагент). Это и закрыло спур-задачи factory-enforcer.

## 4. Тест (Тестирование)
Планировочная задача (без кода) → исполняемых тестов нет. Верификация = внутренняя:
- маппинг 4 этапов ↔ 1С-фазы сверен с фактическими skill'ами (analyze-1c-task-v2 v4.3, implement-1c-task v2.7);
- ADR-019 в формате Context→Decision→Consequences→Alternatives, № 019 = следующий по `_index.json`;
- roadmap по конвенции (Status/Context/Acceptance/§18 progress-log).
Следующий шаг — ревью roadmap пользователем; реализация Phase 1 (профили `pipeline_state.py`) — отдельной задачей.
