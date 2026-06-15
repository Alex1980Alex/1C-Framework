# Единый task-completion gate 1С — pipeline (medium, консолидация)

**План.** Пользователь: единый task-completion gate (все петли 1С-задачи разом, без 3-каскада).
**Дизайн.** `onec-task-completion-stop.py` — ОДИН Stop-хук: один проход по транскрипту → {recall, capture,
research, skill}; блок ОДИН раз с консолидированным чеклистом (✓/✗ по каждой петле). Hard: recall+capture+research;
SKILL — info (уже enforced code-skill-enforcer на Write). Пайплайн — отдельный концерн (pipeline-protocol-stop).
**Заменяет** memory-protocol-stop + research-protocol-stop (удалены) — убирает каскад. Reuse предиката
`is_1c_task_title` (N4) + tail 8МБ (N3) + capture-.claude (N6). Opt-out ONEC_TASK_GATE_DISABLE=1.
**Реализация.** Новый хук + регистрация в settings.json (вместо 2) + удаление 2 хуков + 2 тестов + новый тест +
N1-превью в pipeline-protocol-stop → единый gate.
**Тест.** 7 unit (агрегатор) + 42 (с bridge) + e2e: partial→block с чеклистом (exit 2), all→allow (exit 0),
live не-1С→exit 0. code-verify.
