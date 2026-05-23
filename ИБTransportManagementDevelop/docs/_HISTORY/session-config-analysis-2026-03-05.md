# Анализ настроек модели после перезагрузки терминала

Дата: 2026-03-05

## Текущее состояние модели

| Компонент | Модель | Настроено в |
|-----------|--------|-------------|
| Claude Code CLI | **glm-4.7** | Environment Variables |
| MCP серверы (Z.AI) | **glm-5** | .mcp.json |
| Haiku | glm-4.5-air | Environment Variables |

## Переменные окружения

```
ANTHROPIC_DEFAULT_SONNET_MODEL=glm-4.7
ANTHROPIC_DEFAULT_OPUS_MODEL=glm-4.7
ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.5-air
ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
```

## Как переключить на glm-5

Для Claude Code нужно изменить переменные окружения перед запуском:

```bash
set ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5
set ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5
```

MCP серверы уже используют glm-5 (ZAI_MODEL: "glm-5" в .mcp.json).

## Файлы конфигурации

1. `C:\Users\AlexT\.claude\settings.json` - глобальные настройки
2. `C:\Users\AlexT\.claude\settings.local.json` - локальные настройки (permissions, hooks)
3. `.mcp.json` - настройки MCP серверов (ZAI_MODEL: glm-5)
4. `cache/active-project.json` - активный Serena проект

## Примечание

Секция "env" отсутствует в `C:\Users\AlexT\.claude\settings.local.json`.
Настройки модели задаются через переменные окружения, а не через файл конфигурации.

## Активный проект Serena

**Имя**: 260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС

**Memories**: analysis-GKSTCPLK-2182, impl-GKSTCPLK-2182
