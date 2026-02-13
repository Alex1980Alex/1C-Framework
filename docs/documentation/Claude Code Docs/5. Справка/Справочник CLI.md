> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Справочник CLI

> Полный справочник по интерфейсу командной строки Claude Code, включая команды и флаги.

## Команды CLI

| Команда                         | Описание                                           | Пример                                       |
| :------------------------------ | :------------------------------------------------- | :------------------------------------------- |
| `claude`                        | Запустить интерактивный REPL                       | `claude`                                     |
| `claude "query"`                | Запустить REPL с начальным запросом                | `claude "explain this project"`              |
| `claude -p "query"`             | Запрос через SDK, затем выход                      | `claude -p "explain this function"`          |
| `cat file \| claude -p "query"` | Обработка переданного содержимого                  | `cat logs.txt \| claude -p "explain"`        |
| `claude -c`                     | Продолжить последний разговор в текущей директории | `claude -c`                                  |
| `claude -c -p "query"`          | Продолжить через SDK                               | `claude -c -p "Check for type errors"`       |
| `claude -r "<session>" "query"` | Возобновить сеанс по ID или имени                  | `claude -r "auth-refactor" "Finish this PR"` |
| `claude update`                 | Обновить до последней версии                       | `claude update`                              |
| `claude mcp`                    | Настроить серверы Model Context Protocol (MCP)     | См. [документацию Claude Code MCP](/ru/mcp). |

## Флаги CLI

Настройте поведение Claude Code с помощью этих флагов командной строки:

| Флаг                                   | Описание                                                                                                                                                                                                                                | Пример                                                                                             |
| :------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------- |
| `--add-dir`                            | Добавить дополнительные рабочие директории для доступа Claude (проверяет, что каждый путь существует как директория)                                                                                                                    | `claude --add-dir ../apps ../lib`                                                                  |
| `--agent`                              | Указать агента для текущего сеанса (переопределяет параметр `agent`)                                                                                                                                                                    | `claude --agent my-custom-agent`                                                                   |
| `--agents`                             | Определить пользовательские [подагенты](/ru/sub-agents) динамически через JSON (см. формат ниже)                                                                                                                                        | `claude --agents '{"reviewer":{"description":"Reviews code","prompt":"You are a code reviewer"}}'` |
| `--allow-dangerously-skip-permissions` | Включить обход разрешений как опцию без немедленной активации. Позволяет комбинировать с `--permission-mode` (использовать с осторожностью)                                                                                             | `claude --permission-mode plan --allow-dangerously-skip-permissions`                               |
| `--allowedTools`                       | Инструменты, которые выполняются без запроса разрешения. См. [синтаксис правила разрешения](/ru/settings#permission-rule-syntax) для сопоставления шаблонов. Чтобы ограничить доступные инструменты, используйте `--tools` вместо этого | `"Bash(git log:*)" "Bash(git diff:*)" "Read"`                                                      |
| `--append-system-prompt`               | Добавить пользовательский текст в конец системного приглашения по умолчанию (работает в интерактивном и режиме печати)                                                                                                                  | `claude --append-system-prompt "Always use TypeScript"`                                            |
| `--append-system-prompt-file`          | Загрузить дополнительный текст системного приглашения из файла и добавить к приглашению по умолчанию (только режим печати)                                                                                                              | `claude -p --append-system-prompt-file ./extra-rules.txt "query"`                                  |
| `--betas`                              | Заголовки бета-версии для включения в запросы API (только для пользователей с ключом API)                                                                                                                                               | `claude --betas interleaved-thinking`                                                              |
| `--chrome`                             | Включить [интеграцию браузера Chrome](/ru/chrome) для веб-автоматизации и тестирования                                                                                                                                                  | `claude --chrome`                                                                                  |
| `--continue`, `-c`                     | Загрузить последний разговор в текущей директории                                                                                                                                                                                       | `claude --continue`                                                                                |
| `--dangerously-skip-permissions`       | Пропустить все запросы разрешения (использовать с осторожностью)                                                                                                                                                                        | `claude --dangerously-skip-permissions`                                                            |
| `--debug`                              | Включить режим отладки с опциональной фильтрацией категорий (например, `"api,hooks"` или `"!statsig,!file"`)                                                                                                                            | `claude --debug "api,mcp"`                                                                         |
| `--disable-slash-commands`             | Отключить все навыки и слэш-команды для этого сеанса                                                                                                                                                                                    | `claude --disable-slash-commands`                                                                  |
| `--disallowedTools`                    | Инструменты, которые удаляются из контекста модели и не могут быть использованы                                                                                                                                                         | `"Bash(git log:*)" "Bash(git diff:*)" "Edit"`                                                      |
| `--fallback-model`                     | Включить автоматический переход на указанную модель, когда модель по умолчанию перегружена (только режим печати)                                                                                                                        | `claude -p --fallback-model sonnet "query"`                                                        |
| `--fork-session`                       | При возобновлении создать новый ID сеанса вместо повторного использования исходного (использовать с `--resume` или `--continue`)                                                                                                        | `claude --resume abc123 --fork-session`                                                            |
| `--ide`                                | Автоматически подключиться к IDE при запуске, если доступна ровно одна действительная IDE                                                                                                                                               | `claude --ide`                                                                                     |
| `--include-partial-messages`           | Включить частичные события потока в вывод (требует `--print` и `--output-format=stream-json`)                                                                                                                                           | `claude -p --output-format stream-json --include-partial-messages "query"`                         |
| `--input-format`                       | Указать формат входных данных для режима печати (опции: `text`, `stream-json`)                                                                                                                                                          | `claude -p --output-format json --input-format stream-json`                                        |
| `--json-schema`                        | Получить проверенный вывод JSON, соответствующий JSON Schema после завершения рабочего процесса агентом (только режим печати, см. [Структурированные выходы Agent SDK](https://docs.claude.com/en/docs/agent-sdk/structured-outputs))   | `claude -p --json-schema '{"type":"object","properties":{...}}' "query"`                           |
| `--max-budget-usd`                     | Максимальная сумма в долларах для траты на вызовы API перед остановкой (только режим печати)                                                                                                                                            | `claude -p --max-budget-usd 5.00 "query"`                                                          |
| `--max-turns`                          | Ограничить количество ходов агента (только режим печати). Выходит с ошибкой при достижении лимита. По умолчанию нет лимита                                                                                                              | `claude -p --max-turns 3 "query"`                                                                  |
| `--mcp-config`                         | Загрузить серверы MCP из JSON файлов или строк (разделены пробелом)                                                                                                                                                                     | `claude --mcp-config ./mcp.json`                                                                   |
| `--model`                              | Установить модель для текущего сеанса с псевдонимом для последней модели (`sonnet` или `opus`) или полным названием модели                                                                                                              | `claude --model claude-sonnet-4-5-20250929`                                                        |
| `--no-chrome`                          | Отключить [интеграцию браузера Chrome](/ru/chrome) для этого сеанса                                                                                                                                                                     | `claude --no-chrome`                                                                               |
| `--no-session-persistence`             | Отключить сохранение сеанса, чтобы сеансы не сохранялись на диск и не могли быть возобновлены (только режим печати)                                                                                                                     | `claude -p --no-session-persistence "query"`                                                       |
| `--output-format`                      | Указать формат вывода для режима печати (опции: `text`, `json`, `stream-json`)                                                                                                                                                          | `claude -p "query" --output-format json`                                                           |
| `--permission-mode`                    | Начать в указанном [режиме разрешения](/ru/iam#permission-modes)                                                                                                                                                                        | `claude --permission-mode plan`                                                                    |
| `--permission-prompt-tool`             | Указать инструмент MCP для обработки запросов разрешения в неинтерактивном режиме                                                                                                                                                       | `claude -p --permission-prompt-tool mcp_auth_tool "query"`                                         |
| `--plugin-dir`                         | Загрузить плагины из директорий только для этого сеанса (повторяемо)                                                                                                                                                                    | `claude --plugin-dir ./my-plugins`                                                                 |
| `--print`, `-p`                        | Вывести ответ без интерактивного режима (см. [документацию SDK](https://docs.claude.com/en/docs/agent-sdk) для деталей программного использования)                                                                                      | `claude -p "query"`                                                                                |
| `--remote`                             | Создать новый [веб-сеанс](/ru/claude-code-on-the-web) на claude.ai с предоставленным описанием задачи                                                                                                                                   | `claude --remote "Fix the login bug"`                                                              |
| `--resume`, `-r`                       | Возобновить определенный сеанс по ID или имени, или показать интерактивный выбор для выбора сеанса                                                                                                                                      | `claude --resume auth-refactor`                                                                    |
| `--session-id`                         | Использовать определенный ID сеанса для разговора (должен быть действительным UUID)                                                                                                                                                     | `claude --session-id "550e8400-e29b-41d4-a716-446655440000"`                                       |
| `--setting-sources`                    | Разделенный запятыми список источников параметров для загрузки (`user`, `project`, `local`)                                                                                                                                             | `claude --setting-sources user,project`                                                            |
| `--settings`                           | Путь к файлу параметров JSON или строка JSON для загрузки дополнительных параметров                                                                                                                                                     | `claude --settings ./settings.json`                                                                |
| `--strict-mcp-config`                  | Использовать только серверы MCP из `--mcp-config`, игнорируя все остальные конфигурации MCP                                                                                                                                             | `claude --strict-mcp-config --mcp-config ./mcp.json`                                               |
| `--system-prompt`                      | Заменить весь системный запрос пользовательским текстом (работает в интерактивном и режиме печати)                                                                                                                                      | `claude --system-prompt "You are a Python expert"`                                                 |
| `--system-prompt-file`                 | Загрузить системный запрос из файла, заменяя приглашение по умолчанию (только режим печати)                                                                                                                                             | `claude -p --system-prompt-file ./custom-prompt.txt "query"`                                       |
| `--teleport`                           | Возобновить [веб-сеанс](/ru/claude-code-on-the-web) в вашем локальном терминале                                                                                                                                                         | `claude --teleport`                                                                                |
| `--tools`                              | Ограничить, какие встроенные инструменты может использовать Claude (работает в интерактивном и режиме печати). Используйте `""` для отключения всех, `"default"` для всех или названия инструментов как `"Bash,Edit,Read"`              | `claude --tools "Bash,Edit,Read"`                                                                  |
| `--verbose`                            | Включить подробное логирование, показывает полный вывод по ходам (полезно для отладки в режиме печати и интерактивном режиме)                                                                                                           | `claude --verbose`                                                                                 |
| `--version`, `-v`                      | Вывести номер версии                                                                                                                                                                                                                    | `claude -v`                                                                                        |

<Tip>
  Флаг `--output-format json` особенно полезен для написания скриптов и
  автоматизации, позволяя вам программно анализировать ответы Claude.
</Tip>

### Формат флага agents

Флаг `--agents` принимает объект JSON, который определяет один или несколько пользовательских подагентов. Каждый подагент требует уникального имени (как ключ) и объекта определения со следующими полями:

| Поле          | Обязательно | Описание                                                                                                                                            |
| :------------ | :---------- | :-------------------------------------------------------------------------------------------------------------------------------------------------- |
| `description` | Да          | Описание на естественном языке того, когда должен быть вызван подагент                                                                              |
| `prompt`      | Да          | Системный запрос, который направляет поведение подагента                                                                                            |
| `tools`       | Нет         | Массив конкретных инструментов, которые может использовать подагент (например, `["Read", "Edit", "Bash"]`). Если опущено, наследует все инструменты |
| `model`       | Нет         | Псевдоним модели для использования: `sonnet`, `opus` или `haiku`. Если опущено, использует модель подагента по умолчанию                            |

Пример:

```bash  theme={null}
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer. Use proactively after code changes.",
    "prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  },
  "debugger": {
    "description": "Debugging specialist for errors and test failures.",
    "prompt": "You are an expert debugger. Analyze errors, identify root causes, and provide fixes."
  }
}'
```

Для получения дополнительной информации о создании и использовании подагентов см. [документацию подагентов](/ru/sub-agents).

### Флаги системного запроса

Claude Code предоставляет четыре флага для настройки системного запроса, каждый служит разной цели:

| Флаг                          | Поведение                                             | Режимы                 | Вариант использования                                                         |
| :---------------------------- | :---------------------------------------------------- | :--------------------- | :---------------------------------------------------------------------------- |
| `--system-prompt`             | **Заменяет** весь запрос по умолчанию                 | Интерактивный + Печать | Полный контроль над поведением и инструкциями Claude                          |
| `--system-prompt-file`        | **Заменяет** содержимым файла                         | Только печать          | Загрузить запросы из файлов для воспроизводимости и контроля версий           |
| `--append-system-prompt`      | **Добавляет** к запросу по умолчанию                  | Интерактивный + Печать | Добавить конкретные инструкции, сохраняя поведение Claude Code по умолчанию   |
| `--append-system-prompt-file` | **Добавляет** содержимое файла к запросу по умолчанию | Только печать          | Загрузить дополнительные инструкции из файлов, сохраняя значения по умолчанию |

**Когда использовать каждый:**

* **`--system-prompt`**: Используйте, когда вам нужен полный контроль над системным запросом Claude. Это удаляет все инструкции Claude Code по умолчанию, давая вам чистый лист.
  ```bash  theme={null}
  claude --system-prompt "You are a Python expert who only writes type-annotated code"
  ```

* **`--system-prompt-file`**: Используйте, когда вы хотите загрузить пользовательский запрос из файла, полезно для согласованности команды или контролируемых версией шаблонов запросов.
  ```bash  theme={null}
  claude -p --system-prompt-file ./prompts/code-review.txt "Review this PR"
  ```

* **`--append-system-prompt`**: Используйте, когда вы хотите добавить конкретные инструкции, сохраняя возможности Claude Code по умолчанию. Это самый безопасный вариант для большинства случаев использования.
  ```bash  theme={null}
  claude --append-system-prompt "Always use TypeScript and include JSDoc comments"
  ```

* **`--append-system-prompt-file`**: Используйте, когда вы хотите добавить инструкции из файла, сохраняя значения Claude Code по умолчанию. Полезно для контролируемых версией дополнений.
  ```bash  theme={null}
  claude -p --append-system-prompt-file ./prompts/style-rules.txt "Review this PR"
  ```

`--system-prompt` и `--system-prompt-file` являются взаимоисключающими. Флаги добавления могут использоваться вместе с любым флагом замены.

Для большинства случаев использования рекомендуется `--append-system-prompt` или `--append-system-prompt-file`, так как они сохраняют встроенные возможности Claude Code, добавляя ваши пользовательские требования. Используйте `--system-prompt` или `--system-prompt-file` только когда вам нужен полный контроль над системным запросом.

## См. также

* [Расширение Chrome](/ru/chrome) - Веб-автоматизация и веб-тестирование
* [Интерактивный режим](/ru/interactive-mode) - Ярлыки, режимы ввода и интерактивные функции
* [Слэш-команды](/ru/slash-commands) - Команды интерактивного сеанса
* [Руководство быстрого старта](/ru/quickstart) - Начало работы с Claude Code
* [Общие рабочие процессы](/ru/common-workflows) - Продвинутые рабочие процессы и шаблоны
* [Параметры](/ru/settings) - Опции конфигурации
* [Документация SDK](https://docs.claude.com/en/docs/agent-sdk) - Программное использование и интеграции
