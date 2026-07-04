# ADR-044: Робастность гейтов/пайплайна по паттернам лидеров (P3, roadmap 260703)

**Дата:** 2026-07-04
**Статус:** accepted
**Исследование:** [agentic-quality-gate-workflow-templates-2026](../cache/agentic-quality-gate-workflow-templates-2026.md), [pattern-pipeline-orchestration-2026](../cache/pattern-pipeline-orchestration-2026.md)
**Связь:** фаза P3 [roadmap 260703](../../../../docs/roadmap/260703_ROADMAP_CH43_1C_PIPELINE_AUDIT.md); закрепляет инвариант ADR-034 (gate-policy) / инцидента G-1 (P0.1)

## Контекст

Аудит гл. 43 (roadmap 260703) вскрыл инцидент G-1 (оркестратор гейтов рассинхронился с живыми
Stop-хуками) и потребовал 4-слойной ручной верификации при синхронизации доков (subagent-редакторы
вносили новый дрейф). GitHub-исследование ведущих agentic-workflow (koto/agentico/AWS AI-DLC/Graybark
+ OPA) дало 6 паттернов, которых у нас не хватало для **робастности** (не набора механизмов — он
соответствует фронту, а их надёжности и замкнутости петель).

## Решение

Реализованы 6 улучшений (каждый атрибутирован источником):

1. **P3.4 parity-harness как CI-guard** [web: OPA policy-тесты в CI] — `tests/unit/test_gate_parity_harness.py`:
   матрица синтетических Stop-контекстов (256 комбинаций композиции), инвариант `evaluate_gates ==
   AND(live_pipeline, live_onec)`. Рассинхрон политики с живым хуком валит CI → повтор G-1 невозможен.
   Выделенный CI-шаг «Gate parity (isolated)» обходит пред-существующую `shared`-коллизию полного сбора.
2. **P3.5 doc-drift линтер** [own: 4 дрейфа за сессию; web: code-anchored docs] — `scripts/lint_ch43_sync.py`:
   реестр инвариантов (flow-enum/effort-веса/фантомные тулы/#L-якоря/known-bad), факты ИЗ КОДА (ast+regex),
   не хардкод → не устаревает. CI advisory-джоб. Автоматизирует ручную сверку сессии.
3. **P3.1 gate-output → fix-петля** [web: koto `{{gate_output}}`, Graybark verify.sh] — `_fix_recipe`:
   block-сообщение единого гейта включает copy-paste команды ТОЛЬКО для незакрытых петель (вывод гейта =
   вход фикса, не «догадайся»); sonar fail-файлы прокинуты.
4. **P3.2 bounded AUTO + эскалация** [web: agentico max_failures=3, Graybark needs-human-p0/p1/p2] —
   `pipeline_state.bump_attempt`/`set_needs_human`: счётчик попыток этапа (env `ONEC_MAX_FIX_ITERATIONS`=4) +
   типизированная эскалация в state; run-1c-task SKILL останавливает петлю при exceeded. Против бесконечного retry.
5. **P3.3 адверсариальные критики дизайна** [web: agentico 6 критиков плана; Graybark 3 рецензента JSON] —
   run-1c-task SKILL: перед авто-approve (medium/complex) — 2-3 параллельных субагента-критика ANALYSIS-REPORT
   со структурным вердиктом; любой blocker → деградация в гейтованный поток. Компенсирует отсутствие
   человеческого ревью в AUTO.
6. **P3.6 compound-learning на провале** [web: Graybark docs/solutions → правило] — run-1c-task SKILL:
   при needs-human/повторном FAIL — `capture_pattern(error-fix)` с причиной провала + предложение правки
   SKILL/правила. Выравнивает петлю памяти (фиксирует успехи охотнее провалов).

## Последствия

### Положительные
- Класс дрейфа/рассинхрона, который в этой сессии прорывался 4× и вызвал инцидент G-1, теперь ловится
  автоматически (P3.4 hard CI-gate + P3.5 advisory). [own]
- AUTO-режим `/run-1c-task` перестал быть «доверься дисциплине»: bounded-петля + критики + типизированная
  эскалация делают застревание видимым и остановленным. [own]
- Блок-сообщения гейта — actionable (готовый fix-рецепт), меньше циклов «что чинить». [exp]

### Отрицательные / риски
- P3.4 harness даёт реальный CI-guard только в изолированной инвокации (пред-существующая `shared`→`src/shared`
  коллизия полного сбора — отдельный тех-долг, roadmap P1/P2 нота). Митигация: выделенный CI-шаг.
- P3.5 known-bad — курируемый список; новый класс дрейфа требует нового инварианта (расширяемый реестр). [own]
- P3.3/P3.6 — уровень методики (SKILL): исполняются, когда Claude ведёт `/run-1c-task`; не принуждаются хуком
  (в отличие от P3.1/P3.2/P3.4/P3.5). Приемлемо — AUTO-режим и так методико-ведомый. [own]

## Альтернативы (отклонены)
- **Фикс `shared`-коллизии вместо изолированного CI-шага** — отклонён ПОКА: большой рефактор импортов всех
  хуков; изолированный шаг даёт guard дешевле. Коллизия — отдельная задача.
- **P3.5 hard (--strict) сразу** — отклонён: доки живее кода, ложные блоки на легитимном опережении; advisory
  → промоут по накоплению доверия (лестница ADR-018/tdd-guard/035).
- **P3.3 критики как хук** — отклонён: субагент-оркестрация в Stop-хуке непрактична; методика в SKILL честнее.

## Связанные файлы
- `tests/unit/test_gate_parity_harness.py`, `scripts/lint_ch43_sync.py`, `.github/workflows/ci.yml`
- `.claude/hooks/onec-task-completion-stop.py` (`_fix_recipe`), `.claude/hooks/pipeline-protocol-stop.py`
- `.claude/hooks/shared/pipeline_state.py` (`bump_attempt`/`set_needs_human`), `.claude/skills/run-1c-task/SKILL.md`
