# Команды Claude Code в проекте PDF Vector & Graph Framework

Полный реестр всех slash-команд, доступных в этом проекте. Разделён на две части:

1. **Кастомные команды проекта** — наши, лежат в `.claude/commands/`
2. **Встроенные команды Claude Code CLI** — поставляются с самим Claude Code

> Кастомные команды видны через автодополнение `/` в Claude Code и работают только в рамках этого проекта (либо при активации соответствующего плагина / маркетплейса).

---

## 1. Кастомные команды проекта (наши)

Файлы: [.claude/commands/](../../.claude/commands/)

| Команда | Файл | Назначение |
|---------|------|------------|
| `/activate-project <имя\|тикет\|путь>` | [activate-project.md](../../.claude/commands/activate-project.md) | Активация проекта в Serena (LSP-навигация, `.serena/memories/`). Опциональна — нужна только для Python-кода фреймворка через Serena LSP-инструменты. На BSL не работает (LSP отсутствует). |
| `/analyze-1c-task <ТЗ + путь к src> [--trace]` | [analyze-1c-task.md](../../.claude/commands/analyze-1c-task.md) | Комплексный анализ задачи 1С по 5-фазной методологии (Требования → Объекты → **[опц. Фаза 2.5 Runtime Trace]** → Алгоритм → План → Верификация). Создаёт `ANALYSIS-REPORT.md` с точками модификации. Использует skill `analyze-1c-task-v2` v4.2.0. **Флаг `--trace`** (или self-decision при ≥3 ветвлений по runtime-данным) активирует Фазу 2.5: live BP-trace через `1c-debug-hmr` для алгоритмов с условиями по `Пользователи.ТекущийПользователь()`, `ПолучитьФункциональнуюОпцию`, `Тип(Параметр)`. Output: секция «3.Y Runtime Trace» с Entry/Stack/Variables/Branch evaluation/**Discrepancies** (static vs runtime). |
| `/implement-1c-task <ANALYSIS-REPORT + src>` | [implement-1c-task.md](../../.claude/commands/implement-1c-task.md) | Реализация задачи 1С по готовому `ANALYSIS-REPORT.md` (8-этапный pipeline). Через EDT-MCP + 1c-mcp-crud + bsl-debug-server + **1c-debug-hmr** (live BP-verification). Обязательные циклы: `validate_query` → `execute_query` ДО записи; `get_project_errors` ПОСЛЕ записи; `update_database` ПЕРЕД Этапом 6 (live-вызов изменённой функции); **`debug_set_breakpoint` → trigger → `debug_stack_trace` (assert lineNo) → `debug_step(Continue)` для каждой `[MODIFIED]` точки в Этапе 5.x (режим Full)**. **Режимы pipeline:** Full (все 4 сервера) / Full (no-BP) (debug-hmr недоступен — BP-verification SKIP) / Code-only / Read-only verify / Read-only research. **Требования к среде:** EDT IDE с MCP-плагином на `:8765`, 1С HTTP-сервис `MCP_Сервер` опубликован, `.mcp.json:1c-mcp-crud` с валидным паролем — см. [16.6 EDT-MCP setup](3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md). Smoke-test: `python scripts/smoke_test_implement_1c_task.py` (поле `mcp_health.debug_hmr` в `--json`). **Известные ограничения 1c-mcp-crud (v2.5):** `get_metadata` для регистров возвращает пустой `attributes:[]` (workaround — `execute_query`); `execute_query` падает на сериализации композитных ссылочных типов (workaround — `ПРЕДСТАВЛЕНИЕ()`). Skill: `implement-1c-task` v2.7.0 (2026-05-11 debug-hmr integration). |
| `/pdf-search <запрос>` | [pdf-search.md](../../.claude/commands/pdf-search.md) | Семантический и графовый поиск по индексированным PDF-документам через PDF Vector & Graph Framework. Использует `mcp__pdf-vector-graph__search_documents` / `hybrid_search`. |
| `/write-1c-tests <TEST-PLAN + src>` | [write-1c-tests.md](../../.claude/commands/write-1c-tests.md) | Написание VA BDD тестов (Vanessa Automation) по готовому `TEST-PLAN-DETAILED.md`. 4 фазы: анализ формы → объектная модель → VA docs / API платформы → написание `.feature`. Использует skill `va-bdd-testing`. |
| `/run-1c-tests <папка features> [флаги]` | [run-1c-tests.md](../../.claude/commands/run-1c-tests.md) | Цепочный прогон VA BDD тестов с переиспользованием артефактов между секциями, `pre-scenario` TestDB check, `.run-state.json`, auto-retry транзиентных ошибок, auto-fix типовых ошибок. Флаги: `--section`, `--from`, `--fresh`, `--dry-run`, `--timeout`, `--retries`, `--fix-mode`. |
| `/opsx:propose <название\|описание>` | [opsx/propose.md](../../.claude/commands/opsx/propose.md) | OpenSpec (экспериментальный workflow): создать новый change и сгенерировать все артефакты за один шаг — `proposal.md` (что/зачем), `design.md` (как), `tasks.md` (шаги реализации). |
| `/opsx:apply [имя change]` | [opsx/apply.md](../../.claude/commands/opsx/apply.md) | OpenSpec: реализовать задачи из готового change. Если имя не указано — пытается извлечь из контекста или предлагает выбрать. |
| `/opsx:explore [тема]` | [opsx/explore.md](../../.claude/commands/opsx/explore.md) | OpenSpec: режим исследования. Размышление, поиск информации, прояснение требований — БЕЗ написания кода. Можно создавать только OpenSpec-артефакты (proposals, designs, specs). |
| `/opsx:archive [имя change]` | [opsx/archive.md](../../.claude/commands/opsx/archive.md) | OpenSpec: финализировать и архивировать завершённый change после реализации. |
| `/run-1c-task <JIRA\|описание\|путь>` | [run-1c-task.md](../../.claude/commands/run-1c-task.md) | AUTO-оркестратор 1С-задачи: прогон analyze→implement→test **без паузы** на ревью первого этапа. Вход определяется автоматически (JIRA-код / описание из чата / путь к папке ТЗ). Для ревью `ANALYSIS-REPORT` перед кодом — гейтованный `/analyze-1c-task` → `/implement-1c-task`. Skill `run-1c-task`. |
| `/write-1c-unit-tests <TEST-PLAN + src>` | [write-1c-unit-tests.md](../../.claude/commands/write-1c-unit-tests.md) | Написание YAxUnit unit-тестов серверной бизнес-логики по TEST-PLAN / папке задачи. Запускать ПОСЛЕ `/implement-1c-task`. Пишет тест-модули BSL в расширение `UnitTests`; прогон — `/run-1c-unit-tests`. Skill `yaxunit-unit-testing`. |
| `/run-1c-unit-tests <модуль\|расширение>` | [run-1c-unit-tests.md](../../.claude/commands/run-1c-unit-tests.md) | Прогон YAxUnit unit-тестов через `mcp-onec-test-runner` (`run_module_tests` / `run_all_tests`), парсинг JUnit → `.run-state.json` (формат `chain[]`, как у BDD-трека). Этап 4 пайплайна. Только запускает. |
| `/fix-sonar-task [severities/types/path]` | [fix-sonar-task.md](../../.claude/commands/fix-sonar-task.md) | Обработка Sonar-дефектов **через 1С-пайплайн** (pull→триаж→`/analyze-1c-task`→`/implement-1c-task`→`/run-1c-tests`→re-scan). Sonar-issue НИКОГДА не фиксится ad-hoc. Дефолт-фильтр — BLOCKER+CRITICAL. Skill `fix-sonar-task`. |
| `/pl-plan <задача>` | [pl-plan.md](../../.claude/commands/pl-plan.md) | Generic 4-stage pipeline (ADR-017, домен-агностичный, **НЕ** 1С-цепочка), Этап 1 — Планирование архитектуры. Артефакт `pipeline/<task>/01-architecture.md`. Делегирует `architecture-research`. |
| `/pl-design <задача>` | [pl-design.md](../../.claude/commands/pl-design.md) | Generic pipeline, Этап 2 — Дизайн реализации. Артефакт `pipeline/<task>/02-design.md` (нужен approve перед кодированием). |
| `/pl-code <задача>` | [pl-code.md](../../.claude/commands/pl-code.md) | Generic pipeline, Этап 3 — Кодирование (**gated**: `02-design.md` должен быть одобрен, hard-гейт `pipeline-gate.py`). Артефакт `pipeline/<task>/03-implementation.md`. |
| `/pl-test <задача>` | [pl-test.md](../../.claude/commands/pl-test.md) | Generic pipeline, Этап 4 — Тестирование. Артефакт `pipeline/<task>/04-testing.md`. Делегирует `code-verify`. |
| `/cc-docs <запрос>` | [cc-docs.md](../../.claude/commands/cc-docs.md) | Семантический поиск по документации Claude Code (code.claude.com/docs) со свежестью (sitemap lastmod): CLI/SDK/hooks/subagents/settings/permissions/MCP/plugins. Skill `cc-docs`, `scripts/cc_docs_search.py`. |

### Типовой 1С-пайплайн (последовательная цепочка)

```
/analyze-1c-task <ТЗ + src>
        ↓
ANALYSIS-REPORT.md
        ↓
/implement-1c-task <ANALYSIS-REPORT + src>
        ↓
BSL/XML изменения + IMPLEMENTATION-PROGRESS.md
        ↓
/write-1c-tests <TEST-PLAN + src>
        ↓
features/<task-slug>/*.feature
        ↓
/run-1c-tests features/<task-slug>/
        ↓
.run-state.json + JUnit XML + отчёт
```

Подробности: [17.5 Команды 1С Pipeline](7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.5_КОМАНДЫ_ПАЙПЛАЙНА.md).

### OpenSpec-цикл

```
/opsx:explore <тема>          # размышляем
        ↓
/opsx:propose <название>      # фиксируем proposal + design + tasks
        ↓
/opsx:apply <название>        # реализуем
        ↓
/opsx:archive <название>      # архивируем
```

---

## 2. Встроенные команды Claude Code CLI

Поставляются с самим Claude Code (CLI). Работают в любом проекте.

### 2.1 Slash-команды интерактивного режима

| Команда | Назначение |
|---------|------------|
| `/help` | Помощь по использованию Claude Code |
| `/clear` | Очистить историю разговора в текущей сессии |
| `/compact [focus]` | Компактировать контекст (сжать прошлые сообщения, опционально с фокусом) |
| `/config` | Открыть редактор настроек |
| `/context` | Визуализация занятости контекстного окна |
| `/cost` | Статистика токенов и стоимости текущей сессии |
| `/doctor` | Проверка здоровья установки Claude Code |
| `/exit` | Выйти из CLI |
| `/export [file]` | Экспорт разговора в файл (markdown / JSON) |
| `/init` | Создать `CLAUDE.md` в корне проекта (стартовая документация для Claude) |
| `/mcp` | Управление MCP-серверами (список, добавить, удалить, статус) |
| `/memory` | Открыть редактор `CLAUDE.md` (память проекта) |
| `/model` | Сменить модель (Opus / Sonnet / Haiku) |
| `/permissions` | Управление разрешениями (allowedTools / disallowedTools) |
| `/plan` | Включить режим планирования (Plan Mode) |
| `/rename <name>` | Переименовать текущую сессию |
| `/resume` | Возобновить предыдущую сессию по ID/имени |
| `/rewind` | Откатить разговор / код / и то и другое (Checkpoints) |
| `/stats` | Статистика использования (за период) |
| `/statusline` | Настроить кастомную строку состояния |
| `/tasks` | Список фоновых задач (`Ctrl+B` ставит задачу в фон) |
| `/theme` | Сменить цветовую тему |
| `/todos` | Список TODO текущей сессии |
| `/vim` | Включить Vim mode для ввода |
| `/agents` | Управление подагентами (`.claude/agents/`) |
| `/hooks` | Управление хуками (`.claude/hooks/`) |
| `/review` | Ревью pull request |
| `/security-review` | Полный security-review текущей ветки |
| `/login` / `/logout` | Аутентификация |
| `/upgrade` | Обновить тарифный план |
| `/bug` | Отправить bug-report в Anthropic |
| `/add-dir <path>` | Добавить дополнительную директорию в скоуп Claude |
| `/ide` | Управление интеграцией с IDE (VS Code / JetBrains) |

### 2.2 Префиксы быстрых команд (в строке ввода)

| Префикс | Действие |
|---------|----------|
| `/` | Slash-команда или skill |
| `!` | Bash-режим: выполнить команду напрямую, добавить вывод в контекст |
| `@` | Автодополнение пути к файлу |

### 2.3 Команды CLI (запуск из shell)

| Команда | Назначение |
|---------|------------|
| `claude` | Открыть интерактивный REPL |
| `claude "query"` | REPL с начальным запросом |
| `claude -p "query"` | Headless mode (одноразовый запрос, без интерактива) |
| `cat file \| claude -p "query"` | Pipe содержимого файла в Claude |
| `claude -c` | Продолжить последний разговор |
| `claude -r "<id\|name>" "query"` | Возобновить сессию по ID или имени |
| `claude update` | Обновить версию Claude Code |
| `claude mcp` | Настройка MCP-серверов из CLI |

### 2.4 Ключевые флаги CLI

#### Режимы работы

| Флаг | Назначение |
|------|------------|
| `-p, --print` | Headless (без интерактива) |
| `-c, --continue` | Продолжить последний разговор |
| `-r, --resume <id>` | Возобновить сессию |
| `--model <name>` | Модель: `sonnet`, `opus`, `haiku` |
| `--agent <name>` | Использовать подагента |
| `--agents '<json>'` | Inline-определение подагентов |
| `--fallback-model sonnet` | Fallback при перегрузке основной модели |

#### Разрешения и инструменты

| Флаг | Назначение |
|------|------------|
| `--allowedTools "Tool1" "Tool2"` | Авто-одобренные инструменты |
| `--disallowedTools "Tool"` | Запрещённые инструменты |
| `--tools "Bash,Edit,Read"` | Ограничить набор инструментов |
| `--permission-mode <mode>` | Режим разрешений (default / acceptEdits / bypassPermissions / plan) |
| `--dangerously-skip-permissions` | Пропустить ВСЕ проверки (опасно) |

#### Вывод и формат

| Флаг | Назначение |
|------|------------|
| `--output-format text\|json\|stream-json` | Формат вывода (для headless) |
| `--json-schema '<schema>'` | Структурированный вывод по JSON Schema |
| `--verbose` | Подробное логирование |
| `--debug "api,hooks"` | Отладка по категориям |

#### Системный промпт

| Флаг | Назначение |
|------|------------|
| `--system-prompt "text"` | Заменить весь системный промпт |
| `--system-prompt-file ./file.txt` | Заменить системный промпт из файла |
| `--append-system-prompt "text"` | Добавить к дефолтному |
| `--append-system-prompt-file ./file.txt` | Добавить из файла |

#### Прочие

| Флаг | Назначение |
|------|------------|
| `--add-dir ../lib` | Дополнительные директории в скоуп |
| `--max-turns 5` | Макс. ходов (для headless) |
| `--max-budget-usd 5.00` | Макс. бюджет в USD (для headless) |
| `--mcp-config ./mcp.json` | Путь к MCP-конфигу |
| `--plugin-dir ./plugins` | Директория плагинов |
| `--chrome` | Интеграция с Chrome |
| `--remote "task"` | Создать веб-сессию на claude.ai |

### 2.5 Горячие клавиши

| Клавиша | Действие |
|---------|----------|
| `Ctrl+C` | Отменить ввод/генерацию |
| `Ctrl+D` | Выход |
| `Ctrl+G` | Открыть ввод во внешнем редакторе |
| `Ctrl+L` | Очистить экран |
| `Ctrl+O` | Toggle подробного вывода |
| `Ctrl+R` | Поиск по истории |
| `Ctrl+V` | Вставить изображение из буфера |
| `Ctrl+B` | Перевести задачу в фон (в tmux — двойное нажатие) |
| `Ctrl+T` | Toggle списка задач |
| `Esc + Esc` | Rewind (откат кода/разговора) |
| `Shift+Tab` | Переключить Permission Mode |
| `Alt+P` | Переключить модель |
| `Alt+T` | Toggle расширенного мышления |

### 2.6 Многострочный ввод

| Метод | Клавиша |
|-------|---------|
| Универсальный | `\` + `Enter` |
| macOS | `Option+Enter` |
| iTerm2 / WezTerm / Ghostty / Kitty | `Shift+Enter` |
| Управляющий символ | `Ctrl+J` |

---

## Источники

- Кастомные команды: [`.claude/commands/`](../../.claude/commands/)
- Документация Claude Code: [`docs/documentation/Claude Code Docs/`](../documentation/Claude%20Code%20Docs/)
- Skill: [`claude-code-cli-interactive`](../../.claude/skills/claude-code-cli-interactive/SKILL.md) — справка по CLI и интерактиву
- Skill: [`claude-code-settings`](../../.claude/skills/claude-code-settings/SKILL.md) — конфигурация settings.json и CLAUDE.md
- 1С-пайплайн: [17.5_КОМАНДЫ_ПАЙПЛАЙНА.md](7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.5_КОМАНДЫ_ПАЙПЛАЙНА.md)
