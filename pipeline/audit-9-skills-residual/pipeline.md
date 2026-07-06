# audit-9-skills-residual (trivial)

Задача: верифицировать исполнение roadmap 260705 (аудит гл. 9_НАВЫКИ), найти ошибки, сформировать карту исправлений.

- **План/Дизайн:** code-first — сам прогнал 5 тулов + 31 unit + CI-конфиг; 2 read-only агента сверили doc-претензии P0/P1 с первоисточниками.
- **Код:** артефакт — [docs/roadmap/260706_ROADMAP_SKILLS_AUDIT_RESIDUAL_FIXES.md](../../docs/roadmap/260706_ROADMAP_SKILLS_AUDIT_RESIDUAL_FIXES.md) (5 находок F1-F5; правки кода не применялись — по запросу только карта).
- **Тест:** `lint_skills --strict` 0 err/2 warn; `gen_hooks_catalog --check` OK; pytest 31 passed; агентские отчёты — P0 6/6 FIXED, P1/P2 4/6 FIXED + 2 PARTIAL.
