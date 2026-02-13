---
name: create-hook
description: "Используй этот скилл когда нужно создать новый hook для PDF Framework. Триггеры: 'создай hook', 'новый хук', 'добавить hook', 'create hook', 'автоматизировать событие', 'добавить обработчик', 'хук для', 'hook for'. Содержит шаблон, чеклист, примеры из фреймворка."
---

# Create Hook — создание хуков для PDF Framework

## Обзор

Хуки — компонент **КОГДА** в триаде Hooks + Skills + MCP. Автоматически срабатывают на события Claude Code (до/после инструмента, при вводе пользователя, при остановке). Все хуки наследуют `BaseHook` из `.claude/hooks/base/protocol.py`.

---

## Быстрый справочник

| Задача | Действие |
|--------|----------|
| Новый hook | Создать `.py` в `.claude/hooks/`, наследовать `BaseHook` |
| Регистрация | Добавить в `.claude/settings.json` → `hooks` → `EventName` |
| Задачи из hook | `from shared.task_master import add_task` |
| Блокировка | `HookOutput().block("reason")` + `sys.exit(2)` |
| Подсказка Claude | `HookOutput().system_message("msg")` |
| Тест | `echo '{"prompt":"test"}' \| python hook.py` |

---

## Типы событий

| Event | Когда | Блокирует | Matcher | stdin содержит |
|-------|-------|-----------|---------|----------------|
| **UserPromptSubmit** | Пользователь отправил сообщение | Да | нет | `prompt` |
| **PreToolUse** | До вызова инструмента | Да | `Read\|Write\|Bash` | `tool_name`, `tool_input` |
| **PostToolUse** | После вызова инструмента | Нет | `WebSearch\|WebFetch` | `tool_name`, `tool_input`, `tool_result` |
| **Stop** | Claude пытается остановиться | Да (exit 2) | нет | `transcript`, `reason` |
| **Notification** | Уведомление | Нет | нет | varies |
| **SessionStart** | Начало сессии | Нет | нет | `session_id` |
| **SessionEnd** | Конец сессии | Нет | нет | `session_id` |
| **PreCompact** | Перед компактификацией | Нет | нет | varies |
| **SubagentStop** | Субагент остановился | Нет | нет | varies |
| **PermissionRequest** | Запрос разрешений | Да | нет | varies |

---

## Шаблон нового хука

```python
#!/usr/bin/env python3
"""
Hook: [hook-name]
Event: [UserPromptSubmit|PreToolUse|PostToolUse|Stop]
Matcher: [Read|Write|Bash|WebSearch|WebFetch или пусто]
Purpose: [что делает]
Timeout: [3-5]s
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput


class MyHook(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        # Логика хука

        # Вариант 1: подсказка Claude (не блокирует)
        return HookOutput().system_message("[MY-HOOK] Информация для Claude")

        # Вариант 2: блокировка инструмента
        return HookOutput().block("Причина блокировки")

        # Вариант 3: пропустить (pass through)
        return None


if __name__ == "__main__":
    MyHook().run()
```

---

## Регистрация в settings.json

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "D:\\1С-Framework\\.venv\\Scripts\\python.exe D:\\1С-Framework\\.claude\\hooks\\my-hook.py",
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash|Read",
        "hooks": [
          {
            "type": "command",
            "command": "D:\\1С-Framework\\.venv\\Scripts\\python.exe D:\\1С-Framework\\.claude\\hooks\\my-hook.py",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
```

**Matcher паттерны:**
- `"Bash"` — конкретный инструмент
- `"Read|Write|Glob|Grep"` — несколько через `|`
- `"mcp__serena__.*"` — regex для MCP
- `""` или отсутствие — все инструменты
- `"WebSearch|WebFetch"` — веб-инструменты

---

## Работа с задачами (task_master)

```python
from shared.task_master import add_task, complete_task, get_pending_tasks, has_recent_completion

# Создать задачу
add_task(
    title="Сохранить результаты в кеш",
    priority="high",              # high | normal | low
    created_by="my-hook-name",
)

# Проверить cooldown (антиспам)
if has_recent_completion("my-hook-name", cooldown_minutes=10):
    return None  # Недавно уже создавали

# Получить pending задачи
pending = get_pending_tasks(created_by="my-hook-name")

# Завершить задачу
complete_task("Сохранить результаты в кеш", created_by="my-hook-name")
```

Задачи хранятся в `.claude/cache/hook-todos.json` (отдельно от TodoWrite Claude).

---

## Межхуковая синхронизация (hook_lock)

```python
from shared.hook_lock import hook_lock

with hook_lock("my-hook-name", timeout=10) as acquired:
    if acquired:
        # Критическая секция (другие хуки ждут)
        pass
```

---

## Чеклист

- [ ] Скрипт в `.claude/hooks/<name>.py`
- [ ] Наследует `BaseHook` из `base/protocol.py`
- [ ] `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` в начале
- [ ] Graceful degradation: `execute()` обёрнут в try/except через `BaseHook.run()`
- [ ] Добавлен в `settings.json` с правильным matcher и timeout
- [ ] Абсолютные пути к `.venv\Scripts\python.exe` в settings.json
- [ ] Протестирован: `echo '{"prompt":"test"}' | python hook.py`
- [ ] Не конфликтует с существующими хуками (проверить matchers)

---

## Примеры из фреймворка

### 1. research-task-detector.py (UserPromptSubmit)
Детектирует исследовательские вопросы по 1С, направляет на `1c-doc-research` skill.

### 2. knowledge-cache-reminder.py (PostToolUse: WebSearch|WebFetch)
После веб-поиска создаёт mandatory задачу сохранить в кеш знаний.

### 3. task-enforcer.py (Stop)
Блокирует остановку если есть pending mandatory задачи в hook-todos.json.

### 4. search-optimizer.py (PreToolUse: Bash)
Подсказывает оптимальные параметры поиска (strategy=hybrid, rerank=true).

### 5. ralph_wiggum_stop.py (Stop)
Контролирует итеративный цикл Ralph Wiggum (completion markers).

---

## Паттерн: Расширение домена (Hook + Skill)

Когда появляется **новая предметная область** (домен), нужно обновить хуки роутинга:

### Шаг 1: Анализ домена

| Критерий | Выделенный | Общий (расширить существующий) |
|----------|-----------|-------------------------------|
| Уникальные источники (URL) | its.1c.ru → только 1С | GitHub, arxiv → общий Tech |
| Уникальная терминология | BSL, §X.Y → только 1С | embeddings, LLM → общий Tech |
| Уникальный workflow | Иерархия §X.Y → 1С | 5-фазный research → общий |

### Шаг 2: Если НОВЫЙ домен — создать skill + обновить хуки

```python
# research-task-detector.py — добавить:
NEW_DOMAIN_TERMS = ["term1", "term2", ...]

# В execute():
new_score = sum(1 for kw in self.NEW_DOMAIN_TERMS if kw in prompt_lower)
if research_score >= 1 and new_score >= 1:
    return HookOutput().system_message("[NEW-DOMAIN-DETECTED] ...")
```

```python
# knowledge-cache-reminder.py — добавить:
NEW_DOMAIN_SIGNALS = ["signal1", "signal2", ...]

# В execute():
new_score = sum(1 for s in self.NEW_DOMAIN_SIGNALS if s in result_lower)
if new_score >= 2:
    # ... создать задачу для нового кеша
```

### Шаг 3: Если расширение СУЩЕСТВУЮЩЕГО — добавить термины

```python
# Пример: добавить FastAPI в tech-research
TECH_TERMS = [
    ...,
    "fastapi", "uvicorn", "starlette",  # ← новые
]
```

### Чеклист расширения домена

- [ ] Skill: `skills/<domain>-research/SKILL.md` создан (5 фаз)
- [ ] Skill: `cache/_topic_template.md` создан (категории)
- [ ] Skill: `cache/_index.json` создан (пустой)
- [ ] Hook: `DOMAIN_TERMS` добавлен в `research-task-detector.py`
- [ ] Hook: `DOMAIN_SIGNALS` добавлен в `knowledge-cache-reminder.py`
- [ ] Triad: обновлена таблица Skills в `hooks-skills-mcp-triad/SKILL.md`
- [ ] CLAUDE.md: обновлён раздел Knowledge Cache
- [ ] MEMORY.md: добавлена запись о новом домене

---

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| `except: pass` без logging | Скрывает ошибки | `BaseHook.run()` уже обрабатывает — не нужно дополнительно |
| Hook вызывает тот же инструмент | Зацикливание (PreToolUse:Read → Read) | Использовать альтернативный инструмент |
| Блокировка без причины | Claude не понимает что делать | Всегда указывать `reason` в `block()` |
| Относительные пути в settings.json | Не находит python.exe | Абсолютные: `D:\\1С-Framework\\.venv\\Scripts\\python.exe` |
| Тяжёлые вычисления в хуке | Timeout (3-5s) | Хуки должны быть лёгкими (keyword matching, file read) |
