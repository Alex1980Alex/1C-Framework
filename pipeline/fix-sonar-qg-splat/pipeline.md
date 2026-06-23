# Fix run-sonar-analysis.ps1 — qgArgs splatting bug

Trivial-фикс (1 строка + комментарий) в `scripts/run-sonar-analysis.ps1`.

## 1. Планирование
Симптом: пост-шаг Quality Gate в `run-sonar-analysis.ps1` падал exit≠0 (`argparse: unrecognized arguments: - - s o f t`), хотя Sonar-анализ загружался успешно. Корень найден воспроизведением точного вызова.

## 2. Дизайн
Корень: splat `@qgArgs` к НАТИВНОЙ python.exe в PowerShell 5.1 рвёт строку `"--soft"` на символы. `sonar_quality_gate_check.py` корректен (уже принимает `--soft`). Фикс — в wrapper: `@qgArgs` → `$qgArgs` (array-expansion) + комментарий против регресса. Минимальный diff, поведение сохранить. Approved.

## 3. Кодирование
Edit строки 49→51: `@qgArgs` → `$qgArgs` + 2 строки комментария. Никаких посторонних правок.

## 4. Тестирование
- Эмпирический регресс-тест: SOFT (`SONAR_QG_HARD` не задан) → **exit 0** (warn); HARD (`SONAR_QG_HARD=1`) → **exit 1** (валит на QG=ERROR). Поведение режимов сохранено.
- code-verify reviewer (bug-fix-validation): **PASS** (корень, минимальность, граничный `@()`, нет других splat-багов, анти-регресс-комментарий).

## Capture
skill-learning: «PowerShell 5.1 $arr vs @arr для нативных команд».
