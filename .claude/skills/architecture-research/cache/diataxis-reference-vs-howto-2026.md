# Diátaxis: reference vs how-to — что где документировать (2026-07-19)

**Источник:** [diataxis.fr](https://diataxis.fr) (Daniele Procida, канонический фреймворк таксономии технической документации). Verified via WebFetch 2026-07-19.

## Четыре типа документации

Diátaxis разделяет доку по двум осям (изучение↔работа, практика↔теория):
- **Tutorials** — обучение, шаги для новичка (learning-oriented).
- **How-to guides** — решение конкретной задачи (task-oriented).
- **Reference** — точное описание машинерии (information-oriented).
- **Explanation** — почему так устроено (understanding-oriented).

## Ключевое различие how-to ↔ reference (наш кейс)

**How-to guides** (= Claude Code скиллы: task-oriented, ~500 строк, progressive disclosure):
> «Practical usability is more helpful than completeness. Whereas a tutorial needs to be a complete, end-to-end guide, a how-to guide does not.»
> «Refer to the x reference guide for a full list of options. **Don't pollute your practical how-to guide with every possible thing the user might do.**»

How-to начинается и кончается в точках, значимых для задачи; предполагает базовые знания; НЕ перечисляет исчерпывающе.

**Reference** (= доки `docs/framework documentation/`):
> «Yes, exhaustive listings of API endpoints, configuration variables, and classes belong in reference documentation.»
> «The structure of the documentation should mirror the structure of the product.»
> Принцип «Describe and only describe» — нейтральное описание, без инструкций/объяснений.
> Reference **консультируют** (lookup), а не читают подряд.

## Применение во фреймворке

| Артефакт | Тип Diátaxis | Что несёт |
|----------|--------------|-----------|
| `.claude/skills/*/SKILL.md` | **How-to** | task-guidance, лимит BODY500, progressive disclosure → `references/` |
| `docs/framework documentation/` | **Reference** | исчерпывающие списки endpoint'ов, config-переменных, классов |
| ADR / `explanation` | **Explanation** | почему приняли решение |

**Следствие (ADR-054):** аудит покрытия (`audit_docs_skills.py`) должен считать skill-gap только для task/концептуальных категорий (agent/strategy/mcp_tool/cli/wiki). Справочные (config_var/endpoint/hook/классы) — только по оси docs. Массовый дамп reference-списков в SKILL.md = Diátaxis-антипаттерн «pollute the how-to guide» (что и делал баговый `--update`).

## Связь
- [ADR-054](../adr/054-doc-skill-coverage-diataxis-scoping.md) — скоуп skill-метрики.
- `skills-system-best-practices-2026.md` — официальный контракт SKILL.md (500-строк body ⇒ согласуется с «how-to не перечисляет всё»).
