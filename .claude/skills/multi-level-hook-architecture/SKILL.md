---
name: multi-level-hook-architecture
description: "Трёхуровневая архитектура хуков Claude Code: UserPromptSubmit (уровень 1), PostToolUse (уровень 2, сломан), Stop (уровень 3). Полная карта хуков проекта, порядок выполнения, взаимодействие уровней. Триггеры: 'архитектура хуков', 'уровни хуков', 'hook levels', 'hook architecture', 'трёхуровневая защита', 'порядок хуков', 'hook chain', 'цепочка хуков', 'какие хуки есть'. НЕ для создания хуков — используй create-hook. НЕ для диагностики — используй hook-debugging."
---

# Multi-Level Hook Architecture — трёхуровневая архитектура хуков

## Обзор

Система хуков проекта построена на трёх уровнях защиты. Каждый уровень срабатывает в свой момент и покрывает случаи, которые пропустил предыдущий. Двухуровневый workaround (уровни 1 + 3) компенсирует баг #6305, из-за которого уровень 2 (PostToolUse) не работает.

---

## Схема уровней

```
Пользователь набирает сообщение
    │
    ▼
┌─────────────────────────────────────────────────┐
│  УРОВЕНЬ 1: UserPromptSubmit                    │
│  Когда: при каждом сообщении пользователя        │
│  Может блокировать: Нет (только additionalContext)│
│                                                  │
│  ├─ skill-router.py          → загрузка скиллов  │
│  │   └─ _detect_skill_activations → workaround   │
│  ├─ ralph_activator.py       → Ralph Wiggum loop │
│  ├─ research-task-detector.py→ детекция research  │
│  ├─ decision-to-triad.py     → триада из решений │
│  ├─ document-persistence.py  → сохранение планов │
│  ├─ todo-sync.py             → синхр. задач      │
│  └─ auto-git-save-prompt.py  → АВТОКОММИТ (NEW)  │
└─────────────────────────────────────────────────┘
    │
    ▼
  Claude работает (Edit, Write, Bash, Read, ...)
    │
    ▼
┌─────────────────────────────────────────────────┐
│  УРОВЕНЬ 2: PostToolUse  ⚠️ НЕ РАБОТАЕТ (#6305)│
│  Когда: после каждого вызова инструмента         │
│  Зарегистрированы, но не срабатывают:            │
│                                                  │
│  Write|Edit:                                     │
│  ├─ auto-git-save.py        → автокоммит         │
│  └─ docs-change-tracker.py  → напоминание о доках│
│                                                  │
│  Bash:                                           │
│  ├─ bulk-action-guard.py    → защита от bulk ops │
│  └─ auto-git-save.py        → автокоммит         │
│                                                  │
│  WebSearch|WebFetch:                             │
│  └─ knowledge-cache-reminder.py → кеш знаний    │
│                                                  │
│  Skill:                                          │
│  └─ skill-usage-metrics.py  → метрики + accuracy │
│                                                  │
│  Write:                                          │
│  └─ factory-enforcer.py     → проверка триады    │
└─────────────────────────────────────────────────┘
    │
    ▼
  Claude хочет остановиться
    │
    ▼
┌─────────────────────────────────────────────────┐
│  УРОВЕНЬ 3: Stop (финальная проверка)            │
│  Когда: Claude пытается завершить ответ          │
│  Может блокировать: Да (exit 2)                  │
│  Выполняются ПОСЛЕДОВАТЕЛЬНО:                    │
│                                                  │
│  1. ralph_wiggum_stop.py    → контроль Ralph loop│
│  2. git-commit-enforcer.py  → незакоммиченные?   │
│  3. docs-change-enforcer.py → доки устарели? NEW │
│  4. task-enforcer.py        → задачи не сделаны? │
│                                                  │
│  Если ЛЮБОЙ вернул exit 2 → Claude продолжает    │
│  работу и пробует остановиться снова             │
└─────────────────────────────────────────────────┘
```

---

## Таблица всех хуков

### Уровень 1 — UserPromptSubmit

| Хук | Timeout | Назначение |
|-----|---------|-----------|
| [skill-router.py](.claude/hooks/skill-router.py) | 5s | Загрузка скиллов по ключевым словам |
| [ralph_activator.py](.claude/hooks/ralph_activator.py) | 5s | Активация автономного цикла Ralph Wiggum |
| [research-task-detector.py](.claude/hooks/research-task-detector.py) | 5s | Детекция research vs brainstorm задач |
| [decision-to-triad.py](.claude/hooks/decision-to-triad.py) | 5s | Конвертация решений в артефакты триады |
| [document-persistence.py](.claude/hooks/document-persistence.py) | 3s | Сохранение планов и roadmap |
| [todo-sync.py](.claude/hooks/todo-sync.py) | 3s | Синхронизация hook-todos → TodoWrite |
| [auto-git-save-prompt.py](.claude/hooks/auto-git-save-prompt.py) | 15s | Автокоммит при каждом промпте (workaround) |

### Уровень 2 — PostToolUse (не работает из-за #6305)

| Хук | Matcher | Timeout | Назначение |
|-----|---------|---------|-----------|
| [auto-git-save.py](.claude/hooks/auto-git-save.py) | Write\|Edit | 30s | Sync commit |
| [docs-change-tracker.py](.claude/hooks/docs-change-tracker.py) | Write\|Edit | 5s | Напоминание обновить доки |
| [knowledge-cache-reminder.py](.claude/hooks/knowledge-cache-reminder.py) | WebSearch\|WebFetch | 5s | Напоминание кешировать знания |
| [skill-usage-metrics.py](.claude/hooks/skill-usage-metrics.py) | Skill | 3s | Метрики + accuracy (prompt_id корреляция) |
| [factory-enforcer.py](.claude/hooks/factory-enforcer.py) | Write | 5s | Проверка артефактов триады |
| [bulk-action-guard.py](.claude/hooks/bulk-action-guard.py) | Bash | 3s | Защита от массовых операций |
| [auto-git-save.py](.claude/hooks/auto-git-save.py) | Bash | 30s | Sync commit после Bash |

### Уровень 2 — PreToolUse

| Хук | Matcher | Timeout | Назначение |
|-----|---------|---------|-----------|
| [root-clutter-guard.py](.claude/hooks/root-clutter-guard.py) | Write | 3s | Блокировка записи в корень |
| [search-optimizer.py](.claude/hooks/search-optimizer.py) | Bash | 3s | Оптимизация поисковых запросов |

### Уровень 3 — Stop

| Хук | Timeout | Блокирует | Назначение |
|-----|---------|-----------|-----------|
| [ralph_wiggum_stop.py](.claude/hooks/ralph_wiggum_stop.py) | 5s | Да | Контроль автономного цикла |
| [git-commit-enforcer.py](.claude/hooks/git-commit-enforcer.py) | 5s | Да | Незакоммиченные файлы |
| [docs-change-enforcer.py](.claude/hooks/docs-change-enforcer.py) | 10s | Да | Устаревшая документация |
| [task-enforcer.py](.claude/hooks/task-enforcer.py) | 10s | Да | Невыполненные задачи (v2.2: auto-clean stale code-verify) |

---

## Взаимодействие уровней

### Автокоммит: уровень 1 компенсирует уровень 2

```
PostToolUse (СЛОМАН):
  auto-git-save.py → НЕ срабатывает

Компенсация через UserPromptSubmit:
  auto-git-save-prompt.py → коммит при следующем промпте
  + cooldown 30 сек между коммитами

Финальная проверка через Stop:
  git-commit-enforcer.py → если что-то не закоммичено → блокировка
```

### Skill Metrics: уровень 1 компенсирует уровень 2

```
PostToolUse (СЛОМАН):
  skill-usage-metrics.py → НЕ срабатывает (баг #6305)

Компенсация через UserPromptSubmit:
  skill-router.py → _detect_skill_activations()
  → парсит <command-name>skill</command-name> теги из предыдущего turn
  → SessionState.add_activated_skill() + log activate (source=prompt-detection)
  → корреляция через SessionState.get_prompt_id()
```

### Документация: уровень 3 компенсирует уровень 2

```
PostToolUse (СЛОМАН):
  docs-change-tracker.py → НЕ срабатывает
  → задачи не создаются
  → task-enforcer не видит проблем

Компенсация через Stop:
  docs-change-enforcer.py → проверяет git history за 6 часов
  → код изменился, доки нет → блокировка
  → ссылается на /audit-docs для исправления
```

### Задачи: все 3 уровня

```
Уровень 1: todo-sync.py → синхронизирует hook-todos.json с TodoWrite
Уровень 2: хуки создают задачи через task_master (если работает)
Уровень 3: task-enforcer.py → блокирует если mandatory задачи не выполнены
```

---

## Когда какой уровень использовать

| Потребность | Уровень | Пример |
|-------------|---------|--------|
| Тихое действие при каждом промпте | 1 (UserPromptSubmit) | Автокоммит |
| Реакция на конкретный инструмент | 2 (PostToolUse) | Напоминание (когда починят) |
| Блокировка при завершении | 3 (Stop) | Enforcer |
| Загрузка контекста | 1 (UserPromptSubmit) | Skill router |
| Валидация перед действием | PreToolUse | Root clutter guard |

---

## Дизайн-принципы

1. **Defense in depth** — критичные проверки дублируются на нескольких уровнях
2. **Graceful degradation** — если хук упал, не блокировать работу
3. **Cooldown** — предотвращение спама (30 сек для автокоммита)
4. **Один enforcer — одно условие** — не мешать логику в одном хуке
5. **Actionable messages** — enforcer говорит ЧТО делать и КАКИМ скиллом

---

## Связанные скиллы

| Скилл | Связь |
|-------|-------|
| [create-hook](.claude/skills/create-hook/SKILL.md) | Шаблон создания нового хука |
| [hook-debugging](.claude/skills/hook-debugging/SKILL.md) | Диагностика когда хук не работает |
| [claude-code-hooks-bugs](.claude/skills/claude-code-hooks-bugs/SKILL.md) | Известные баги и workaround-ы |
| [hook-enforcement-pattern](.claude/skills/hook-enforcement-pattern/SKILL.md) | Паттерн Enforcer для Stop-хуков |
| [hooks-skills-mcp-triad](.claude/skills/hooks-skills-mcp-triad/SKILL.md) | Общая архитектура триады |
| [auto-git-save](.claude/skills/auto-git-save/SKILL.md) | Система автокоммита |
