# Roadmap 260523 — Unified Branch Topology Reconciliation

**Дата создания:** 2026-05-23
**Статус:** living document — Phase 0 DONE (PR #4 landed), Phase 1-5 PENDING
**Заменяет:** [260519](260519_ROADMAP_MASTER_RECONCILIATION.md) + [260522](260522_ROADMAP_PR_AUTOMATION_MIGRATION_TO_DEV_MASTER.md)
**Память:** [project_disjoint_master_topology](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/project_disjoint_master_topology.md), [feedback_precommit_vendor_excludes](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/feedback_precommit_vendor_excludes.md)

---

## §0 TL;DR

В репо живут две независимые ветки истории: `origin/master` (legacy, frozen Apr 2026) и `origin/dev-master` (canonical для разработки). Они без общего предка — `git merge-base` пусто. Это корневая проблема (roadmap 260519).

Следствие: любая фича разрабатываемая на длинноживущей `feat/serena-audit-hybrid-refactor` (2233+ коммитов поверх `dev-master`) не может быть merged быстро — её нужно мигрировать на `dev-master` отдельным PR'ом с inventory + protocol-port + surgical settings.json patches. **PR-automation было первым прохождением** этого паттерна (roadmap 260522 → **PR #4 MERGED 2026-05-23**). Каждая следующая фича повторит цикл.

**Unified roadmap решает три задачи:**
1. **Стандартизирует** workflow «feat → dev-master migration PR» (lessons из PR #4 round-6/7)
2. **Закрывает** structural master reconciliation (260519 Phase 2-6)
3. **Удаляет** `dev-master` как workaround, делая `master` единственной canonical branch

Трудозатраты: **3-7 часов** + одна крупная migration PR из feat-ветки.

---

## §1 Реальная картина 2026-05-23
