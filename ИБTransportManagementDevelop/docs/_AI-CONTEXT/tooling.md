# AI-инструменты для разработки в этом проекте

## Slash-команды Claude Code (проектные)

| Команда | Назначение | Output |
|---|---|---|
| `/analyze-1c-task` | 5-фазный анализ задачи (требования → объекты → алгоритм → план → верификация). Запускает skill `analyze-1c-task-v2` | `docs/<JIRA>/ANALYSIS-REPORT.md` |
| `/implement-1c-task` | Реализация по готовому ANALYSIS-REPORT через EDT-MCP (BSL/XML правки) | Изменения в `Конфигурация/src/` + `IMPLEMENTATION-PROGRESS.md` |
| `/write-1c-tests` | Написание Vanessa BDD тестов | `features/*.feature` + `docs/<JIRA>/test-plan.md` |
| `/run-1c-tests` | Прогон BDD с pre-scenario TestDB check, resume через `.run-state.json` | Отчёты в `docs/<JIRA>/` |
| `/audit-docs` | Аудит соответствия кода и документации | Action items |

## MCP-серверы (см. `.mcp.json` в корне фреймворка)

| Сервер | Когда использовать |
|---|---|
| `bsl-semantic-search` | Семантический поиск по BSL-коду (find_callers, search_symbols, get_module_ast). Auto-detect через `.bsl-language-server.json` |
| `bsl-platform-context` | Документация платформы 8.3.27 (объекты, синтаксис) |
| `auto-documenter` | generate_documentation, autoreview, autotestplan, generate_inline_docs |
| `bsl-debugger` | Подключение к процессу 1С, точки останова, stack trace |
| `ast-grep-mcp` | AST-поиск по BSL (структурный matching) |
| `bsl-semantic-diff` | Семантический diff между версиями BSL модулей |
| `1c-mcp-crud` | Прямой доступ к данным/метаданным 1С (execute_query, get_metadata, journal) |

## Жизненный цикл задачи

```
1. ТЗ от заказчика → docs/YYMMDD_GKSTCPLK-NNNN_описание/<тикет>.md
                     (+ скриншоты, PDF при необходимости)
                                  ↓
2. /analyze-1c-task → ANALYSIS-REPORT.md (5 фаз)
                      + DATA-ROADMAP.md (если нужен анализ данных)
                                  ↓
3. /implement-1c-task → правки в Конфигурация/src/
                        IMPLEMENTATION-PROGRESS.md (чек-лист)
                                  ↓
4. /write-1c-tests → features/*.feature + ТЕСТ-N_*.md (сценарии)
                                  ↓
5. /run-1c-tests → BDD прогон, отчёты, .run-state.json
                                  ↓
6. /audit-docs → проверка соответствия (опционально)
                                  ↓
7. Code review (subagent) → REVIEW.md (опционально)
                                  ↓
8. git commit (auto-git-save хук) + post-commit reindex
                                  → bsl_code_v4_late коллекция обновляется
```

## Расширенный pipeline (опционально)

| Стадия | Когда | Артефакт |
|---|---|---|
| 0. Discovery | До анализа, для familiarization | Поиск через `bsl-semantic-search` |
| 6. Performance | Если задача performance-critical | `docs/<JIRA>/benchmark.md` |
| 9. Deployment notes | При обновлении прод-БД | `docs/<JIRA>/DEPLOYMENT.md` |
| 10. Changelog | После завершения | `docs/<JIRA>/CHANGELOG.md` |

## AI-контекст для агентов

`docs/_AI-CONTEXT/` (этот каталог) — стабильный контекст проекта:

- `project-context.md` — кто/что/зачем проект
- `tooling.md` — этот файл (инструменты + lifecycle)
- `coding-conventions.md` — правила именования, стиль BSL
- `lifecycle.md` — детальный lifecycle с шаблонами prompt'ов

`docs/_HISTORY/` — архив рабочих заметок прошлых сессий:

- `analysis-GKSTCPLK-NNNN.md` — артефакты конкретных задач (исторические)
- `session-status-YYYY-MM-DD.md` — снапшоты состояния сессий
- `troubleshooting-*.md` — решения проблем окружения

## Refactoring BSL

Используй skill `bsl-refactoring-workflow` (5-категорийная матрица выбора
инструмента) + `bsl-symbol-editing` (symbol-anchored правки через EDT-MCP).
Для переименования символов — `mcp__bsl-semantic-search__bsl_rename_symbol`.

## Vanessa Automation (BDD)

- Runner: `tools/vanessa/run-bdd.ps1 -OutputJson -RunId` (в корне фреймворка)
- Skill: `va-bdd-testing` v1.1 (Stage 4a: pre-scenario TestDB check)
- Тесты: `features/*.feature` (gherkin-синтаксис)
- Калибровка шагов: см. `.claude/skills/va-bdd-testing/`
