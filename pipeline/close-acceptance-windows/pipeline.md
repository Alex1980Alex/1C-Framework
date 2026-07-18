# Закрытие 4 acceptance-окон (trivial)

**Задача:** прогнать `--final` по 4 acceptance-скриптам и зафиксировать «Acceptance вердикт: PASS» в §18 соответствующих роадмапов/ADR, чтобы SessionStart-баннеры замолчали.

**Классификация:** trivial (документационная правка, без изменения кода/поведения).

## Выполнено
- `onec_toolgate_validation.py --final` → PASS (keep-advisory) → ADR-035 §18
- `skill_learning_acceptance.py --final` → PASS (5/5) → 260611 §18
- `tdd_guard_validation.py --final` → PASS (keep-advisory) → 260613 §18
- `skill_system_acceptance.py --final` → PASS (9/9) → 260612 §18

## Проверка
Маркер «Acceptance вердикт» присутствует в §18 всех 4 файлов → баннеры замолчат со следующей сессии. Правки — только Markdown, runtime-поведение не затронуто.
