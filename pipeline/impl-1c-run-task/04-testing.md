# /run-1c-task — Тестирование (этап 4, DoD пройден)

| Проверка | DoD | Результат |
|---|---|---|
| unit (новые) | pytest | **18 passed** (14 прежних + 4 `resolve_task_input`) |
| collision-immune | full `-m unit -k "pipeline or tool_usage"` | **51 passed, 1 skipped, 0 collision** (importlib-загрузка моста) |
| ruff / compile | clean | All checks passed / compile OK |
| live `resolve_task_input` | 3 кейса | `GKSTCPLK-2182…`→**jira**; `pipeline/impl-1c-run-task`→**folder** (slug из имени); `исправить…`→**chat** (slug `1c-task`) |
| skill discovery | available-skills | `run-1c-task` зарегистрирован (виден в системном списке скиллов) |
| команда | формат | `/run-1c-task` создан по образцу `implement-1c-task.md` (frontmatter + `$ARGUMENTS` + делегирование скиллу) |

**Вердикт: DONE.** AUTO-режим `/run-1c-task <вход>` собран: одна команда прогоняет analyze→approve(авто)→implement→test
без паузы; вход (JIRA / описание / папка ТЗ) детектится автоматически. Гейтованный поток B′ не затронут.

**Граница (честно):** оркестрация 4 этапов — инструкция скиллу (Claude исполняет: активирует analyze-1c-task-v2 /
implement-1c-task / va-bdd-testing по подсказке). Юнит-тесты покрывают `resolve_task_input` (детект входа); реальный
сквозной прогон 4 этапов на живой 1С-задаче — операторская приёмка (предложена отдельно). Авто-approve = осознанный
обход ревью с хард-правилом «стоп на критическом блокере».
