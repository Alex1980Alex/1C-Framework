---
name: claude-code-github-actions
description: "Claude Code GitHub Actions: CI/CD интеграция, автоматизация PR, code review, настройка workflow, trigger events, конфигурация action v1.0. Триггеры: 'github actions', 'github action', 'CI/CD claude', 'PR automation', 'автоматизация PR', 'claude-code-action', 'code review CI', 'github workflow', '@claude trigger', 'автоматический review'."
---

# Claude Code GitHub Actions

## Обзор

GitHub Action `anthropics/claude-code-action@v1` позволяет Claude автоматически
обрабатывать PR, issues и scheduled задачи в CI/CD pipeline.

## Быстрый старт

### 1. Установить GitHub App

```bash
/install-github-app    # В Claude Code CLI
```

Или вручную: [github.com/apps/claude](https://github.com/apps/claude)

### 2. Добавить API ключ

GitHub repo → Settings → Secrets → `ANTHROPIC_API_KEY`

### 3. Создать workflow

`.github/workflows/claude.yml`:

```yaml
name: Claude Code
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
  issues:
    types: [opened, assigned]

jobs:
  claude:
    if: |
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
      github.event_name == 'issues'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      issues: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Параметры Action (v1.0)

| Параметр | Обяз. | Описание |
|----------|-------|----------|
| `anthropic_api_key` | Да* | API ключ Anthropic |
| `prompt` | Нет | Инструкции или `/review` |
| `claude_args` | Нет | CLI аргументы |
| `github_token` | Нет | GitHub token (для GitHub App) |
| `trigger_phrase` | Нет | Фраза триггера (default: `@claude`) |
| `use_bedrock` | Нет | `"true"` для AWS Bedrock |
| `use_vertex` | Нет | `"true"` для Google Vertex AI |

## Полезные CLI аргументы (claude_args)

```yaml
claude_args: "--max-turns 5"                    # Лимит ходов
claude_args: "--model claude-sonnet-4-5-20250929"  # Конкретная модель
claude_args: "--mcp-config ./mcp.json"          # MCP серверы
claude_args: "--allowed-tools Read,Grep,Glob"   # Ограничить инструменты
claude_args: "--system-prompt 'You are a security reviewer'"  # Промпт
```

## Типовые workflow

### Code Review на каждый PR

```yaml
on:
  pull_request:
    types: [opened, synchronize]

steps:
  - uses: anthropics/claude-code-action@v1
    with:
      anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
      prompt: |
        Review this PR for:
        - Code quality and readability
        - Security vulnerabilities
        - Performance issues
        Provide specific suggestions with code examples.
```

### По расписанию (ежедневный аудит)

```yaml
on:
  schedule:
    - cron: "0 9 * * *"

steps:
  - uses: anthropics/claude-code-action@v1
    with:
      anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
      prompt: "Audit the codebase for security issues and outdated dependencies"
```

### Trigger по комментарию

В PR или issue напишите: `@claude review this code` или `@claude fix the linting errors`.

## Миграция Beta → v1.0

| Старый параметр | Новый параметр |
|----------------|----------------|
| `mode: "tag"` | Удалён (авто-определение) |
| `direct_prompt` | `prompt` |
| `custom_instructions` | `claude_args: --system-prompt` |
| `max_turns` | `claude_args: --max-turns` |
| `model` | `claude_args: --model` |

## Оптимизация стоимости

- Используйте конкретные `@claude` команды (не broad scans)
- Ограничьте `--max-turns` (default: 10)
- Настройте workflow-level `timeout-minutes`
- Используйте `concurrency` для ограничения параллельных запусков

## Источники

- `docs/documentation/Claude Code Docs/1. Начало работы/Claude Code GitHub Actions.md`
