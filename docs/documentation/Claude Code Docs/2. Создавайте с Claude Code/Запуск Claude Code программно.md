> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Запуск Claude Code программно

> Используйте Agent SDK для программного запуска Claude Code из CLI, Python или TypeScript.

[Agent SDK](https://platform.claude.com/docs/ru/agent-sdk/overview) предоставляет вам те же инструменты, цикл агента и управление контекстом, которые питают Claude Code. Он доступен как CLI для скриптов и CI/CD, или как пакеты [Python](https://platform.claude.com/docs/ru/agent-sdk/python) и [TypeScript](https://platform.claude.com/docs/ru/agent-sdk/typescript) для полного программного управления.

<Note>
  CLI ранее назывался "режимом без интерфейса". Флаг `-p` и все параметры CLI работают так же.
</Note>

Для программного запуска Claude Code из CLI передайте `-p` с вашей подсказкой и любыми [параметрами CLI](/ru/cli-reference):

```bash  theme={null}
claude -p "Find and fix the bug in auth.py" --allowedTools "Read,Edit,Bash"
```

На этой странице рассматривается использование Agent SDK через CLI (`claude -p`). Для пакетов SDK Python и TypeScript со структурированными выходами, обратными вызовами одобрения инструментов и собственными объектами сообщений см. [полную документацию Agent SDK](https://platform.claude.com/docs/ru/agent-sdk/overview).

## Базовое использование

Добавьте флаг `-p` (или `--print`) к любой команде `claude` для её неинтерактивного запуска. Все [параметры CLI](/ru/cli-reference) работают с `-p`, включая:

* `--continue` для [продолжения разговоров](#continue-conversations)
* `--allowedTools` для [автоматического одобрения инструментов](#auto-approve-tools)
* `--output-format` для [структурированного вывода](#get-structured-output)

Этот пример задаёт Claude вопрос о вашей кодовой базе и выводит ответ:

```bash  theme={null}
claude -p "What does the auth module do?"
```

## Примеры

Эти примеры выделяют общие шаблоны CLI.

### Получение структурированного вывода

Используйте `--output-format` для управления тем, как возвращаются ответы:

* `text` (по умолчанию): простой текстовый вывод
* `json`: структурированный JSON с результатом, ID сеанса и метаданными
* `stream-json`: JSON с разделением по новым строкам для потоковой передачи в реальном времени

Этот пример возвращает сводку проекта в виде JSON с метаданными сеанса, с текстовым результатом в поле `result`:

```bash  theme={null}
claude -p "Summarize this project" --output-format json
```

Для получения вывода, соответствующего определённой схеме, используйте `--output-format json` с `--json-schema` и определением [JSON Schema](https://json-schema.org/). Ответ включает метаданные о запросе (ID сеанса, использование и т. д.) со структурированным выводом в поле `structured_output`.

Этот пример извлекает имена функций и возвращает их как массив строк:

```bash  theme={null}
claude -p "Extract the main function names from auth.py" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"functions":{"type":"array","items":{"type":"string"}}},"required":["functions"]}'
```

<Tip>
  Используйте инструмент, такой как [jq](https://jqlang.github.io/jq/), для анализа ответа и извлечения определённых полей:

  ```bash  theme={null}
  # Extract the text result
  claude -p "Summarize this project" --output-format json | jq -r '.result'

  # Extract structured output
  claude -p "Extract function names from auth.py" \
    --output-format json \
    --json-schema '{"type":"object","properties":{"functions":{"type":"array","items":{"type":"string"}}},"required":["functions"]}' \
    | jq '.structured_output'
  ```
</Tip>

### Автоматическое одобрение инструментов

Используйте `--allowedTools` для разрешения Claude использовать определённые инструменты без запроса. Этот пример запускает набор тестов и исправляет ошибки, позволяя Claude выполнять команды Bash и читать/редактировать файлы без запроса разрешения:

```bash  theme={null}
claude -p "Run the test suite and fix any failures" \
  --allowedTools "Bash,Read,Edit"
```

### Создание коммита

Этот пример проверяет поставленные в очередь изменения и создаёт коммит с соответствующим сообщением:

```bash  theme={null}
claude -p "Look at my staged changes and create an appropriate commit" \
  --allowedTools "Bash(git diff:*),Bash(git log:*),Bash(git status:*),Bash(git commit:*)"
```

Флаг `--allowedTools` использует [синтаксис правил разрешений](/ru/settings#permission-rule-syntax). Суффикс `:*` включает сопоставление по префиксу, поэтому `Bash(git diff:*)` разрешает любую команду, начинающуюся с `git diff`.

<Note>
  [Слэш-команды](/ru/slash-commands) такие как `/commit` доступны только в интерактивном режиме. В режиме `-p` опишите задачу, которую вы хотите выполнить.
</Note>

### Настройка системной подсказки

Используйте `--append-system-prompt` для добавления инструкций при сохранении поведения Claude Code по умолчанию. Этот пример передаёт diff PR в Claude и инструктирует его проверить наличие уязвимостей безопасности:

```bash  theme={null}
gh pr diff "$1" | claude -p \
  --append-system-prompt "You are a security engineer. Review for vulnerabilities." \
  --output-format json
```

См. [флаги системной подсказки](/ru/cli-reference#system-prompt-flags) для получения дополнительных параметров, включая `--system-prompt` для полной замены подсказки по умолчанию.

### Продолжение разговоров

Используйте `--continue` для продолжения самого последнего разговора или `--resume` с ID сеанса для продолжения определённого разговора. Этот пример запускает проверку, а затем отправляет дополнительные подсказки:

```bash  theme={null}
# First request
claude -p "Review this codebase for performance issues"

# Continue the most recent conversation
claude -p "Now focus on the database queries" --continue
claude -p "Generate a summary of all issues found" --continue
```

Если вы запускаете несколько разговоров, захватите ID сеанса для возобновления определённого:

```bash  theme={null}
session_id=$(claude -p "Start a review" --output-format json | jq -r '.session_id')
claude -p "Continue that review" --resume "$session_id"
```

## Следующие шаги

<CardGroup cols={2}>
  <Card title="Быстрый старт Agent SDK" icon="play" href="https://platform.claude.com/docs/ru/agent-sdk/quickstart">
    Создайте своего первого агента с помощью Python или TypeScript
  </Card>

  <Card title="Справочник CLI" icon="terminal" href="/ru/cli-reference">
    Изучите все флаги и параметры CLI
  </Card>

  <Card title="GitHub Actions" icon="github" href="/ru/github-actions">
    Используйте Agent SDK в рабочих процессах GitHub
  </Card>

  <Card title="GitLab CI/CD" icon="gitlab" href="/ru/gitlab-ci-cd">
    Используйте Agent SDK в конвейерах GitLab
  </Card>
</CardGroup>
