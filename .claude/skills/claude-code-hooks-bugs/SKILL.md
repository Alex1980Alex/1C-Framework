---
name: claude-code-hooks-bugs
description: "Известные баги хуков Claude Code и обходные пути: PostToolUse не срабатывает (#6305), пустой stdin на Windows (#10450), таблица надёжности событий по платформам. Триггеры: 'баг хука', 'hook bug', '#6305', '#10450', 'PostToolUse не работает', 'hooks not firing', 'хуки не запускаются', 'workaround hooks', 'обходной путь хуков', 'платформенные баги'. НЕ для отладки конкретного хука — используй hook-debugging."
---

# Claude Code Hooks Bugs — известные баги и обходные пути

## Обзор

Справочник известных багов хуков Claude Code, собранный из реальной отладки проекта и GitHub issues. Актуален по состоянию на март 2026.

---

## Таблица надёжности событий по платформам

| Событие | Windows | macOS | Linux | WSL2 | Termux |
|---------|---------|-------|-------|------|--------|
| **UserPromptSubmit** | OK | OK | OK | OK | OK |
| **Stop** | OK | OK | OK | OK | OK |
| **PreToolUse** | **OK (v2.1.87+)** | ? | ? | НЕТ | НЕТ |
| **PostToolUse** | **OK (v2.1.87+)** | ? | ? | НЕТ | НЕТ |
| **Notification** | OK | OK | OK | OK | OK |

**Обновление 2026-03-29:** Canary-тест на Windows + v2.1.87 подтвердил: **PreToolUse и PostToolUse оба работают**. Процесс запускается, stdin содержит полные данные (tool_name, tool_input, tool_response). Fix #25981 (Git Bash вместо cmd.exe) решил проблему на Windows. Issue #6305 формально OPEN, но на Windows — исправлен.

**Вывод:** На Windows v2.1.87+ можно использовать все типы событий. WSL2/Termux — не проверены.

---

## Основные баги

### #6305 — Pre/PostToolUse не запускают процесс (CRITICAL)

- **Статус:** OPEN (подтверждён)
- **URL:** https://github.com/anthropics/claude-code/issues/6305
- **Суть:** Claude Code регистрирует tool-related хуки, но НЕ запускает процессы при реальных вызовах инструментов
- **Доказательство:** Canary-тест (запись файла ДО импортов) — файл не создаётся. Процесс не стартует.
- **Платформы:** Windows, WSL2, Termux (macOS/Linux — данных мало)
- **Workaround:** Перенести логику на `UserPromptSubmit` (уровень 1) и `Stop` (уровень 2)

### #6403 — Регистрация хуков ломается после перезагрузки

- **Статус:** OPEN
- **URL:** https://github.com/anthropics/claude-code/issues/6403
- **Суть:** После рестарта Claude Code tool-related хуки перестают регистрироваться
- **Связь с #6305:** Возможно одна и та же root cause — инициализация tool hooks

### #10450 — Windows: пустой stdin в хуках

- **Статус:** OPEN
- **URL:** https://github.com/anthropics/claude-code/issues/10450
- **Суть:** Даже если хук запускается, `sys.stdin.buffer.read()` возвращает пустые данные
- **Платформа:** Windows
- **Workaround:** Обрабатывать пустой stdin gracefully, не полагаться на tool_input из stdin

### #17424 — Windows: stdin не передаётся

- **Статус:** OPEN
- **URL:** https://github.com/anthropics/claude-code/issues/17424
- **Суть:** Дублирует #10450 с дополнительными данными
- **Платформа:** Windows

### #3148 — Matcher `*` не поддерживается

- **Статус:** CLOSED (fix в v1.0.51)
- **URL:** https://github.com/anthropics/claude-code/issues/3148
- **Суть:** Использование `"matcher": "*"` не работало, нужно `"matcher": ""` или список конкретных инструментов
- **Fix:** Обновиться до v1.0.51+, использовать `"matcher": "Write|Edit|Bash"`

### #15617 — Termux: PostToolUse не срабатывает

- **Статус:** OPEN
- **URL:** https://github.com/anthropics/claude-code/issues/15617
- **Суть:** Подтверждение #6305 на Termux

### #10011 — Изменения файлов перезаписываются

- **Статус:** OPEN
- **URL:** https://github.com/anthropics/claude-code/issues/10011
- **Суть:** Hook изменяет файл, Claude перезаписывает изменения

### #3179 — WSL2: хуки не срабатывают

- **Статус:** OPEN
- **URL:** https://github.com/anthropics/claude-code/issues/3179
- **Суть:** Подтверждение #6305 на WSL2

---

## Паттерн workaround: двухуровневая защита

Поскольку PostToolUse не работает, используется паттерн замены:

```
PostToolUse (СЛОМАН)
    ↓ заменяется на
UserPromptSubmit (уровень 1) + Stop (уровень 2)
```

### Уровень 1 — UserPromptSubmit

- **Когда:** При каждом сообщении пользователя (следующий промпт после изменения)
- **Задержка:** Коммит/проверка происходит не сразу, а при следующем промпте
- **Пример:** `auto-git-save-prompt.py` — автокоммит при промпте

### Уровень 2 — Stop

- **Когда:** Claude пытается остановиться
- **Гарантия:** Ничего не будет пропущено — это последняя проверка
- **Пример:** `git-commit-enforcer.py`, `docs-change-enforcer.py`

### Сравнение

| Аспект | PostToolUse (идеал) | UserPromptSubmit | Stop |
|--------|-------------------|-----------------|------|
| Работает? | НЕТ (баг) | ДА | ДА |
| Задержка | Мгновенно | До след. промпта | В конце сессии |
| Может блокировать? | Нет | Нет (только контекст) | Да (exit 2) |
| stdin содержит | tool_name, tool_input | prompt | {} |
| Частота | На каждый Edit/Write | На каждое сообщение | 1 раз при остановке |

---

## Чеклист при создании нового хука

1. **НЕ полагайся на PostToolUse** — он не работает (#6305)
2. **Дублируй критичную логику** на UserPromptSubmit + Stop
3. **Обрабатывай пустой stdin** — на Windows может быть пуст (#10450)
4. **Используй matcher с pipe** — `"Write|Edit"`, не `"*"` (#3148)
5. **Canary-тест** — перед регистрацией проверь что хук вообще запускается

---

## Связанные скиллы

| Скилл | Когда использовать |
|-------|-------------------|
| [hook-debugging](.claude/skills/hook-debugging/SKILL.md) | Отладка конкретного хука (canary, логирование) |
| [create-hook](.claude/skills/create-hook/SKILL.md) | Создание нового хука (шаблон, чеклист) |
| [multi-level-hook-architecture](.claude/skills/multi-level-hook-architecture/SKILL.md) | Архитектура трёхуровневой защиты |
| [hook-enforcement-pattern](.claude/skills/hook-enforcement-pattern/SKILL.md) | Паттерн Enforcer для Stop-хуков |
| [windows-hooks-paths](.claude/skills/windows-hooks-paths/SKILL.md) | Windows: bash съедает `\` в путях хуков |
