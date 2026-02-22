---
name: windows-hooks-paths
description: "Windows-пути в хуках Claude Code: bash съедает обратные слеши, диагностика, исправление, профилактика. Триггеры: 'command not found hook', 'хук не находит python', 'backslash hook', 'обратные слеши хук', 'путь хука Windows', 'hook path windows', 'D:1С-Framework', 'слипшийся путь', 'bash escape path'. НЕ для создания хуков — используй create-hook. НЕ для известных API-багов — используй claude-code-hooks-bugs."
---

# Windows Hooks Paths — обратные слеши в хуках Claude Code

## Проблема

Claude Code на Windows выполняет хуки через `/usr/bin/bash` (Git Bash).
Bash интерпретирует `\` как escape-символ, а не разделитель пути.

```
ЗАПИСАНО:  D:\1С-Framework\.venv\Scripts\python.exe
BASH ВИДИТ: D:1С-Framework.venvScriptspython.exe
ОШИБКА:    command not found
```

## Диагностика

### Симптомы

- Ошибка: `/usr/bin/bash: line 1: D:1С-Framework.venvScriptspython.exe: command not found`
- Путь "слипается" — все `\` исчезают, сегменты склеиваются
- Хуки перестают выводить текст (stdout), только ошибки
- Все 4 Stop хука (или N хуков) выдают одинаковую ошибку

### Как отличить от других проблем

| Симптом | Это path-баг? | Другая причина |
|---------|--------------|----------------|
| `command not found` + слипшийся путь | **ДА** | — |
| `command not found` + путь нормальный | Нет | python.exe не установлен |
| Хук молча не запускается | Нет | PostToolUse баг (#6305) |
| Пустой stdin | Нет | Windows stdin баг (#10450) |

### Быстрая проверка

Посмотреть `settings.json` — если в `hooks.*.command` есть `\`, это баг:

```json
// ПЛОХО — bash съест обратные слеши
"command": "D:\\1С-Framework\\.venv\\Scripts\\python.exe D:\\1С-Framework\\.claude\\hooks\\my-hook.py"

// ХОРОШО — forward slashes работают в bash и Windows
"command": "D:/1С-Framework/.venv/Scripts/python.exe D:/1С-Framework/.claude/hooks/my-hook.py"
```

## Исправление

### Ручное

Открыть `.claude/settings.json`, заменить все `\` на `/` в полях `command` внутри секции `hooks`.

### Автоматическое (через Claude Code)

Прочитать `settings.json` → найти все `hooks.*.hooks[].command` → заменить `\` на `/`.

### Правило замены

```
D:\path\to\file  →  D:/path/to/file
```

Forward slash `/` работает:
- В Git Bash (основной shell Claude Code)
- В Python (`pathlib`, `os.path`)
- В Windows API (начиная с NT)
- В cmd.exe и PowerShell

## Профилактика

### При создании хуков — ВСЕГДА использовать forward slashes

```json
{
  "type": "command",
  "command": "D:/1С-Framework/.venv/Scripts/python.exe D:/1С-Framework/.claude/hooks/my-hook.py",
  "timeout": 5
}
```

### Чеклист для settings.json

1. Открыть `.claude/settings.json`
2. Ctrl+F → `\\` (двойной обратный слеш, JSON-escaped)
3. Если найдены в секции `hooks` → заменить на `/`
4. Секция `permissions.allow` — там `\\\\` допустим (JSON escaping для pattern matching)

### Разница: hooks vs permissions

| Секция | Формат пути | Почему |
|--------|------------|--------|
| `hooks[].command` | `D:/path/file` (forward slash) | Выполняется bash напрямую |
| `permissions.allow` | `D:\\\\path\\\\file` (escaped backslash) | JSON pattern matching, не выполняется |

## Причины появления

- Claude Code обновился и изменил shell для хуков
- settings.json редактировался из Windows-инструмента, который подставил `\`
- Хуки создавались через скрипт, использующий `os.path` вместо `pathlib.as_posix()`
- Copy-paste пути из Windows Explorer

## Связанные скиллы

| Скилл | Когда |
|-------|-------|
| [claude-code-hooks-bugs](../claude-code-hooks-bugs/SKILL.md) | API-баги: PostToolUse #6305, stdin #10450 |
| [hook-debugging](../hook-debugging/SKILL.md) | Отладка конкретного хука (canary, логирование) |
| [create-hook](../create-hook/SKILL.md) | Создание нового хука (шаблон + чеклист) |
