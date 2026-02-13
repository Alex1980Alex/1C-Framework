> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Справочник по hooks

> На этой странице представлена справочная документация по реализации hooks в Claude Code.

<Tip>
  Для краткого руководства с примерами см. [Начало работы с hooks Claude Code](/ru/hooks-guide).
</Tip>

## Конфигурация

Hooks Claude Code настраиваются в ваших [файлах настроек](/ru/settings):

* `~/.claude/settings.json` - Пользовательские настройки
* `.claude/settings.json` - Настройки проекта
* `.claude/settings.local.json` - Локальные настройки проекта (не коммитятся)
* Управляемые настройки политики

<Note>
  Администраторы предприятия могут использовать `allowManagedHooksOnly` для блокировки пользовательских, проектных и плагинных hooks. См. [Конфигурация hooks](/ru/settings#hook-configuration).
</Note>

### Структура

Hooks организованы по матчерам, где каждый матчер может иметь несколько hooks:

```json  theme={null}
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",
        "hooks": [
          {
            "type": "command",
            "command": "your-command-here"
          }
        ]
      }
    ]
  }
}
```

* **matcher**: Шаблон для сопоставления имён инструментов, чувствителен к регистру (применяется только для
  `PreToolUse`, `PermissionRequest` и `PostToolUse`)
  * Простые строки совпадают точно: `Write` совпадает только с инструментом Write
  * Поддерживает regex: `Edit|Write` или `Notebook.*`
  * Используйте `*` для сопоставления всех инструментов. Вы также можете использовать пустую строку (`""`) или оставить
    `matcher` пустым.
* **hooks**: Массив hooks для выполнения при совпадении шаблона
  * `type`: Тип выполнения hook - `"command"` для bash команд или `"prompt"` для оценки на основе LLM
  * `command`: (Для `type: "command"`) Bash команда для выполнения (может использовать переменную окружения `$CLAUDE_PROJECT_DIR`)
  * `prompt`: (Для `type: "prompt"`) Подсказка для отправки LLM для оценки
  * `timeout`: (Опционально) Как долго hook должен работать в секундах перед отменой этого конкретного hook

Для событий типа `UserPromptSubmit`, `Stop` и `SubagentStop`
которые не используют матчеры, вы можете опустить поле matcher:

```json  theme={null}
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/prompt-validator.py"
          }
        ]
      }
    ]
  }
}
```

### Скрипты Hook для конкретного проекта

Вы можете использовать переменную окружения `CLAUDE_PROJECT_DIR` (доступна только когда
Claude Code запускает команду hook) для ссылки на скрипты, хранящиеся в вашем проекте,
обеспечивая их работу независимо от текущей директории Claude:

```json  theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-style.sh"
          }
        ]
      }
    ]
  }
}
```

### Hooks плагинов

[Плагины](/ru/plugins) могут предоставлять hooks, которые беспрепятственно интегрируются с вашими пользовательскими и проектными hooks. Hooks плагинов автоматически объединяются с вашей конфигурацией при включении плагинов.

**Как работают hooks плагинов**:

* Hooks плагинов определяются в файле `hooks/hooks.json` плагина или в файле, указанном пользовательским путём к полю `hooks`.
* Когда плагин включен, его hooks объединяются с пользовательскими и проектными hooks
* Несколько hooks из разных источников могут реагировать на одно и то же событие
* Hooks плагинов используют переменную окружения `${CLAUDE_PLUGIN_ROOT}` для ссылки на файлы плагина

**Пример конфигурации hook плагина**:

```json  theme={null}
{
  "description": "Automatic code formatting",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

<Note>
  Hooks плагинов используют тот же формат, что и обычные hooks с опциональным полем `description` для объяснения назначения hook.
</Note>

<Note>
  Hooks плагинов работают вместе с вашими пользовательскими hooks. Если несколько hooks совпадают с событием, они все выполняются параллельно.
</Note>

**Переменные окружения для плагинов**:

* `${CLAUDE_PLUGIN_ROOT}`: Абсолютный путь к директории плагина
* `${CLAUDE_PROJECT_DIR}`: Корневая директория проекта (то же самое, что и для проектных hooks)
* Все стандартные переменные окружения доступны

См. [справочник компонентов плагинов](/ru/plugins-reference#hooks) для деталей по созданию hooks плагинов.

### Hooks в Skills, Agents и Slash Commands

В дополнение к файлам настроек и плагинам, hooks могут быть определены непосредственно в [Skills](/ru/skills), [subagents](/ru/sub-agents) и [slash commands](/ru/slash-commands) используя frontmatter. Эти hooks ограничены жизненным циклом компонента и работают только когда этот компонент активен.

**Поддерживаемые события**: `PreToolUse`, `PostToolUse` и `Stop`

**Пример в Skill**:

```yaml  theme={null}
---
name: secure-operations
description: Perform operations with security checks
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/security-check.sh"
---
```

**Пример в agent**:

```yaml  theme={null}
---
name: code-reviewer
description: Review code changes
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/run-linter.sh"
---
```

Hooks с областью действия компонента следуют той же конфигурации, что и hooks на основе настроек, но автоматически очищаются при завершении выполнения компонента.

**Дополнительная опция для skills и slash commands:**

* `once`: Установите значение `true` для выполнения hook только один раз за сеанс. После первого успешного выполнения hook удаляется. Примечание: Эта опция в настоящее время поддерживается только для skills и slash commands, а не для agents.

## Hooks на основе подсказок

В дополнение к bash command hooks (`type: "command"`), Claude Code поддерживает hooks на основе подсказок (`type: "prompt"`), которые используют LLM для оценки того, разрешить или заблокировать действие. Hooks на основе подсказок в настоящее время поддерживаются только для `Stop` и `SubagentStop` hooks, где они обеспечивают интеллектуальные, контекстно-зависимые решения.

### Как работают hooks на основе подсказок

Вместо выполнения bash команды, hooks на основе подсказок:

1. Отправляют входные данные hook и вашу подсказку быстрому LLM (Haiku)
2. LLM отвечает структурированным JSON, содержащим решение
3. Claude Code автоматически обрабатывает решение

### Конфигурация

```json  theme={null}
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

**Поля:**

* `type`: Должно быть `"prompt"`
* `prompt`: Текст подсказки для отправки LLM
  * Используйте `$ARGUMENTS` как заполнитель для входных данных hook JSON
  * Если `$ARGUMENTS` отсутствует, входной JSON добавляется к подсказке
* `timeout`: (Опционально) Timeout в секундах (по умолчанию: 30 секунд)

### Схема ответа

LLM должен ответить JSON, содержащим:

```json  theme={null}
{
  "ok": true | false,
  "reason": "Explanation for the decision"
}
```

**Поля ответа:**

* `ok`: `true` разрешает действие, `false` предотвращает его
* `reason`: Требуется когда `ok` это `false`. Объяснение, показанное Claude

### Поддерживаемые события hook

Hooks на основе подсказок работают с любым событием hook, но наиболее полезны для:

* **Stop**: Интеллектуально решить, должен ли Claude продолжать работу
* **SubagentStop**: Оценить, завершил ли subagent свою задачу
* **UserPromptSubmit**: Валидировать пользовательские подсказки с помощью LLM
* **PreToolUse**: Принимать контекстно-зависимые решения по разрешениям
* **PermissionRequest**: Интеллектуально разрешать или отрицать диалоги разрешений

### Пример: Интеллектуальный Stop hook

```json  theme={null}
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "You are evaluating whether Claude should stop working. Context: $ARGUMENTS\n\nAnalyze the conversation and determine if:\n1. All user-requested tasks are complete\n2. Any errors need to be addressed\n3. Follow-up work is needed\n\nRespond with JSON: {\"ok\": true} to allow stopping, or {\"ok\": false, \"reason\": \"your explanation\"} to continue working.",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Пример: SubagentStop с пользовательской логикой

```json  theme={null}
{
  "hooks": {
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Evaluate if this subagent should stop. Input: $ARGUMENTS\n\nCheck if:\n- The subagent completed its assigned task\n- Any errors occurred that need fixing\n- Additional context gathering is needed\n\nReturn: {\"ok\": true} to allow stopping, or {\"ok\": false, \"reason\": \"explanation\"} to continue."
          }
        ]
      }
    ]
  }
}
```

### Сравнение с bash command hooks

| Функция                         | Bash Command Hooks            | Hooks на основе подсказок     |
| ------------------------------- | ----------------------------- | ----------------------------- |
| **Выполнение**                  | Запускает bash скрипт         | Запрашивает LLM               |
| **Логика решения**              | Вы реализуете в коде          | LLM оценивает контекст        |
| **Сложность настройки**         | Требует файл скрипта          | Настройка подсказки           |
| **Осведомленность о контексте** | Ограничена логикой скрипта    | Понимание естественного языка |
| **Производительность**          | Быстро (локальное выполнение) | Медленнее (вызов API)         |
| **Случай использования**        | Детерминированные правила     | Контекстно-зависимые решения  |

### Лучшие практики

* **Будьте конкретны в подсказках**: Четко укажите, что вы хотите, чтобы LLM оценил
* **Включите критерии решения**: Перечислите факторы, которые LLM должен учитывать
* **Тестируйте ваши подсказки**: Проверьте, что LLM принимает правильные решения для ваших случаев использования
* **Установите соответствующие timeouts**: По умолчанию 30 секунд, отрегулируйте при необходимости
* **Используйте для сложных решений**: Bash hooks лучше для простых, детерминированных правил

См. [справочник компонентов плагинов](/ru/plugins-reference#hooks) для деталей по созданию hooks плагинов.

## События Hook

### PreToolUse

Запускается после того, как Claude создает параметры инструмента и перед обработкой вызова инструмента.

**Общие матчеры:**

* `Task` - Задачи Subagent (см. [документацию subagents](/ru/sub-agents))
* `Bash` - Команды оболочки
* `Glob` - Сопоставление шаблонов файлов
* `Grep` - Поиск содержимого
* `Read` - Чтение файлов
* `Edit` - Редактирование файлов
* `Write` - Запись файлов
* `WebFetch`, `WebSearch` - Веб-операции

Используйте [управление решениями PreToolUse](#pretooluse-decision-control) для разрешения, отрицания или запроса разрешения на использование инструмента.

### PermissionRequest

Запускается когда пользователю показывается диалог разрешения.
Используйте [управление решениями PermissionRequest](#permissionrequest-decision-control) для разрешения или отрицания от имени пользователя.

Распознает те же значения матчеров, что и PreToolUse.

### PostToolUse

Запускается сразу после успешного завершения инструмента.

Распознает те же значения матчеров, что и PreToolUse.

### Notification

Запускается когда Claude Code отправляет уведомления. Поддерживает матчеры для фильтрации по типу уведомления.

**Общие матчеры:**

* `permission_prompt` - Запросы разрешения от Claude Code
* `idle_prompt` - Когда Claude ждет ввода пользователя (после 60+ секунд простоя)
* `auth_success` - Уведомления об успешной аутентификации
* `elicitation_dialog` - Когда Claude Code нуждается в вводе для выявления инструмента MCP

Вы можете использовать матчеры для запуска различных hooks для разных типов уведомлений или опустить матчер для запуска hooks для всех уведомлений.

**Пример: Различные уведомления для разных типов**

```json  theme={null}
{
  "hooks": {
    "Notification": [
      {
        "matcher": "permission_prompt",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/permission-alert.sh"
          }
        ]
      },
      {
        "matcher": "idle_prompt",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/idle-notification.sh"
          }
        ]
      }
    ]
  }
}
```

### UserPromptSubmit

Запускается когда пользователь отправляет подсказку, перед обработкой Claude. Это позволяет вам
добавить дополнительный контекст на основе подсказки/разговора, валидировать подсказки или
блокировать определенные типы подсказок.

### Stop

Запускается когда основной agent Claude Code завершил ответ. Не запускается если
остановка произошла из-за прерывания пользователем.

### SubagentStop

Запускается когда Claude Code subagent (вызов инструмента Task) завершил ответ.

### PreCompact

Запускается перед тем, как Claude Code собирается выполнить операцию compact.

**Матчеры:**

* `manual` - Вызвано из `/compact`
* `auto` - Вызвано из auto-compact (из-за полного контекстного окна)

### SessionStart

Запускается когда Claude Code запускает новый сеанс или возобновляет существующий сеанс (который
в настоящее время запускает новый сеанс под капотом). Полезно для загрузки контекста разработки, такого как существующие проблемы или недавние изменения вашей кодовой базы, установка зависимостей или настройка переменных окружения.

**Матчеры:**

* `startup` - Вызвано из startup
* `resume` - Вызвано из `--resume`, `--continue` или `/resume`
* `clear` - Вызвано из `/clear`
* `compact` - Вызвано из auto или manual compact.

#### Сохранение переменных окружения

SessionStart hooks имеют доступ к переменной окружения `CLAUDE_ENV_FILE`, которая предоставляет путь к файлу, где вы можете сохранять переменные окружения для последующих bash команд.

**Пример: Установка отдельных переменных окружения**

```bash  theme={null}
#!/bin/bash

if [ -n "$CLAUDE_ENV_FILE" ]; then
  echo 'export NODE_ENV=production' >> "$CLAUDE_ENV_FILE"
  echo 'export API_KEY=your-api-key' >> "$CLAUDE_ENV_FILE"
  echo 'export PATH="$PATH:./node_modules/.bin"' >> "$CLAUDE_ENV_FILE"
fi

exit 0
```

**Пример: Сохранение всех изменений окружения из hook**

Когда ваша настройка изменяет окружение (например, `nvm use`), захватите и сохраните все изменения путем сравнения окружения:

```bash  theme={null}
#!/bin/bash

ENV_BEFORE=$(export -p | sort)

# Run your setup commands that modify the environment
source ~/.nvm/nvm.sh
nvm use 20

if [ -n "$CLAUDE_ENV_FILE" ]; then
  ENV_AFTER=$(export -p | sort)
  comm -13 <(echo "$ENV_BEFORE") <(echo "$ENV_AFTER") >> "$CLAUDE_ENV_FILE"
fi

exit 0
```

Любые переменные, записанные в этот файл, будут доступны во всех последующих bash командах, которые Claude Code выполняет во время сеанса.

<Note>
  `CLAUDE_ENV_FILE` доступна только для SessionStart hooks. Другие типы hooks не имеют доступа к этой переменной.
</Note>

### SessionEnd

Запускается когда сеанс Claude Code завершается. Полезно для задач очистки, логирования
статистики сеанса или сохранения состояния сеанса.

Поле `reason` во входных данных hook будет одним из:

* `clear` - Сеанс очищен командой /clear
* `logout` - Пользователь вышел
* `prompt_input_exit` - Пользователь вышел во время видимого ввода подсказки
* `other` - Другие причины выхода

## Входные данные Hook

Hooks получают JSON данные через stdin, содержащие информацию о сеансе и
данные, специфичные для события:

```typescript  theme={null}
{
  // Common fields
  session_id: string
  transcript_path: string  // Path to conversation JSON
  cwd: string              // The current working directory when the hook is invoked
  permission_mode: string  // Current permission mode: "default", "plan", "acceptEdits", "dontAsk", or "bypassPermissions"

  // Event-specific fields
  hook_event_name: string
  ...
}
```

### Входные данные PreToolUse

Точная схема для `tool_input` зависит от инструмента.

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_use_id": "toolu_01ABC123..."
}
```

### Входные данные PostToolUse

Точная схема для `tool_input` и `tool_response` зависит от инструмента.

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.txt",
    "content": "file content"
  },
  "tool_response": {
    "filePath": "/path/to/file.txt",
    "success": true
  },
  "tool_use_id": "toolu_01ABC123..."
}
```

### Входные данные Notification

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "Notification",
  "message": "Claude needs your permission to use Bash",
  "notification_type": "permission_prompt"
}
```

### Входные данные UserPromptSubmit

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "Write a function to calculate the factorial of a number"
}
```

### Входные данные Stop и SubagentStop

`stop_hook_active` имеет значение true когда Claude Code уже продолжает работу в результате
stop hook. Проверьте это значение или обработайте транскрипт, чтобы предотвратить Claude Code
от бесконечного выполнения.

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "permission_mode": "default",
  "hook_event_name": "Stop",
  "stop_hook_active": true
}
```

### Входные данные PreCompact

Для `manual`, `custom_instructions` поступает из того, что пользователь передает в
`/compact`. Для `auto`, `custom_instructions` пуста.

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "permission_mode": "default",
  "hook_event_name": "PreCompact",
  "trigger": "manual",
  "custom_instructions": ""
}
```

### Входные данные SessionStart

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "permission_mode": "default",
  "hook_event_name": "SessionStart",
  "source": "startup"
}
```

### Входные данные SessionEnd

```json  theme={null}
{
  "session_id": "abc123",
  "transcript_path": "~/.claude/projects/.../00893aaf-19fa-41d2-8238-13269b9b3ca0.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "SessionEnd",
  "reason": "exit"
}
```

## Выходные данные Hook

Существует два взаимоисключающих способа для hooks возвращать выходные данные обратно в Claude Code. Выходные данные
сообщают, блокировать ли и любую обратную связь, которая должна быть показана Claude
и пользователю.

### Простой: Код выхода

Hooks сообщают статус через коды выхода, stdout и stderr:

* **Код выхода 0**: Успех. `stdout` показывается пользователю в режиме verbose
  (ctrl+o), за исключением `UserPromptSubmit` и `SessionStart`, где stdout
  добавляется в контекст. JSON выход в `stdout` анализируется для структурированного управления
  (см. [Продвинутый: JSON выход](#advanced-json-output)).
* **Код выхода 2**: Блокирующая ошибка. Используется только `stderr` как сообщение об ошибке
  и передается обратно Claude. Формат `[command]: {stderr}`. JSON в `stdout`
  **не** обрабатывается для кода выхода 2. См. поведение для каждого события hook ниже.
* **Другие коды выхода**: Неблокирующая ошибка. `stderr` показывается пользователю в режиме verbose (ctrl+o) с
  форматом `Failed with non-blocking status code: {stderr}`. Если `stderr` пуста,
  показывает `No stderr output`. Выполнение продолжается.

<Warning>
  Напоминание: Claude Code не видит stdout если код выхода 0, за исключением
  hook `UserPromptSubmit` где stdout вводится как контекст.
</Warning>

#### Поведение кода выхода 2

| Событие Hook        | Поведение                                                                               |
| ------------------- | --------------------------------------------------------------------------------------- |
| `PreToolUse`        | Блокирует вызов инструмента, показывает stderr Claude                                   |
| `PermissionRequest` | Отрицает разрешение, показывает stderr Claude                                           |
| `PostToolUse`       | Показывает stderr Claude (инструмент уже запущен)                                       |
| `Notification`      | N/A, показывает stderr только пользователю                                              |
| `UserPromptSubmit`  | Блокирует обработку подсказки, стирает подсказку, показывает stderr только пользователю |
| `Stop`              | Блокирует остановку, показывает stderr Claude                                           |
| `SubagentStop`      | Блокирует остановку, показывает stderr Claude subagent                                  |
| `PreCompact`        | N/A, показывает stderr только пользователю                                              |
| `SessionStart`      | N/A, показывает stderr только пользователю                                              |
| `SessionEnd`        | N/A, показывает stderr только пользователю                                              |

### Продвинутый: JSON выход

Hooks могут возвращать структурированный JSON в `stdout` для более сложного управления.

<Warning>
  JSON выход обрабатывается только когда hook выходит с кодом 0. Если ваш hook
  выходит с кодом 2 (блокирующая ошибка), текст `stderr` используется напрямую—любой JSON в `stdout`
  игнорируется. Для других ненулевых кодов выхода, только `stderr` показывается пользователю в режиме verbose (ctrl+o).
</Warning>

#### Общие поля JSON

Все типы hooks могут включать эти опциональные поля:

```json  theme={null}
{
  "continue": true, // Whether Claude should continue after hook execution (default: true)
  "stopReason": "string", // Message shown when continue is false

  "suppressOutput": true, // Hide stdout from transcript mode (default: false)
  "systemMessage": "string" // Optional warning message shown to the user
}
```

Если `continue` это false, Claude останавливает обработку после выполнения hooks.

* Для `PreToolUse`, это отличается от `"permissionDecision": "deny"`, который
  только блокирует конкретный вызов инструмента и предоставляет автоматическую обратную связь Claude.
* Для `PostToolUse`, это отличается от `"decision": "block"`, который
  предоставляет автоматизированную обратную связь Claude.
* Для `UserPromptSubmit`, это предотвращает обработку подсказки.
* Для `Stop` и `SubagentStop`, это имеет приоритет над любым
  `"decision": "block"` выходом.
* Во всех случаях, `"continue" = false` имеет приоритет над любым
  `"decision": "block"` выходом.

`stopReason` сопровождает `continue` с причиной, показанной пользователю, не показанной
Claude.

#### Управление решениями `PreToolUse`

Hooks `PreToolUse` могут управлять тем, продолжается ли вызов инструмента.

* `"allow"` обходит систему разрешений. `permissionDecisionReason` показывается
  пользователю, но не Claude.
* `"deny"` предотвращает выполнение вызова инструмента. `permissionDecisionReason` показывается
  Claude.
* `"ask"` просит пользователя подтвердить вызов инструмента в UI.
  `permissionDecisionReason` показывается пользователю, но не Claude.

Кроме того, hooks могут изменять входные данные инструмента перед выполнением используя `updatedInput`:

* `updatedInput` изменяет параметры входных данных инструмента перед выполнением инструмента
* Комбинируйте с `"permissionDecision": "allow"` для изменения входных данных и автоматического одобрения вызова инструмента
* Комбинируйте с `"permissionDecision": "ask"` для изменения входных данных и показа их пользователю для подтверждения

```json  theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "My reason here",
    "updatedInput": {
      "field_to_modify": "new value"
    }
  }
}
```

<Note>
  Поля `decision` и `reason` устарели для hooks PreToolUse.
  Используйте `hookSpecificOutput.permissionDecision` и
  `hookSpecificOutput.permissionDecisionReason` вместо этого. Устаревшие поля
  `"approve"` и `"block"` соответствуют `"allow"` и `"deny"` соответственно.
</Note>

#### Управление решениями `PermissionRequest`

Hooks `PermissionRequest` могут разрешать или отрицать запросы разрешения, показанные пользователю.

* Для `"behavior": "allow"` вы также можете опционально передать `"updatedInput"`, который изменяет параметры входных данных инструмента перед выполнением инструмента.
* Для `"behavior": "deny"` вы также можете опционально передать строку `"message"`, которая говорит модели, почему разрешение было отрицано, и булево значение `"interrupt"`, которое остановит Claude.

```json  theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow",
      "updatedInput": {
        "command": "npm run lint"
      }
    }
  }
}
```

#### Управление решениями `PostToolUse`

Hooks `PostToolUse` могут предоставлять обратную связь Claude после выполнения инструмента.

* `"block"` автоматически подсказывает Claude с `reason`.
* `undefined` ничего не делает. `reason` игнорируется.
* `"hookSpecificOutput.additionalContext"` добавляет контекст для Claude для рассмотрения.

```json  theme={null}
{
  "decision": "block" | undefined,
  "reason": "Explanation for decision",
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Additional information for Claude"
  }
}
```

#### Управление решениями `UserPromptSubmit`

Hooks `UserPromptSubmit` могут управлять тем, обрабатывается ли пользовательская подсказка и добавлять контекст.

**Добавление контекста (код выхода 0):**
Существует два способа добавить контекст к разговору:

1. **Простой текст stdout** (проще): Любой не-JSON текст, написанный в stdout, добавляется
   как контекст. Это самый простой способ внедрить информацию.

2. **JSON с `additionalContext`** (структурированный): Используйте формат JSON ниже для
   большего контроля. Поле `additionalContext` добавляется как контекст.

Оба метода работают с кодом выхода 0. Простой stdout показывается как выход hook в
транскрипте; `additionalContext` добавляется более дискретно.

**Блокирование подсказок:**

* `"decision": "block"` предотвращает обработку подсказки. Отправленная
  подсказка стирается из контекста. `"reason"` показывается пользователю, но не добавляется
  в контекст.
* `"decision": undefined` (или опущено) позволяет подсказке продолжаться нормально.

```json  theme={null}
{
  "decision": "block" | undefined,
  "reason": "Explanation for decision",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "My additional context here"
  }
}
```

<Note>
  Формат JSON не требуется для простых случаев использования. Для добавления контекста, вы можете напечатать простой текст в stdout с кодом выхода 0. Используйте JSON когда вам нужно
  блокировать подсказки или вы хотите более структурированный контроль.
</Note>

#### Управление решениями `Stop`/`SubagentStop`

Hooks `Stop` и `SubagentStop` могут управлять тем, должен ли Claude продолжить.

* `"block"` предотвращает Claude от остановки. Вы должны заполнить `reason` для Claude
  чтобы знать как продолжить.
* `undefined` позволяет Claude остановиться. `reason` игнорируется.

```json  theme={null}
{
  "decision": "block" | undefined,
  "reason": "Must be provided when Claude is blocked from stopping"
}
```

#### Управление решениями `SessionStart`

Hooks `SessionStart` позволяют вам загружать контекст в начале сеанса.

* `"hookSpecificOutput.additionalContext"` добавляет строку в контекст.
* Значения `additionalContext` из нескольких hooks объединяются.

```json  theme={null}
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "My additional context here"
  }
}
```

#### Управление решениями `SessionEnd`

Hooks `SessionEnd` запускаются когда сеанс завершается. Они не могут блокировать завершение сеанса
но могут выполнять задачи очистки.

#### Пример кода выхода: Валидация Bash команды

```python  theme={null}
#!/usr/bin/env python3
import json
import re
import sys

# Define validation rules as a list of (regex pattern, message) tuples
VALIDATION_RULES = [
    (
        r"\bgrep\b(?!.*\|)",
        "Use 'rg' (ripgrep) instead of 'grep' for better performance and features",
    ),
    (
        r"\bfind\s+\S+\s+-name\b",
        "Use 'rg --files | rg pattern' or 'rg --files -g pattern' instead of 'find -name' for better performance",
    ),
]


def validate_command(command: str) -> list[str]:
    issues = []
    for pattern, message in VALIDATION_RULES:
        if re.search(pattern, command):
            issues.append(message)
    return issues


try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})
command = tool_input.get("command", "")

if tool_name != "Bash" or not command:
    sys.exit(1)

# Validate the command
issues = validate_command(command)

if issues:
    for message in issues:
        print(f"• {message}", file=sys.stderr)
    # Exit code 2 blocks tool call and shows stderr to Claude
    sys.exit(2)
```

#### Пример JSON выхода: UserPromptSubmit для добавления контекста и валидации

<Note>
  Для hooks `UserPromptSubmit`, вы можете внедрить контекст используя любой метод:

  * **Простой текст stdout** с кодом выхода 0: Самый простой подход, печатает текст
  * **JSON выход** с кодом выхода 0: Используйте `"decision": "block"` для отклонения подсказок,
    или `additionalContext` для структурированного внедрения контекста

  Помните: Код выхода 2 использует только `stderr` для сообщения об ошибке. Для блокирования используя
  JSON (с пользовательской причиной), используйте `"decision": "block"` с кодом выхода 0.
</Note>

```python  theme={null}
#!/usr/bin/env python3
import json
import sys
import re
import datetime

# Load input from stdin
try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

prompt = input_data.get("prompt", "")

# Check for sensitive patterns
sensitive_patterns = [
    (r"(?i)\b(password|secret|key|token)\s*[:=]", "Prompt contains potential secrets"),
]

for pattern, message in sensitive_patterns:
    if re.search(pattern, prompt):
        # Use JSON output to block with a specific reason
        output = {
            "decision": "block",
            "reason": f"Security policy violation: {message}. Please rephrase your request without sensitive information."
        }
        print(json.dumps(output))
        sys.exit(0)

# Add current time to context
context = f"Current time: {datetime.datetime.now()}"
print(context)

"""
The following is also equivalent:
print(json.dumps({
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": context,
  },
}))
"""

# Allow the prompt to proceed with the additional context
sys.exit(0)
```

#### Пример JSON выхода: PreToolUse с одобрением

```python  theme={null}
#!/usr/bin/env python3
import json
import sys

# Load input from stdin
try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
    sys.exit(1)

tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})

# Example: Auto-approve file reads for documentation files
if tool_name == "Read":
    file_path = tool_input.get("file_path", "")
    if file_path.endswith((".md", ".mdx", ".txt", ".json")):
        # Use JSON output to auto-approve the tool call
        output = {
            "decision": "approve",
            "reason": "Documentation file auto-approved",
            "suppressOutput": True  # Don't show in verbose mode
        }
        print(json.dumps(output))
        sys.exit(0)

# For other cases, let the normal permission flow proceed
sys.exit(0)
```

## Работа с MCP инструментами

Claude Code hooks работают беспрепятственно с
[инструментами Model Context Protocol (MCP)](/ru/mcp). Когда MCP серверы
предоставляют инструменты, они появляются со специальным шаблоном имени, который вы можете сопоставить в
ваших hooks.

### Именование MCP инструментов

MCP инструменты следуют шаблону `mcp__<server>__<tool>`, например:

* `mcp__memory__create_entities` - Инструмент create entities сервера Memory
* `mcp__filesystem__read_file` - Инструмент read file сервера Filesystem
* `mcp__github__search_repositories` - Инструмент search сервера GitHub

### Конфигурирование hooks для MCP инструментов

Вы можете нацеливаться на конкретные MCP инструменты или целые MCP серверы:

```json  theme={null}
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__memory__.*",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Memory operation initiated' >> ~/mcp-operations.log"
          }
        ]
      },
      {
        "matcher": "mcp__.*__write.*",
        "hooks": [
          {
            "type": "command",
            "command": "/home/user/scripts/validate-mcp-write.py"
          }
        ]
      }
    ]
  }
}
```

## Примеры

<Tip>
  Для практических примеров, включая форматирование кода, уведомления и защиту файлов, см. [Больше примеров](/ru/hooks-guide#more-examples) в руководстве по началу работы.
</Tip>

## Соображения безопасности

### Отказ от ответственности

**ИСПОЛЬЗУЙТЕ НА СВОЙ РИСК**: Hooks Claude Code выполняют произвольные shell команды на
вашей системе автоматически. Используя hooks, вы признаете, что:

* Вы несете исключительную ответственность за команды, которые вы настраиваете
* Hooks могут изменять, удалять или получать доступ к любым файлам, к которым может получить доступ ваша учетная запись пользователя
* Вредоносные или плохо написанные hooks могут вызвать потерю данных или повреждение системы
* Anthropic не предоставляет гарантию и не несет ответственность за любые убытки
  в результате использования hooks
* Вы должны тщательно тестировать hooks в безопасной среде перед использованием в production

Всегда проверяйте и понимайте любые команды hook перед добавлением их в
вашу конфигурацию.

### Лучшие практики безопасности

Вот некоторые ключевые практики для написания более безопасных hooks:

1. **Валидируйте и санитизируйте входные данные** - Никогда не доверяйте входным данным вслепую
2. **Всегда цитируйте переменные shell** - Используйте `"$VAR"` не `$VAR`
3. **Блокируйте обход пути** - Проверяйте наличие `..` в путях файлов
4. **Используйте абсолютные пути** - Указывайте полные пути для скриптов (используйте
   "\$CLAUDE\_PROJECT\_DIR" для пути проекта)
5. **Пропускайте чувствительные файлы** - Избегайте `.env`, `.git/`, ключей и т.д.

### Безопасность конфигурации

Прямые редактирования hooks в файлах настроек не вступают в силу немедленно. Claude
Code:

1. Захватывает снимок hooks при запуске
2. Использует этот снимок на протяжении сеанса
3. Предупреждает если hooks изменяются извне
4. Требует проверки в меню `/hooks` для применения изменений

Это предотвращает вредоносные изменения hooks от влияния на ваш текущий сеанс.

## Детали выполнения Hook

* **Timeout**: Лимит выполнения 60 секунд по умолчанию, настраивается для каждой команды.
  * Timeout для отдельной команды не влияет на другие команды.
* **Параллелизация**: Все совпадающие hooks запускаются параллельно
* **Дедупликация**: Несколько идентичных команд hook автоматически дедублируются
* **Окружение**: Запускается в текущей директории с окружением Claude Code
  * Переменная окружения `CLAUDE_PROJECT_DIR` доступна и содержит
    абсолютный путь к корневой директории проекта (где был запущен Claude Code)
  * Переменная окружения `CLAUDE_CODE_REMOTE` указывает, запущен ли hook в удаленной (веб) среде (`"true"`) или локальной CLI среде (не установлена или пуста). Используйте это для запуска различной логики в зависимости от контекста выполнения.
* **Входные данные**: JSON через stdin
* **Выходные данные**:
  * PreToolUse/PermissionRequest/PostToolUse/Stop/SubagentStop: Прогресс показывается в режиме verbose (ctrl+o)
  * Notification/SessionEnd: Логируется только в debug (`--debug`)
  * UserPromptSubmit/SessionStart: stdout добавляется как контекст для Claude

## Отладка

### Базовое устранение неполадок

Если ваши hooks не работают:

1. **Проверьте конфигурацию** - Запустите `/hooks` чтобы увидеть, зарегистрирован ли ваш hook
2. **Проверьте синтаксис** - Убедитесь, что ваш JSON настроек валиден
3. **Тестируйте команды** - Сначала запустите команды hook вручную
4. **Проверьте разрешения** - Убедитесь, что скрипты исполняемы
5. **Просмотрите логи** - Используйте `claude --debug` чтобы увидеть детали выполнения hook

Общие проблемы:

* **Кавычки не экранированы** - Используйте `\"` внутри JSON строк
* **Неправильный матчер** - Проверьте, что имена инструментов совпадают точно (чувствительны к регистру)
* **Команда не найдена** - Используйте полные пути для скриптов

### Продвинутая отладка

Для сложных проблем с hooks:

1. **Проверьте выполнение hook** - Используйте `claude --debug` чтобы увидеть детальное выполнение hook
2. **Валидируйте JSON схемы** - Тестируйте входные/выходные данные hook с внешними инструментами
3. **Проверьте переменные окружения** - Проверьте, что окружение Claude Code корректно
4. **Тестируйте граничные случаи** - Попробуйте hooks с необычными путями файлов или входными данными
5. **Мониторьте ресурсы системы** - Проверьте на истощение ресурсов во время выполнения hook
6. **Используйте структурированное логирование** - Реализуйте логирование в ваших скриптах hook

### Пример выхода отладки

Используйте `claude --debug` чтобы увидеть детали выполнения hook:

```
[DEBUG] Executing hooks for PostToolUse:Write
[DEBUG] Getting matching hook commands for PostToolUse with query: Write
[DEBUG] Found 1 hook matchers in settings
[DEBUG] Matched 1 hooks for query "Write"
[DEBUG] Found 1 hook commands to execute
[DEBUG] Executing hook command: <Your command> with timeout 60000ms
[DEBUG] Hook command completed with status 0: <Your stdout>
```

Сообщения о прогрессе появляются в режиме verbose (ctrl+o) показывая:

* Какой hook запускается
* Выполняемая команда
* Статус успеха/неудачи
* Выходные данные или сообщения об ошибках
