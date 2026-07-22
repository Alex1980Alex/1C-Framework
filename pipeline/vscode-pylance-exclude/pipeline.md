# Trivial: exclude-пути Pylance для воркспейса

**Дата:** 2026-07-22
**Класс:** trivial (1 новый конфиг-файл, нет продуктового кода)

## Задача
Pylance показал предупреждение «found a large number of source files in this workspace».
Причина: в анализ попадали вендоренные и не-Python деревья (`.venv`, `tools/`, `external/`,
`infra/`, `.claude/worktrees/`, `src/bsl/exts/`, `configuration/`, `data/`, `cache/`).

## Решение
Создан [.vscode/settings.json](../../.vscode/settings.json):
- `python.analysis.exclude` — вендоренное вне анализа Pylance
- `files.watcherExclude` — снятие нагрузки файлового вотчера
- `search.exclude` — чище результаты поиска

Скоуп анализа сохранён для `src/`, `scripts/`, `.claude/hooks/` — автодополнение и типы целы.

## Проверка
Применяется после Developer: Reload Window в VS Code. Кода не тронуто, тестов не требуется.
