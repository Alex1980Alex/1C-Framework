---
name: claude-code-settings
description: >
  Параметры и конфигурация Claude Code: settings.json (scopes: managed/user/project/local),
  переменные окружения, CLAUDE.md иерархия памяти, модели, стили вывода.
  Триггеры: 'settings.json', 'параметры claude code', 'claude code config',
  'настройки claude', 'managed settings', 'CLAUDE.md', 'память claude', 'memory management',
  'model config', 'output style', 'стиль вывода', 'конфигурация модели',
  'scopes', 'области конфигурации', 'environment variables claude'.
  НЕ для .env фреймворка — используй framework-config.
---

# Параметры Claude Code

## Области конфигурации (Scopes)

| Область | Расположение | Кто видит | В git? |
|---------|-------------|-----------|--------|
| **Managed** | `managed-settings.json` (системный) | Все пользователи машины | Нет |
| **User** | `~/.claude/settings.json` | Вы, все проекты | Нет |
| **Project** | `.claude/settings.json` | Вся команда | Да |
| **Local** | `.claude/settings.local.json` | Вы, этот проект | Нет (.gitignore) |

**Приоритет (от высшего к низшему):**
Managed → CLI аргументы → Local → Project → User

## Файлы конфигурации

| Файл | Описание |
|------|----------|
| `~/.claude/settings.json` | Глобальные пользовательские настройки |
| `.claude/settings.json` | Проектные настройки (в git) |
| `.claude/settings.local.json` | Локальные переопределения (не в git) |
| `CLAUDE.md` | Память / инструкции для Claude |
| `.claude/agents/*.md` | Подагенты проекта |
| `.claude/skills/*/SKILL.md` | Навыки проекта |

## Ключевые настройки settings.json

### Разрешения

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Bash(git log:*)",
      "Bash(npm test:*)",
      "Edit(/src/**/*.ts)",
      "WebFetch(domain:github.com)",
      "mcp__server__tool"
    ],
    "deny": [
      "Bash(rm -rf:*)",
      "Task(Explore)"
    ],
    "defaultMode": "default"
  }
}
```

### Синтаксис правил разрешений

| Паттерн | Описание |
|---------|----------|
| `Tool` | Любое использование инструмента |
| `Bash(command)` | Точная команда |
| `Bash(npm run test:*)` | Префикс с wildcard |
| `Bash(npm *)` | Wildcard в любом месте |
| `Read(*.env)` | Относительно cwd |
| `Read(~/path/*)` | Относительно home |
| `Read(//absolute/*)` | Абсолютный путь |
| `Edit(/src/**)` | Относительно файла settings |
| `WebFetch(domain:github.com)` | Домен |
| `mcp__server__tool` | MCP инструмент |
| `Task(agent-name)` | Подагент |

### Хуки

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "./scripts/check.sh" }]
      }
    ],
    "PostToolUse": [...],
    "Stop": [...],
    "SubagentStart": [...],
    "SubagentStop": [...]
  }
}
```

### MCP серверы

```json
{
  "mcpServers": {
    "server-name": {
      "command": "node",
      "args": ["./server.js"],
      "env": { "KEY": "value" }
    }
  }
}
```

### Прочие настройки

| Настройка | Тип | Описание |
|-----------|-----|----------|
| `enableAllProjectMcpServers` | bool | Включить все MCP из `.claude/` |
| `additionalDirectories` | string[] | Доп. директории для доступа |
| `pluginMarketplaces` | object[] | Маркетплейсы плагинов |
| `cleanupPeriodDays` | number | Очистка старых сессий (default: 30) |

## Переменные окружения

### Основные

| Переменная | Описание |
|-----------|----------|
| `ANTHROPIC_API_KEY` | API ключ Anthropic |
| `CLAUDE_CODE_USE_BEDROCK=1` | Использовать AWS Bedrock |
| `CLAUDE_CODE_USE_VERTEX=1` | Использовать Google Vertex AI |
| `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` | Отключить фоновые задачи |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` | Порог авто-компактирования (default: 95%) |
| `CLAUDE_CODE_TASK_LIST_ID=my-project` | Именованный список задач |

### OpenTelemetry

| Переменная | Описание |
|-----------|----------|
| `CLAUDE_CODE_ENABLE_TELEMETRY=1` | Включить телеметрию |
| `OTEL_METRICS_EXPORTER=otlp` | Экспортер метрик |
| `OTEL_LOGS_EXPORTER=otlp` | Экспортер логов |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Endpoint OTLP |
| `OTEL_EXPORTER_OTLP_HEADERS` | Заголовки авторизации |
| `OTEL_RESOURCE_ATTRIBUTES` | Атрибуты (department, team) |
| `OTEL_LOG_USER_PROMPTS=1` | Логировать промпты |

### API Key Helper

```json
{
  "apiKeyHelper": "./scripts/get-api-key.sh"
}
```

TTL: `CLAUDE_CODE_API_KEY_HELPER_TTL_MS` (default: 300000 = 5 мин).

## Конфигурация моделей

### Псевдонимы

| Псевдоним | Модель | Где использовать |
|-----------|--------|-----------------|
| `sonnet` | Claude Sonnet (последняя) | Баланс скорость/качество |
| `opus` | Claude Opus (последняя) | Сложные задачи |
| `haiku` | Claude Haiku (последняя) | Быстрые задачи, исследование |

### Выбор модели

```bash
claude --model opus                          # CLI флаг
/model                                       # В сессии
Alt+P                                        # Горячая клавиша
```

### Fallback модель

```bash
claude -p --fallback-model sonnet "query"    # При перегрузке основной
```

## Управление памятью (CLAUDE.md)

### Иерархия файлов

| Файл | Область | Приоритет |
|------|---------|-----------|
| `~/.claude/CLAUDE.md` | Глобальный | Все проекты |
| `./CLAUDE.md` | Проект (корень) | Текущий проект |
| `./.claude/CLAUDE.md` | Проект (скрытый) | Текущий проект |
| `./src/CLAUDE.md` | Поддиректория | При работе в src/ |

### Project rules (glob patterns)

```json
{
  "projectRules": [
    {
      "glob": "**/*.ts",
      "rule": "Always use strict TypeScript"
    },
    {
      "glob": "src/api/**",
      "rule": "Follow REST conventions, add OpenAPI docs"
    }
  ]
}
```

### Команды памяти

| Команда | Описание |
|---------|----------|
| `/memory` | Редактировать CLAUDE.md |
| `/init` | Создать начальный CLAUDE.md |
| `#` в промпте | Добавить в память (начало строки с #) |

### Compact hints

В CLAUDE.md:
```markdown
# Summary instructions
When using compact, focus on test output and code changes
```

## Стили вывода

### Встроенные

| Стиль | Описание |
|-------|----------|
| Default | Стандартный стиль |
| Explanatory | Подробные объяснения |
| Learning | Обучающий формат |

### Пользовательский стиль

Файл `~/.claude/styles/my-style.md`:

```markdown
---
name: my-style
description: Concise responses in Russian
---
Always respond in Russian. Be concise. Use code examples.
Skip explanations unless asked. Use markdown tables for comparisons.
```

Переключение: `/style` в сессии.

## Источники

- `docs/documentation/Claude Code Docs/3. Конфигурация/Параметры Claude Code.md`
- `docs/documentation/Claude Code Docs/3. Конфигурация/Конфигурация модели.md`
- `docs/documentation/Claude Code Docs/3. Конфигурация/Управление памятью Claude.md`
- `docs/documentation/Claude Code Docs/2. Создавайте с Claude Code/Стили вывода.md`
