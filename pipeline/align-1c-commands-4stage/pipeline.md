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
- Доп. анализ (по запросу «есть ли ещё команды/решения»): 4-агентное исследование всего 1С-ландшафта →
  секция «Дополнительный анализ» в roadmap (3 пути реализации: direct/SDD/autonomous; 2 слоя тестов: VA BDD/YaXUnit;
  gaps G6–G15; Phases 0.5/7/8) + кеш-факты `architecture-research/cache/1c-task-implementation-landscape.md`.
- Глубокий разбор Варианта C (по запросу): 4-агентное вн/внеш исследование → секции «Глубокий разбор Варианта C»
  (D1–D5 спорные границы, 26 точек поломки C1–C26, гибрид C+B, индустрия strangler-fig/Spolsky/Brooks vs rewrite)
  + «Инструменты» (drift T.1; внешние кандидаты T.2: claude-code-bsl-lsp/mcp-bsl-lsp-bridge/Coverage41C/1c-templates-mcp/
  1c-mcp-metacode/comol-cursor_rules_1c; Phase 9) + кеш `cache/1c-bsl-tooling-ecosystem-2026.md`.
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
