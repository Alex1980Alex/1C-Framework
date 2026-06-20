# 01 — Планирование

**Задача:** pre-push submodule-ordering guard — предотвратить класс PR #77 (dangling gitlink: родитель пушит указатель на незапушенный коммит сабмодуля → клон/CI ломается).
**Источник:** критический анализ оркестрации ([cache/orchestration-best-practices](../../.claude/skills/architecture-research/cache/orchestration-best-practices.md)) — единственный gap с реальной непокрытой ценностью под single-user. Проверено: `pre-push` (ruff/compileall) и `submodule-status-check` НЕ покрывают push-ordering.
**Цель:** блок push родителя, если изменённый gitlink указывает на коммит, не достижимый на remote сабмодуля.
