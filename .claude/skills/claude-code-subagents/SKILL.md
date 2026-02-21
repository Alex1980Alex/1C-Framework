---
name: claude-code-subagents
description: "Подагенты Claude Code: создание, YAML конфигурация, инструменты, permissions, модели, хуки подагентов, встроенные агенты (Explore, Plan, general-purpose). Триггеры: 'subagent', 'подагент', 'создать агента', 'create agent', '/agents', 'Task tool', 'делегировать', 'delegate', 'agent YAML', 'agent frontmatter', 'permission mode', 'встроенные агенты', 'built-in agents'. НЕ для LangGraph агентов фреймворка — используй agent-orchestration."
---

# Подагенты Claude Code

## Обзор

Подагент = специализированный AI помощник со своим контекстом, системным промптом,
ограничениями инструментов и моделью. Claude делегирует задачи подагентам автоматически
по описанию или по явному запросу.

**Возможности:**
- Собственное окно контекста (изоляция от основного разговора)
- Ограничение инструментов (только Read, только Bash, и т.д.)
- Своя модель (haiku для быстрых, opus для сложных)
- Хуки жизненного цикла (PreToolUse, PostToolUse, Stop)
- Предзагрузка навыков (skills)

## Встроенные подагенты

| Агент | Модель | Инструменты | Назначение |
|-------|--------|-------------|------------|
| **Explore** | Haiku | Read-only | Поиск и анализ кодовой базы |
| **Plan** | Inherit | Read-only | Исследование для режима планирования |
| **general-purpose** | Inherit | Все | Сложные многошаговые задачи |
| **Bash** | Inherit | Bash | Терминальные команды в отдельном контексте |
| **statusline-setup** | Sonnet | — | Настройка строки состояния |
| **Claude Code Guide** | Haiku | — | Вопросы о функциях Claude Code |

## Быстрый старт

### Через команду /agents

```
/agents → Create new agent → User-level → Generate with Claude
```

### Через файл Markdown

```markdown
---
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep
model: sonnet
---

You are a code reviewer. Analyze code and provide
specific, actionable feedback on quality, security, and best practices.
```

## Конфигурация (frontmatter)

| Поле | Обяз. | Описание |
|------|-------|----------|
| `name` | Да | Уникальный ID (lowercase, hyphens) |
| `description` | Да | Когда Claude должен делегировать (для автоматического выбора) |
| `tools` | Нет | Список инструментов. Если опущен — наследует все |
| `disallowedTools` | Нет | Инструменты для запрета (убираются из наследованных) |
| `model` | Да | `sonnet`, `opus`, `haiku` или `inherit` (default: `sonnet`) |
| `permissionMode` | Нет | `default`, `acceptEdits`, `dontAsk`, `bypassPermissions`, `plan` |
| `skills` | Нет | Навыки для предзагрузки в контекст подагента |
| `hooks` | Нет | Хуки жизненного цикла подагента |

## Области подагентов

| Расположение | Область | Приоритет | Создание |
|--------------|---------|-----------|----------|
| Флаг CLI `--agents` | Текущая сессия | 1 (высший) | JSON при запуске |
| `.claude/agents/` | Текущий проект | 2 | Файл или `/agents` |
| `~/.claude/agents/` | Все проекты | 3 | Файл или `/agents` |
| Плагин `agents/` | Где плагин включён | 4 (низший) | Через плагин |

## Режимы разрешений

| Режим | Поведение |
|-------|-----------|
| `default` | Стандартные проверки с подсказками |
| `acceptEdits` | Авто-одобрение редактирования файлов |
| `dontAsk` | Авто-отклонение неразрешённых (разрешённые работают) |
| `bypassPermissions` | Пропустить ВСЕ проверки (осторожно!) |
| `plan` | Только чтение, без правок и команд |

## Доступные инструменты

Стандартные: `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`, `WebFetch`, `WebSearch`,
`TodoWrite`, `Task`, `AskUserQuestion`, `NotebookEdit`, `EnterPlanMode`, `ExitPlanMode`.

MCP инструменты: `mcp__server__tool_name` (недоступны в фоновых подагентах).

## Хуки подагентов

### В frontmatter подагента

```yaml
---
name: safe-builder
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-command.sh"
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/run-linter.sh"
---
```

### В settings.json (уровень проекта)

```json
{
  "hooks": {
    "SubagentStart": [
      {
        "matcher": "db-agent",
        "hooks": [{ "type": "command", "command": "./scripts/setup-db.sh" }]
      }
    ],
    "SubagentStop": [
      {
        "matcher": "db-agent",
        "hooks": [{ "type": "command", "command": "./scripts/cleanup-db.sh" }]
      }
    ]
  }
}
```

## Предзагрузка навыков

```yaml
---
name: api-developer
description: Implement API endpoints following team conventions
skills:
  - api-conventions
  - error-handling-patterns
---

Implement API endpoints. Follow the conventions from preloaded skills.
```

Содержимое навыков внедряется в контекст при запуске. Подагенты НЕ наследуют
навыки из родительского разговора.

## CLI определение подагентов

```bash
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer. Use proactively after code changes.",
    "prompt": "You are a senior code reviewer.",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  }
}'
```

## Отключение подагентов

В settings.json:
```json
{
  "permissions": {
    "deny": ["Task(Explore)", "Task(my-custom-agent)"]
  }
}
```

Или через CLI:
```bash
claude --disallowedTools "Task(Explore)"
```

## Паттерны использования

| Паттерн | Описание |
|---------|----------|
| **Изоляция вывода** | Тесты/логи в подагенте, только summary возвращается |
| **Параллельное исследование** | Несколько Explore агентов одновременно |
| **Цепочка** | code-reviewer → optimizer → tester (последовательно) |
| **Фоновое выполнение** | `Ctrl+B` или "run in background" |
| **Возобновление** | Claude сохраняет agent ID, можно продолжить |

## Когда подагент, когда основной разговор

| Ситуация | Выбор |
|----------|-------|
| Частое взаимодействие, итерации | Основной разговор |
| Быстрое целевое изменение | Основной разговор |
| Много вывода (тесты, логи) | Подагент |
| Нужны ограничения инструментов | Подагент |
| Самодостаточная задача | Подагент |

**Ограничение:** подагенты НЕ могут порождать других подагентов.

## Источники

- `docs/documentation/Claude Code Docs/2. Создавайте с Claude Code/Создание пользовательских подагентов.md`
