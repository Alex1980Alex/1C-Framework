# F-3 — Дизайн (self-approve)

Вставить блок-ноту после frontmatter (`---`), перед `# …` заголовком каждого SKILL.md.

**analyze-1c-task-v2/SKILL.md** ← Этап 1 (Фазы 1–3) + Этап 2 (Фазы 4–5), артефакт ANALYSIS-REPORT, авто-проводка F-1/F-1.5, гейт F-2.
**implement-1c-task/SKILL.md** ← Этап 3 (Этапы 0–3) + Этап 4 (Этапы 4–6 + write/run-tests), артефакт IMPLEMENTATION-PROGRESS, гейт F-2.

Текст нот — в 03 (реализовано). Только документация, методика не тронута.

**DoD:** обе ноты на месте; `frontmatter` парсится (python yaml на head); без правок логики. Откат = revert нот.
