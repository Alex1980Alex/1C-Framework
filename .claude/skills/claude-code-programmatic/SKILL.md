---
name: claude-code-programmatic
description: "Программный запуск Claude Code: headless mode (-p), Agent SDK, structured output, JSON schema, streaming, продолжение сессий, Ralph Wiggum автономные циклы. Триггеры: 'headless', 'programmatic', 'программный запуск', 'agent sdk', 'structured output', 'json schema', '-p flag', 'print mode', 'автоматизация claude', 'ralph wiggum', 'автономный цикл', 'autonomous loop', 'stream-json', 'claude -p', 'скрипт с claude', 'CI pipeline claude'."
---

# Программный запуск Claude Code

## Headless режим (-p)

```bash
claude -p "query"                          # Выполнить и выйти
claude -p "query" --output-format json     # JSON вывод
claude -p "query" --output-format stream-json  # Потоковый JSON
```

### Форматы вывода

| Формат | Описание |
|--------|----------|
| `text` | Только текст ответа (default) |
| `json` | `{ "result": "...", "session_id": "...", "usage": {...} }` |
| `stream-json` | Построчный JSON (line-delimited) |

## Structured Output (JSON Schema)

```bash
claude -p "Extract functions from auth.py" \
  --output-format json \
  --json-schema '{
    "type": "object",
    "properties": {
      "functions": {
        "type": "array",
        "items": { "type": "string" }
      }
    },
    "required": ["functions"]
  }'
```

Результат в поле `structured_output` JSON-ответа.

## Управление инструментами

### Авто-одобрение

```bash
claude -p "Run tests and fix failures" \
  --allowedTools "Bash" "Read" "Edit"
```

### Конкретные команды

```bash
claude -p "Commit changes" \
  --allowedTools "Bash(git diff:*)" "Bash(git commit:*)" "Bash(git log:*)"
```

### Ограничение доступных инструментов

```bash
claude -p "Analyze code" --tools "Read,Grep,Glob"     # Только чтение
claude -p "Help me" --tools ""                         # Без инструментов
```

## Системный промпт

```bash
# Полная замена
claude -p "Review code" --system-prompt "You are a security engineer"

# Добавить к дефолтному
claude -p "Review code" --append-system-prompt "Focus on XSS vulnerabilities"

# Из файла
claude -p "Review" --system-prompt-file ./prompts/security.txt
claude -p "Review" --append-system-prompt-file ./prompts/rules.txt
```

## Продолжение сессий

```bash
# Первый запуск — получить session_id
session_id=$(claude -p "Start task" --output-format json | jq -r '.session_id')

# Продолжить
claude -p "Next step" --resume "$session_id"

# Или продолжить последнюю
claude -p "Next step" --continue
```

## Лимиты

```bash
claude -p "query" --max-turns 5           # Макс. ходов
claude -p "query" --max-budget-usd 5.00   # Макс. бюджет ($)
```

## Pipe входных данных

```bash
cat error.log | claude -p "Explain these errors"
git diff | claude -p "Review these changes"
cat schema.sql | claude -p "Generate TypeScript types"
```

## Подагенты через CLI

```bash
claude --agents '{
  "reviewer": {
    "description": "Code reviewer",
    "prompt": "Review code for quality",
    "tools": ["Read", "Grep"],
    "model": "haiku"
  }
}'
```

## Ralph Wiggum — автономные циклы

### Концепция

Ralph Wiggum = итеративный автономный цикл: Claude выполняет задачу,
проверяет результат, повторяет до завершения.

### Запуск

```bash
# Через скрипт фреймворка
scripts/ralph.bat --template reindex

# Доступные шаблоны
--template reindex          # Проверка pipeline индексации
--template test-coverage    # Увеличение покрытия до 80%+
--template evaluation       # RAGAS evaluation suite
--template documentation    # Добавление docstrings
--template lint             # Исправление linter warnings
```

### Протокол завершения

В CLAUDE.md:
```markdown
## Ralph Wiggum — Autonomous Loop Rules
- At start: check `git log --oneline -5` and `git diff --stat`
- Commit each meaningful change: `[RALPH] description`
- When ALL criteria met: output `RALPH_DONE`
- Alternative markers: `TASK_COMPLETE_OK`, `ALL_DONE`
- If impossible after 3 attempts: explain why
```

### Программный Ralph

```bash
claude -p "Fix all linting errors in src/" \
  --allowedTools "Bash" "Read" "Edit" \
  --append-system-prompt "Work iteratively. After each fix, run the linter.
    When all errors fixed, output RALPH_DONE." \
  --max-turns 50 \
  --max-budget-usd 10.00
```

## Интеграция в скрипты

### Python

```python
import subprocess
import json

result = subprocess.run(
    ["claude", "-p", "Analyze auth module", "--output-format", "json"],
    capture_output=True, text=True
)
data = json.loads(result.stdout)
print(data["result"])
```

### Bash

```bash
#!/bin/bash
result=$(claude -p "Check for security issues" --output-format json)
echo "$result" | jq -r '.result'
```

### CI Pipeline

```yaml
steps:
  - run: |
      claude -p "Run tests and report failures" \
        --output-format json \
        --allowedTools "Bash(npm test:*)" "Read" \
        --max-turns 3
```

## Источники

- `docs/documentation/Claude Code Docs/2. Создавайте с Claude Code/Запуск Claude Code программно.md`
- `docs/documentation/Claude Code Docs/2. Создавайте с Claude Code/Автономные циклы Ralph Wiggum.md`
