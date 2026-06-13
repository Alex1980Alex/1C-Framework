# ADR-013: Дизайн — architecture-research ядро + simplicity-discipline; frontend/Figma SKIP

**Дата:** 2026-06-13
**Статус:** accepted (реализовано 2026-06-13 — Этап 2.2)
**Исследование:** ../cache/claude-code-ecosystem-tools-2026.md
**Шаг SDLC:** 2. Дизайн

> **Реализация (260613 Этап 2.2):** из двух опций («секция в architecture-research» vs
> «отдельный skill») выбран **отдельный skill** [`simplicity-discipline`](../../simplicity-discipline/SKILL.md)
> (4 правила Karpathy + чеклист). **БЕЗ router-bundle записи** → нулевой regress
> `action_f1` (роутер не эмитит скилл вне бандла — структурно невозможно), доступен
> явным `Skill()` + semantic-surfacing (skill_library, floor-гейт 0.55). Реверс = удалить каталог.

## Контекст
Ресёрч предложил design-skills: Vercel (Web Design / React / Composition), Andrej
Karpathy Guidelines, Figma design-to-code, design-pattern субагенты. Нужно решить,
что усиливает наш дизайн-этап без поломок.

## Решение
**`architecture-research` остаётся ядром дизайна** (6-фаз research + cache + ADR).
Дополнительно: **simplicity-discipline** (Karpathy: think-before-coding / simplicity-first
/ surgical-changes / goal-driven) — внедрить как доп-секцию в `architecture-research/SKILL.md`
ИЛИ отдельный лёгкий skill (roadmap Этап 2.2). SKIP Vercel/Frontend/Figma.
- [own] Karpathy-принципы кодифицируют нашу подтверждённую anti-overfit / minimal-change
  дисциплину (Фаза C roadmap 260613: точечные правки, не переписывание).
- [web] Vercel-skills — frontend-only (React/Next.js); наш домен — Python/1C-бэкенд.
- [exp] Figma — нет дизайн-процесса в проекте.

## Последствия
**Положительные:** наша дисциплина «простота + хирургические правки» становится явной и переиспользуемой.
**Отрицательные:** нет UI-design помощи (не требуется для backend/1C).

## Альтернативы
- **Vercel/Frontend Design skills** — отклонены: frontend-домен, не наш.
- **Figma MCP (generate_diagram)** — отклонён сейчас: нет Figma-процесса; пересмотреть если появятся арх-диаграммы.

## Связанные файлы
`.claude/skills/architecture-research/SKILL.md`, `framework-patterns`, `docs/architecture/PATTERNS.md`.
