# ADR-054: Скоуп skill-gap-метрики аудита покрытия по Diátaxis

- **Статус:** Accepted
- **Дата:** 2026-07-19
- **Контекст-триггер:** чистка протёкших `--update`-таблиц в 9 скиллах вскрыла, что skill-gaps подскочили 24→298.

## Контекст

`scripts/audit_docs_skills.py` меряет покрытие фич кода по двум осям: **docs** (`docs/framework documentation/`) и **skills** (`.claude/skills/*/SKILL.md`). Метрика skill-gap проверяет, упомянута ли КАЖДАЯ фича (298 config-переменных, 88 endpoint'ов, 101 хук, внутренние классы) в скилле.

Эта метрика удовлетворима только **массовым дампом** каждого элемента в SKILL.md. Именно это делал баговый прогон `--update` (updater `update_skill_file` вписывал секции «## Незадокументированные X»). Дамп раздул `framework-config` за официальный бюджет BODY500 и был мислейблен. Удаление дампов «обнажило» истинно низкое skill-покрытие справочных фич (24→298), т.к. дампы БЫЛИ единственным их упоминанием (whole-tree fallback их засчитывал).

## Решение

Skill-gap считается **только для task/концептуальных категорий**:
`SKILL_COVERAGE_CATEGORIES = {agent, strategy, mcp_tool, cli_command, wiki_component}` (все уже 100%).

Справочные категории (`config_var`, `endpoint`, `hook`, `memory_subsystem`, `bsl_tool`) трекаются **только по оси docs**; их `coverage_skills = None` (n/a).

## Обоснование (best-practice, GitHub/web research)

**Diátaxis** (канонический фреймворк таксономии документации, [diataxis.fr](https://diataxis.fr)):
- **How-to guides** (= Claude Code скиллы: task-oriented, лимит ~500 строк, progressive disclosure): *«Refer to the reference guide for a full list of options. Don't pollute your practical how-to guide with every possible thing the user might do. Practical usability is more helpful than completeness.»*
- **Reference** (= доки фреймворка): *«exhaustive listings of API endpoints, configuration variables, and classes belong in reference documentation... structure mirrors the product.»*

Требовать, чтобы скилл-гайд перечислял каждую config-переменную/endpoint - прямой Diátaxis-антипаттерн («pollute the how-to guide»). Ось docs уже несёт эту ответственность (config/endpoint/hook = 82-100% doc-покрытие).

## Последствия

- Баннер `[AUDIT-COVERAGE]`: **22 doc + 0 skill** (было 89+52 шума → 22+24 → честные 22+0).
- **Чинит корень pollution:** `--update` больше не имеет skill-gaps для справочных категорий → не дампит их в скиллы.
- 9 протёкших таблиц удалены и остаются удалёнными (reference-в-how-to = нарушение таксономии).
- Остаток 22 doc-gaps = реально экспортированные-но-недокументированные внутренние классы (bsl 13 + memory 9) - честный сигнал на правильной оси.

## Альтернативы (отклонены)

- **Вернуть таблицы честным справочником в скиллы** - нарушает Diátaxis + бюджет BODY500; рецидив «дампа».
- **Оставить skill-gaps=298** - честно, но баннер алармит и метрика меряет не то.

## Связь

Продолжает [ADR-011](011-curated-memory-sync-model.md) (курируемость), кеш `architecture-research/cache/diataxis-reference-vs-howto-2026.md`, память `project-audit-docs-banner-precision-fix`.
