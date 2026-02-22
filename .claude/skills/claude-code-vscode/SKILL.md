---
name: claude-code-vscode
description: "Claude Code в VS Code: расширение, настройки, shortcuts, @-mentions, plugins UI, diff review, MCP интеграция, git worktrees, несколько бесед, CLI vs Extension. Триггеры: 'VS Code', 'vscode', 'расширение claude', 'extension', 'vscode extension', 'Open in New Tab', '@-mention', '@-упоминание', 'Spark icon', 'permission mode', 'acceptEdits', 'bypassPermissions', 'selectedModel', 'useTerminal', 'autosave', 'preferredLocation', 'Cmd+Esc', 'Ctrl+Esc', 'Option+K', 'Alt+K', 'diff view', 'plan mode vscode', 'worktree', 'remote session', 'Claude.ai session'. НЕ для CLI-команд терминала — используй claude-code-cli-interactive. НЕ для settings.json scopes — используй claude-code-settings."
---

# Claude Code в VS Code

## Предварительные требования

- VS Code **1.98.0+**
- Учетная запись Anthropic (или third-party: Bedrock / Vertex AI / Foundry)

## Установка

| IDE | Способ |
|-----|--------|
| VS Code | `Cmd+Shift+X` → "Claude Code" → Install |
| VS Code (прямая) | [vscode:extension/anthropic.claude-code](vscode:extension/anthropic.claude-code) |
| Cursor | [cursor:extension/anthropic.claude-code](cursor:extension/anthropic.claude-code) |

После установки: если не появляется — "Developer: Reload Window" из палитры команд.

## Открытие панели Claude

| Способ | Действие |
|--------|----------|
| **Spark icon** | Значок в панели инструментов редактора (верхний правый, нужен открытый файл) |
| **Палитра команд** | `Cmd+Shift+P` / `Ctrl+Shift+P` → "Claude Code" |
| **Строка состояния** | Клик на "Claude Code" внизу справа (работает без открытого файла) |

## Поле ввода запроса

### Режимы разрешений

Индикатор внизу поля ввода. Настройка по умолчанию: `claudeCode.initialPermissionMode`.

| Режим | Поведение |
|-------|-----------|
| **Default** | Claude спрашивает перед каждым действием |
| **Plan** | Claude описывает план → ждет одобрения → выполняет |
| **Accept Edits** | Claude вносит правки без запроса |
| **Bypass Permissions** | Без запросов вообще (осторожно!) |

### Меню команд

Нажмите `/` в поле ввода:
- Присоединить файлы
- Переключить модель (`/model`)
- Расширенное мышление (toggle)
- Использование (`/usage`)
- Настройка: MCP servers, hooks, память, разрешения, plugins

### @-mentions (ссылки на файлы и папки)

```
@auth              → fuzzy match: auth.js, AuthService.ts, ...
@src/components/   → папка (trailing slash)
@app.ts#5-10       → файл + диапазон строк
```

- Выделенный текст виден Claude автоматически
- `Option+K` (Mac) / `Alt+K` (Win/Linux) — вставить @-mention текущего файла и выделения
- Индикатор выделения: клик → скрыть/показать выделение от Claude
- `Shift` + drag файлов → вложения; X на вложении → удалить

### Контекст и компактирование

Индикатор контекста показывает использование контекстного окна. Автоматическое компактирование при необходимости, или `/compact` вручную.

### Многострочный ввод

`Shift+Enter` — новая строка без отправки.

## Команды и сочетания клавиш VS Code

| Команда | Shortcut (Mac / Win) | Описание |
|---------|----------------------|----------|
| Focus Input | `Cmd+Esc` / `Ctrl+Esc` | Переключение фокуса редактор ↔ Claude |
| Open in Side Bar | — | Claude в левой боковой панели |
| Open in Terminal | — | Claude в режиме терминала |
| Open in New Tab | `Cmd+Shift+Esc` / `Ctrl+Shift+Esc` | Новая беседа как вкладка |
| Open in New Window | — | Новая беседа в отдельном окне |
| New Conversation | `Cmd+N` / `Ctrl+N` | Новая беседа (фокус Claude) |
| Insert @-Mention | `Option+K` / `Alt+K` | Ссылка на файл+выделение (фокус редактора) |
| Show Logs | — | Журналы отладки расширения |
| Logout | — | Выход из учетной записи |

## Параметры расширения VS Code

Открыть: `Cmd+,` / `Ctrl+,` → Extensions → Claude Code. Или `/` → **General Config**.

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `selectedModel` | `default` | Модель для новых бесед. `/model` для смены в сеансе |
| `useTerminal` | `false` | Режим терминала вместо графической панели |
| `initialPermissionMode` | `default` | `default` / `plan` / `acceptEdits` / `bypassPermissions` |
| `preferredLocation` | `panel` | `sidebar` (справа) или `panel` (вкладка) |
| `autosave` | `true` | Авто-сохранение файлов перед чтением/записью Claude |
| `useCtrlEnterToSend` | `false` | Ctrl/Cmd+Enter вместо Enter для отправки |
| `enableNewConversationShortcut` | `true` | Cmd/Ctrl+N для новой беседы |
| `hideOnboarding` | `false` | Скрыть контрольный список адаптации |
| `respectGitIgnore` | `true` | Исключить .gitignore паттерны из поиска |
| `environmentVariables` | `[]` | Env-переменные для процесса Claude |
| `disableLoginPrompt` | `false` | Пропустить запросы аутентификации |
| `allowDangerouslySkipPermissions` | `false` | Обойти ВСЕ разрешения |
| `claudeProcessWrapper` | — | Путь исполняемого для запуска процесса Claude |

## Настройка рабочего процесса

### Расположение панели

Перетащите панель Claude в:
- **Вторичная боковая панель** (справа) — видим во время кодирования
- **Основная боковая панель** (слева) — рядом с Explorer/Search
- **Область редактора** — вкладка рядом с файлами

Spark icon в Activity Bar появляется только при закреплении панели слева.

### Несколько бесед

`Open in New Tab` / `Open in New Window` из палитры команд. Каждая беседа имеет свою историю и контекст.

Цветные точки на вкладках:
- **Синий** — ожидается разрешение
- **Оранжевый** — Claude закончил (вкладка была скрыта)

### Возобновление прошлых бесед

Раскрывающееся меню вверху панели → поиск по ключевому слову / время.

### Возобновление удалённых сеансов (Claude.ai)

Требует вход через **Claude.ai Subscription** (не Anthropic Console):
1. Меню Past Conversations → вкладка **Remote**
2. Выбрать сеанс → загружается локально

Только сеансы, начатые с GitHub-репо. Изменения НЕ синхронизируются обратно.

## CLI vs Extension — сравнение

| Функция | CLI | VS Code Extension |
|---------|-----|-------------------|
| Команды и skills | Все | Подмножество (введите `/`) |
| Конфигурация MCP server | Да | Нет (настройте через CLI) |
| Checkpoints | Да | Скоро |
| `!` bash shortcut | Да | Нет |
| Tab completion | Да | Нет |

### Запуск CLI в VS Code

```bash
# Встроенный терминал (Ctrl+` / Cmd+`)
claude

# Внешний терминал — подключение к VS Code
/ide
```

### Продолжение беседы Extension → CLI

```bash
claude --resume   # интерактивный выбор беседы
```

### Ссылка на вывод терминала

```
@terminal:name    # name = название терминала
```

## Управление plugins (GUI)

Введите `/plugins` в поле ввода → **Manage plugins**.

### Вкладка Plugins
- **Установленные** — с переключателями enable/disable
- **Доступные** — из настроенных маркетплейсов
- Поиск по имени/описанию
- **Install** → выбор scope:
  - **Install for you** — user scope (все проекты)
  - **Install for this project** — project scope (команда)
  - **Install locally** — local scope (только вы, этот репо)

### Вкладка Marketplaces
- Добавить: GitHub repo, URL или локальный путь
- Обновить список (refresh icon)
- Удалить (trash icon)
- Баннер перезагрузки после изменений

Plugins GUI = те же CLI-команды. Настройки доступны и в CLI, и в расширении.

## MCP в VS Code

Настройка через CLI, использование в обоих:

```bash
# Встроенный терминал VS Code
claude mcp add --transport http github https://api.githubcopilot.com/mcp/
```

Использование: попросите Claude ("Review PR #456"). Аутентификация: `/mcp` в терминале.

## Git-интеграция

### Commits и PR

```
> commit my changes with a descriptive message
> create a pr for this feature
> summarize the changes I've made to the auth module
```

### Git worktrees (параллельные задачи)

```bash
# Создать worktree для фичи
git worktree add ../project-feature-a -b feature-a

# Claude Code в каждом worktree
cd ../project-feature-a && claude
```

Каждый worktree — независимые файлы, общая git-история. Экземпляры Claude не мешают друг другу.

## Third-party providers

1. Параметр `Disable Login Prompt` → включить
2. Настроить provider в `~/.claude/settings.json`:
   - Amazon Bedrock
   - Google Vertex AI
   - Microsoft Foundry

## Безопасность

- Код НЕ используется для обучения моделей
- С auto-accept Claude может менять `settings.json` / `tasks.json` (VS Code выполняет автоматически)
- Рекомендации:
  - **Restricted Mode** для ненадежных workspace
  - Ручное одобрение вместо auto-accept
  - Проверка изменений перед принятием

## Локальные расширения проекта

### claude-select — Send Selection to Terminal

Минимальное расширение для отправки `@file#lines` ссылки в терминал Claude CLI.

**Расположение:** `.vscode-extensions/claude-select/`

| Shortcut | Действие |
|----------|----------|
| `Ctrl+Shift+L` | Отправить `@relativePath#startLine-endLine` в активный терминал (без Enter) |

**Логика:**
1. Берёт выделение в активном редакторе → вычисляет относительный путь от workspace root
2. Одна строка → `@path#line`, диапазон → `@path#startLine-endLine`
3. `sendText(ref, false)` — текст вставляется в терминал без нажатия Enter, можно дописать вопрос

**Установка / обновление:**
```bash
cd .vscode-extensions/claude-select
npm install && npm run compile
npx @vscode/vsce package --allow-missing-repository
code --install-extension claude-select-0.1.0.vsix --force
```

После установки: "Developer: Reload Window" для активации.

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| Расширение не устанавливается | VS Code 1.98.0+, проверить разрешения, установить из Marketplace |
| Spark icon не виден | Открыть файл, VS Code 1.98.0+, Reload Window, отключить конфликтующие AI-расширения, проверить Workspace Trust |
| Claude не отвечает | Проверить интернет, новая беседа, `claude` из терминала (детальные ошибки) |

### Удаление

1. `Cmd+Shift+X` / `Ctrl+Shift+X` → "Claude Code" → Uninstall
2. Очистка данных: `rm -rf ~/.vscode/globalStorage/anthropic.claude-code`

## Встроенные tutorials

- **Walkthrough**: "Claude Code: Open Walkthrough" из палитры команд
- **Интерактивный чеклист**: значок выпускной шапки в заголовке панели Claude

---

**Источники:** Использование Claude Code в VS Code.md (docs/documentation/Claude Code Docs/1. Начало работы/)
