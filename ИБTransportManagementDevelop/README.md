# ИБTransportManagementDevelop

EDT-проект 1С:Предприятие 8.3.27 для разработки и сопровождения функционала
**управления транспортом на ПЛК** (Промышленно-логистический комплекс).

Подключён к фреймворку через маркер [`.bsl-language-server.json`](.bsl-language-server.json)
с `configurationRoot: "Конфигурация/src"`.

---

## Структура проекта

```
ИБTransportManagementDevelop/
├── .bsl-language-server.json   ← Маркер BSL-проекта (configurationRoot)
├── .gitignore                   ← Игнор-правила для 1С + Python + EDT
├── .metadata/                   ← EDT/Eclipse workspace (НЕ редактировать)
├── .vscode/                     ← VS Code workspace
│   ├── settings.json            ← Python interpreter
│   ├── extensions.json          ← Рекомендуемые расширения
│   └── tasks.json               ← Задачи: Конфигуратор, BDD, BSL LS
├── Конфигурация/                ← EDT project (BSL/XML конфигурация 1С)
│   ├── .project                 ← Eclipse marker
│   ├── DT-INF/                  ← EDT internal
│   └── src/                     ← Catalogs/, Documents/, CommonModules/, ...
├── docs/                        ← ТЗ + анализы + прогрессы по Jira-задачам
│   ├── _AI-CONTEXT/             ← Контекст проекта для AI-агентов
│   │   ├── project-context.md   ← Что за проект, зачем
│   │   ├── tooling.md           ← Инструменты и lifecycle
│   │   ├── coding-conventions.md ← Стиль BSL
│   │   └── lifecycle.md         ← 8-стадийный pipeline задач
│   ├── _HISTORY/                ← Архив заметок прошлых сессий
│   ├── _TEMPLATE/               ← Шаблон новой задачи (копируй и переименовывай)
│   └── <YYMMDD>_<JIRA>/         ← Папка конкретной задачи
├── features/                    ← Vanessa BDD `.feature` файлы
└── scripts/                     ← Per-project автоматизация
    ├── build_benchmark_tasks.py
    ├── diag_testdb.os
    └── PROMPT-TEMPLATE-1C-TASK-ANALYSIS.md
```

---

## Жизненный цикл задачи (8 стадий)

```
0. Discovery (опц.) → 1. Analysis → 2. Design (опц.) → 3. Implementation
   → 4. Testing → 5. Review (опц.) → 6. Audit → 7. Deployment (опц.)
```

| Стадия | Slash-команда | Output |
|---|---|---|
| 0 | — (поиск через MCP) | Контекст |
| 1 | `/analyze-1c-task` | `docs/<JIRA>/ANALYSIS-REPORT.md` |
| 2 | (OpenSpec / brownfield-validate) | `DESIGN.md` |
| 3 | `/implement-1c-task` | BSL/XML правки + `IMPLEMENTATION-PROGRESS.md` |
| 4 | `/write-1c-tests` + `/run-1c-tests` | `features/*.feature` + `test-plan.md` |
| 5 | code-verify subagent | `REVIEW.md` |
| 6 | `/audit-docs` | Action items |
| 7 | вручную | `DEPLOYMENT.md` + `*.cf` |

Подробности — в [`docs/_AI-CONTEXT/lifecycle.md`](docs/_AI-CONTEXT/lifecycle.md).

---

## Как начать новую задачу

```bash
# 1. Скопировать шаблон
cp -r docs/_TEMPLATE "docs/260502_GKSTCPLK-2400 Краткое описание"

# 2. Положить ТЗ
# вставить ТЗ в файл "<тикет>.md" внутри новой папки

# 3. Запустить анализ
# В Claude Code: /analyze-1c-task

# 4. После анализа — реализовать
# В Claude Code: /implement-1c-task

# 5. Тесты
# В Claude Code: /write-1c-tests, потом /run-1c-tests
```

---

## AI-инструменты

### Slash-команды Claude Code (проектные)

- `/analyze-1c-task` — 5-фазный анализ
- `/implement-1c-task` — реализация по ANALYSIS-REPORT
- `/write-1c-tests` — Vanessa BDD .feature
- `/run-1c-tests` — прогон BDD с resume
- `/audit-docs` — аудит соответствия документации

### MCP-серверы (см. `.mcp.json` в корне фреймворка)

| Сервер | Используется для |
|---|---|
| `bsl-semantic-search` | Поиск по BSL коду (callers, symbols, AST) |
| `bsl-platform-context` | Документация платформы 8.3.27 |
| `auto-documenter` | autoreview, autotestplan, generate_documentation |
| `bsl-debugger` | Отладка процессов 1С |
| `1c-mcp-crud` | Прямые запросы к данным 1С |
| `ast-grep-mcp` | Структурный поиск по BSL AST |
| `bsl-semantic-diff` | Семантический diff BSL модулей |

### Skills

- `analyze-1c-task-v2` — v4 SDD-методология
- `bsl-development` — общие правила BSL
- `bsl-symbol-editing` — symbol-anchored правки через EDT-MCP
- `bsl-refactoring-workflow` — 5-категорийная матрица refactoring
- `va-bdd-testing` v1.1 — BDD тесты (Stage 4a TestDB check)
- `code-verify` — 4 режима верификации
- `1c-doc-research` — research по документации платформы

---

## Подключение к ИБ

```
SQL Server:    localhost (default instance)
БД:            ИБTransportManagementDevelop
sa-пароль:     <см. password manager>
Платформа:     1С:Предприятие 8.3.27.1936
Кластер 1С:    localhost:1541
Драйвер:       Microsoft OLE DB Driver 19 (MSOLEDBSQL19)
```

Из VS Code: `Ctrl+Shift+P → Tasks: Run Task → 1С: Открыть Конфигуратор`.

---

## Связь с фреймворком

Этот EDT-проект — стандартный BSL-проект, обнаруживается фреймворком через
`.bsl-language-server.json` маркер. Подробности интеграции — в
[`docs/_AI-CONTEXT/tooling.md`](docs/_AI-CONTEXT/tooling.md).

После каждого `git commit` BSL-файла → автоматический реиндекс
`bsl_code_v4_late` коллекции через post-commit хук.
