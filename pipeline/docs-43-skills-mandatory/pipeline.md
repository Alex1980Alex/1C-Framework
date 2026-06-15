# Обязательное использование системы скиллов (гл.11) в 43.4 — pipeline (trivial)

**План.** Пользователь: система скиллов (гл.11) тоже обязательна + зафиксирована в 43.4 с логированием и
оценкой эффективности (по аналогии с памятью гл.27 + W).
**Дизайн.** Документировать (новый хук НЕ нужен — обязательность уже enforced `code-skill-enforcer`): в 43.4
строка «Система скиллов — ОБЯЗАТЕЛЬНО» в Сквозных + раздел «Обязательное использование системы скиллов»
(skill-на-этап + лог + оценка) + строка в шаблоне TOOL-PLAN.
**Реализация.** 3 правки 43.4. Заземлено на реальные механизмы: лог `skill-accuracy.jsonl`
(posttooluse-skill-metrics + db_writer) / `session-skills.json` / `skill-router.log`; оценка
`skill_system_acceptance.py` / `eval-skill-router.py` / `skill-quality-monitor.py` /
`skill-enforcement-dashboard.py` + `skill-health-report.md` (гл.11.7); enforcement `code-skill-enforcer`.
**Тест.** Ссылки 11.1/11.7 + скрипты/хуки существуют; fence-баланс чётный.
