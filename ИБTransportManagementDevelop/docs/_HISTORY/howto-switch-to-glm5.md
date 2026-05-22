# Инструкция: Переключение модели Claude Code на glm-5

Дата: 2026-03-05

## Текущее состояние
- Claude Code CLI: **glm-4.7**
- MCP серверы: **glm-5** (уже switched)

## Как переключить на glm-5

### Вариант 1: Временное изменение (текущая сессия)

```bash
set ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5
set ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5
claude
```

### Вариант 2: Постоянное изменение (Windows)

1. Откройте "Системные свойства" -> "Переменные среды"
2. Добавьте или измените переменные:
   - `ANTHROPIC_DEFAULT_SONNET_MODEL` = `glm-5`
   - `ANTHROPIC_DEFAULT_OPUS_MODEL` = `glm-5`
3. Перезапустите терминал

### Вариант 3: Через bat-файл

Создайте файл `start-claude-glm5.bat`:
```batch
@echo off
set ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5
set ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5
claude
```

## Проверка

После перезапуска проверьте:
```bash
echo %ANTHROPIC_DEFAULT_SONNET_MODEL%
echo %ANTHROPIC_DEFAULT_OPUS_MODEL%
```

Должно показать: `glm-5`
