---
name: claude-code-plugins
description: >
  Система плагинов Claude Code: создание, manifest, slash-команды, агенты, хуки, LSP,
  маркетплейсы, установка, распространение. Триггеры: 'plugin', 'плагин', 'marketplace',
  'маркетплейс', 'создать плагин', 'create plugin', 'manifest', 'slash command',
  'распространить', 'distribute plugin', 'установить плагин', 'install plugin'.
  НЕ для навыков (skills) — используй doc-to-skill. НЕ для хуков — используй create-hook.
---

# Система плагинов Claude Code

## Обзор

Плагин = пакет из нескольких компонентов Claude Code (команды, агенты, навыки, хуки, MCP, LSP),
распространяемый через маркетплейсы или локально.

**Когда плагин, а не standalone конфигурация:**
- Нужно распространить набор инструментов команде → плагин
- Один hook или skill для себя → standalone файлы

## Быстрый старт

### 1. Создать структуру

```
my-plugin/
├── manifest.json          # ОБЯЗАТЕЛЬНЫЙ: метаданные плагина
├── commands/              # Slash-команды (/plugin-name:command)
│   └── review.md
├── agents/                # Подагенты
│   └── reviewer.md
├── skills/                # Навыки (SKILL.md)
│   └── conventions/
│       └── SKILL.md
├── hooks/                 # Хуки (PreToolUse, PostToolUse, Stop)
│   └── settings.json
├── mcp-servers/           # MCP серверы
│   └── settings.json
└── lsp-servers/           # LSP серверы
    └── settings.json
```

### 2. Написать manifest.json

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Description of what the plugin does",
  "author": "Author Name"
}
```

**Все поля manifest:**

| Поле | Обяз. | Описание |
|------|-------|----------|
| `name` | Да | Уникальное имя (lowercase, hyphens) |
| `version` | Да | Semver (1.0.0) |
| `description` | Да | Описание для маркетплейса |
| `author` | Нет | Автор |
| `homepage` | Нет | URL документации |
| `license` | Нет | Лицензия |

### 3. Тестировать локально

```bash
claude --plugin-dir ./my-plugin
```

Или установить локально:
```bash
/plugins install --path ./my-plugin --scope local
```

## Компоненты плагина

### Commands (Slash-команды)

Файлы `.md` в `commands/`. Вызываются как `/plugin-name:command-name`.

```markdown
---
name: review
description: Review code for quality and security
---
Review the current changes for code quality, security issues, and best practices.
Focus on: error handling, input validation, naming conventions.
```

**Команда по умолчанию:** файл `commands/index.md` → вызывается как `/plugin-name`.

### Agents (Подагенты)

Файлы `.md` в `agents/`. Автоматически делегируются Claude по описанию.

```markdown
---
name: code-reviewer
description: Reviews code for quality (use proactively after changes)
tools: Read, Grep, Glob
model: sonnet
---
You are a senior code reviewer. Analyze code quality, security, best practices.
```

### Skills (Навыки)

Директории с `SKILL.md` в `skills/`. Загружаются по триггерам из description.

### Hooks

Файл `hooks/settings.json` — стандартный формат хуков Claude Code:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/lint.sh"
          }
        ]
      }
    ]
  }
}
```

`${CLAUDE_PLUGIN_ROOT}` — путь к корню плагина (разрешается автоматически).

### MCP Servers

Файл `mcp-servers/settings.json`:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/server.js"]
    }
  }
}
```

### LSP Servers

Файл `lsp-servers/settings.json`:

```json
{
  "lspServers": {
    "my-lsp": {
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/lsp/server.js"],
      "languages": ["typescript", "javascript"]
    }
  }
}
```

## Области установки

| Область | Путь | Кто видит |
|---------|------|-----------|
| `user` | `~/.claude/plugins/` | Только вы, все проекты |
| `project` | `.claude/plugins/` | Вся команда (в git) |
| `local` | `.claude/plugins.local/` | Только вы, этот проект |
| `managed` | Системная директория | Все пользователи машины |

## Маркетплейсы

### Установка из маркетплейса

```bash
/plugins install plugin-name              # Из Anthropic marketplace
/plugins install plugin-name --scope project  # Для всей команды
```

### Добавить маркетплейс

```bash
/plugins marketplace add https://github.com/org/marketplace
/plugins marketplace add /path/to/local/marketplace
```

### Управление

```bash
/plugins list                    # Список установленных
/plugins enable plugin-name      # Включить
/plugins disable plugin-name     # Выключить
/plugins uninstall plugin-name   # Удалить
/plugins update plugin-name      # Обновить
/plugins marketplace update      # Обновить индексы маркетплейсов
```

### Командный маркетплейс

Для организации — `.claude/settings.json`:

```json
{
  "pluginMarketplaces": [
    {
      "url": "https://github.com/our-org/claude-plugins",
      "autoUpdate": true
    }
  ]
}
```

## CLI управление плагинами

| Команда | Описание |
|---------|----------|
| `/plugins` | Интерактивное меню |
| `/plugins install <name\|path\|url>` | Установить |
| `/plugins uninstall <name>` | Удалить |
| `/plugins enable <name>` | Включить |
| `/plugins disable <name>` | Выключить |
| `/plugins update [name]` | Обновить (все или конкретный) |
| `/plugins list` | Список установленных |
| `/plugins marketplace add <url>` | Добавить маркетплейс |
| `/plugins marketplace remove <url>` | Удалить маркетплейс |

## Конвертация существующей конфигурации в плагин

Если уже есть hooks, skills, MCP серверы в проекте:

1. Создать `manifest.json`
2. Скопировать hooks → `hooks/settings.json`
3. Скопировать skills → `skills/`
4. Скопировать MCP → `mcp-servers/settings.json`
5. Заменить абсолютные пути на `${CLAUDE_PLUGIN_ROOT}`
6. Тестировать: `claude --plugin-dir ./my-plugin`

## Отладка

```bash
claude --debug "plugins"          # Логи загрузки плагинов
/plugins list                     # Проверить статус
```

**Частые проблемы:**
- `manifest.json` не найден → проверить структуру директории
- Хук не срабатывает → проверить matcher, путь к скрипту
- `${CLAUDE_PLUGIN_ROOT}` не разрешается → проверить установку плагина

## Источники

- `docs/documentation/Claude Code Docs/2. Создавайте с Claude Code/Создание плагинов.md`
- `docs/documentation/Claude Code Docs/5. Справка/Справочник плагинов.md`
- `docs/documentation/Claude Code Docs/2. Создавайте с Claude Code/Обнаружение и установка готовых плагинов через маркетплейсы.md`
