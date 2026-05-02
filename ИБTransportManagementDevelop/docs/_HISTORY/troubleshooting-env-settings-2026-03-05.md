# Проблема: Отсутствует секция env в settings.local.json

Дата: 2026-03-05

## Ситуация

Файл `C:\Users\AlexT\.claude\settings.local.json` содержит только:
- `permissions`
- `hooks`

Секция `env` отсутствует.

## Решение

Настройки модели Claude Code задаются через **переменные окружения**, а не через файл конфигурации:

```bash
# Текущие значения (glm-4.7)
set ANTHROPIC_DEFAULT_SONNET_MODEL=glm-4.7
set ANTHROPIC_DEFAULT_OPUS_MODEL=glm-4.7
set ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.5-air

# Для переключения на glm-5
set ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5
set ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5
```

## Почему не работает секция env

1. Файл `settings.local.json` перезаписывается хуками (permissions + hooks)
2. Переменные окружения имеют приоритет над настройками в файле
3. Для постоянного сохранения нужно использовать системные переменные окружения Windows

## MCP серверы

MCP серверы используют **glm-5** (настроено в `.mcp.json`):
- `ZAI_MODEL`: "glm-5"
- `DEEP_REASONING_MODEL`: "glm-5"

Только Claude Code CLI работает на glm-4.7.