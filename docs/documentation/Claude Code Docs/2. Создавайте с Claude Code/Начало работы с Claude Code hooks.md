> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Справочник по хукам

> Справочник по событиям хуков Claude Code, схеме конфигурации, форматам JSON ввода/вывода, кодам выхода, асинхронным хукам, prompt-хукам и хукам для MCP-инструментов.

<Tip>
  Для быстрого старта с примерами см. [Автоматизация рабочих процессов с помощью хуков](/en/hooks-guide).
</Tip>

Хуки — это определяемые пользователем shell-команды или LLM-промпты, которые выполняются автоматически в определённые моменты жизненного цикла Claude Code. Используйте этот справочник для поиска схем событий, параметров конфигурации, форматов JSON ввода/вывода и расширенных функций, таких как асинхронные хуки и хуки для MCP-инструментов.

## Жизненный цикл хуков

Хуки срабатывают в определённые моменты сессии Claude Code. Когда событие срабатывает и matcher совпадает, Claude Code передаёт JSON-контекст о событии вашему обработчику. Для command-хуков данные поступают через stdin. Обработчик может проверить входные данные, выполнить действие и опционально вернуть решение.

| Событие              | Когда срабатывает                                                  |
| :------------------- | :----------------------------------------------------------------- |
| `SessionStart`       | Когда сессия начинается или возобновляется                         |
| `UserPromptSubmit`   | Когда вы отправляете промпт, до того как Claude его обработает     |
| `PreToolUse`         | Перед выполнением вызова инструмента. Может заблокировать          |
| `PermissionRequest`  | Когда появляется диалог запроса разрешений                         |
| `PostToolUse`        | После успешного выполнения инструмента                             |
| `PostToolUseFailure` | После неудачного выполнения инструмента                            |
| `Notification`       | Когда Claude Code отправляет уведомление                           |
| `SubagentStart`      | Когда порождается подагент                                         |
| `SubagentStop`       | Когда подагент завершает работу                                    |
| `Stop`               | Когда Claude завершает ответ                                       |
| `TeammateIdle`       | Когда teammate из agent team собирается перейти в режим ожидания   |
| `TaskCompleted`      | Когда задача помечается как выполненная                             |
| `PreCompact`         | Перед компактификацией контекста                                   |
| `SessionEnd`         | Когда сессия завершается                                           |

## Конфигурация

Хуки определяются в JSON-файлах настроек. Конфигурация имеет три уровня вложенности:

1. Выберите событие хука, например `PreToolUse` или `Stop`
2. Добавьте группу matcher для фильтрации
3. Определите один или несколько обработчиков хуков

### Расположение хуков

Где вы определяете хук, определяет его область действия:

| Расположение                      | Область действия         | Можно делиться              |
| :-------------------------------- | :----------------------- | :-------------------------- |
| `~/.claude/settings.json`         | Все ваши проекты         | Нет, локально               |
| `.claude/settings.json`           | Один проект              | Да, можно закоммитить       |
| `.claude/settings.local.json`     | Один проект              | Нет, в gitignore            |
| Managed policy settings           | Вся организация          | Да, управляется админом     |
| Plugin `hooks/hooks.json`         | Когда плагин включён     | Да, в составе плагина       |

### Паттерны matcher

Поле `matcher` — regex-строка, фильтрующая когда срабатывают хуки. Используйте `"*"`, `""` или опустите `matcher` для совпадения со всеми.

| Событие                                                               | Что фильтрует matcher     |
| :--------------------------------------------------------------------- | :------------------------ |
| `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest` | имя инструмента           |
| `SessionStart`                                                         | как началась сессия       |
| `SessionEnd`                                                           | причина завершения        |
| `Notification`                                                         | тип уведомления           |
| `UserPromptSubmit`, `Stop`, `TeammateIdle`, `TaskCompleted`            | не поддерживает matcher   |

### Поля обработчика хуков

Каждый объект во внутреннем массиве `hooks` — это обработчик. Есть три типа:

- **Command** (`type: "command"`): запускает shell-команду
- **Prompt** (`type: "prompt"`): отправляет промпт модели Claude для однократной оценки
- **Agent** (`type: "agent"`): порождает подагента с доступом к инструментам

#### Общие поля

| Поле            | Обязательное | Описание                                                    |
| :-------------- | :----------- | :---------------------------------------------------------- |
| `type`          | да           | `"command"`, `"prompt"` или `"agent"`                       |
| `timeout`       | нет          | Секунды до отмены. Default: 600 (command), 30 (prompt), 60 (agent) |
| `statusMessage` | нет          | Пользовательское сообщение спиннера                         |
| `once`          | нет          | Если `true`, запускается один раз за сессию                 |

#### Поля command-хука

| Поле      | Обязательное | Описание                                              |
| :-------- | :----------- | :---------------------------------------------------- |
| `command` | да           | Shell-команда для выполнения                          |
| `async`   | нет          | Если `true`, запускается в фоне без блокировки        |

## Ввод и вывод хуков

### Общие поля ввода

Все события хуков получают через stdin JSON с полями:

| Поле              | Описание                                         |
| :---------------- | :----------------------------------------------- |
| `session_id`      | Идентификатор текущей сессии                     |
| `transcript_path` | Путь к JSON разговора                            |
| `cwd`             | Текущая рабочая директория                       |
| `permission_mode` | Текущий режим разрешений                         |
| `hook_event_name` | Имя сработавшего события                         |

### Коды выхода

- **Exit 0**: успех. Claude Code парсит stdout для JSON
- **Exit 2**: блокирующая ошибка. stderr передаётся Claude как сообщение об ошибке
- **Другие коды**: неблокирующая ошибка. Продолжение работы

### JSON вывод

```json
{
  "continue": true,
  "stopReason": "сообщение при continue=false",
  "suppressOutput": false,
  "systemMessage": "предупреждение пользователю"
}
```

### Управление решениями

| События                                                               | Паттерн решения     | Ключевые поля                                                    |
| :-------------------------------------------------------------------- | :------------------ | :--------------------------------------------------------------- |
| UserPromptSubmit, PostToolUse, PostToolUseFailure, Stop, SubagentStop | Top-level `decision` | `decision: "block"`, `reason`                                    |
| PreToolUse                                                            | `hookSpecificOutput` | `permissionDecision` (allow/deny/ask), `permissionDecisionReason` |
| PermissionRequest                                                     | `hookSpecificOutput` | `decision.behavior` (allow/deny)                                 |

## Пример: блокировка rm -rf

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/block-rm.sh"
          }
        ]
      }
    ]
  }
}
```

```bash
#!/bin/bash
# .claude/hooks/block-rm.sh
COMMAND=$(jq -r '.tool_input.command')

if echo "$COMMAND" | grep -q 'rm -rf'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Destructive command blocked by hook"
    }
  }'
else
  exit 0
fi
```

## Prompt-хуки

Вместо выполнения Bash-команды, prompt-хуки отправляют входные данные и ваш промпт модели Claude:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Evaluate if Claude should stop: $ARGUMENTS. Check if all tasks are complete."
          }
        ]
      }
    ]
  }
}
```

LLM отвечает JSON:

```json
{
  "ok": true,
  "reason": "Объяснение решения"
}
```

## Agent-хуки

Agent-хуки порождают подагента с доступом к инструментам (Read, Grep, Glob):

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "agent",
            "prompt": "Verify that all unit tests pass. Run the test suite and check the results. $ARGUMENTS",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

## Асинхронные хуки

Добавьте `"async": true` для запуска хука в фоне:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/run-tests.sh",
            "async": true,
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

## Отладка хуков

Запустите `claude --debug` для просмотра деталей выполнения хуков. Переключите verbose-режим с помощью `Ctrl+O`.

## Безопасность

- Всегда проверяйте и санитизируйте входные данные
- Используйте кавычки для shell-переменных: `"$VAR"` а не `$VAR`
- Блокируйте path traversal: проверяйте `..` в путях файлов
- Используйте абсолютные пути: `"$CLAUDE_PROJECT_DIR"` для корня проекта
- Пропускайте чувствительные файлы: `.env`, `.git/`, ключи
