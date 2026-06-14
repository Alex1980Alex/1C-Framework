# ADR-012: Планирование — OpenSpec ядро SDD; Spec Kit/BMAD SKIP; Grill Me опц.

**Дата:** 2026-06-13
**Статус:** accepted
**Исследование:** ../cache/claude-code-ecosystem-tools-2026.md
**Шаг SDLC:** 1. Планирование (решение фиксируется в Дизайне)

## Контекст
Ресёрч экосистемы Claude Code (2026) выявил 3 spec-driven-фреймворка планирования:
GitHub Spec Kit (80k★), BMAD-METHOD (37k★), OpenSpec. Нужно решить — менять ли наш
стек планирования или оставить текущий. Условие внедрения: ничего не сломать
(roadmap [260613 Tooling Adoption](../../../../docs/roadmap/260613_ROADMAP_TOOLING_ADOPTION.md)).

## Решение
**OpenSpec остаётся ядром планирования.** SKIP Spec Kit и BMAD.
- [exp] OpenSpec уже даёт spec→plan→approval-gate (`openspec-mcp` + SDD approval-gate hook, MEMORY pattern «SDD Approval Gate»).
- [web] BMAD ~31.7k токенов/прогон — дороже; вводит чужие роли-агенты (PM/architect/dev), конфликтующие с нашим task-protocol.
- [own] миграция = риск сломать рабочий approval-gate без выигрыша.
- **Grill Me** (mattpocock) — опционально как лёгкий skill `plan-grill` (интеррогация плана), additive, opt-in (roadmap Этап 1.3).

## Последствия
**Положительные:** ноль регрессий, ноль доп-стоимости, рабочий SDD-flow не тронут.
**Отрицательные:** не получаем GitHub-distribution Spec Kit (нам не нужен); Grill Me — лишний skill, если включим (mitigated: opt-in + router regress-чек).

## Альтернативы
- **Spec Kit** — отклонён: дублирует OpenSpec (spec→plan→tasks), миграция без выигрыша.
- **BMAD** — отклонён: дорогой по токенам, чужая ролевая модель агентов.

## Связанные файлы
`.mcp.json` (openspec-mcp), SDD approval-gate hook, skill `openspec-*`, (опц.) `.claude/skills/plan-grill/`.
