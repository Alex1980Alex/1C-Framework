> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Расширение Claude с помощью навыков (Skills)

> Создавайте, управляйте и делитесь навыками для расширения возможностей Claude в Claude Code. Включает пользовательские slash-команды.

Навыки расширяют возможности Claude. Создайте файл `SKILL.md` с инструкциями, и Claude добавит его в свой набор инструментов. Claude использует навыки, когда это уместно, или вы можете вызвать навык напрямую через `/skill-name`.

<Note>
  Для встроенных команд, таких как `/help` и `/compact`, см. [Интерактивный режим](/en/interactive-mode#built-in-commands).

  **Пользовательские slash-команды объединены с навыками.** Файл в `.claude/commands/review.md` и навык в `.claude/skills/review/SKILL.md` оба создают `/review` и работают одинаково. Ваши существующие файлы `.claude/commands/` продолжают работать.
</Note>

## Начало работы

### Создайте свой первый навык

Этот пример создаёт навык, который учит Claude объяснять код с помощью визуальных диаграмм и аналогий.

1. **Создайте директорию навыка:**

```bash
mkdir -p ~/.claude/skills/explain-code
```

2. **Напишите SKILL.md:**

Каждый навык нуждается в файле `SKILL.md` с двумя частями: YAML frontmatter (между `---` маркерами) и markdown-контент с инструкциями.

Создайте `~/.claude/skills/explain-code/SKILL.md`:

```yaml
---
name: explain-code
description: Explains code with visual diagrams and analogies. Use when explaining how code works.
---

When explaining code, always include:

1. **Start with an analogy**: Compare the code to something from everyday life
2. **Draw a diagram**: Use ASCII art to show the flow
3. **Walk through the code**: Explain step-by-step
4. **Highlight a gotcha**: Common mistake or misconception
```

3. **Протестируйте навык:**

```
/explain-code src/auth/login.ts
```

### Где хранятся навыки

| Расположение | Путь                                                     | Применяется к              |
| :----------- | :------------------------------------------------------- | :------------------------- |
| Enterprise   | См. [managed settings](/en/permissions#managed-settings)  | Все пользователи организации |
| Личные       | `~/.claude/skills/<skill-name>/SKILL.md`                 | Все ваши проекты           |
| Проектные    | `.claude/skills/<skill-name>/SKILL.md`                   | Только этот проект         |
| Плагин       | `<plugin>/skills/<skill-name>/SKILL.md`                  | Где плагин включён         |

### Структура директории навыка

```
my-skill/
├── SKILL.md           # Основные инструкции (обязательно)
├── template.md        # Шаблон для Claude
├── examples/
│   └── sample.md      # Пример вывода
└── scripts/
    └── validate.sh    # Скрипт для выполнения
```

## Конфигурация навыков

### Справочник по frontmatter

```yaml
---
name: my-skill
description: What this skill does
disable-model-invocation: true
allowed-tools: Read, Grep
---
```

| Поле                       | Обязат. | Описание                                                              |
| :------------------------- | :------ | :-------------------------------------------------------------------- |
| `name`                     | Нет     | Отображаемое имя. По умолчанию — имя директории                      |
| `description`              | Рек.    | Что делает навык. Claude использует для автовызова                     |
| `argument-hint`            | Нет     | Подсказка при автодополнении, напр. `[issue-number]`                  |
| `disable-model-invocation` | Нет     | `true` — только ручной вызов через `/name`. Default: `false`         |
| `user-invocable`           | Нет     | `false` — скрыть из меню `/`. Default: `true`                        |
| `allowed-tools`            | Нет     | Инструменты без запроса разрешения                                    |
| `model`                    | Нет     | Модель для использования                                             |
| `context`                  | Нет     | `fork` для запуска в отдельном подагенте                             |
| `agent`                    | Нет     | Тип подагента при `context: fork`                                    |
| `hooks`                    | Нет     | Хуки, привязанные к жизненному циклу навыка                          |

### Подстановки переменных

| Переменная               | Описание                                                          |
| :------------------------ | :---------------------------------------------------------------- |
| `$ARGUMENTS`              | Все аргументы, переданные при вызове навыка                       |
| `$ARGUMENTS[N]`           | Конкретный аргумент по индексу (0-based)                          |
| `$N`                      | Сокращение для `$ARGUMENTS[N]`                                    |
| `${CLAUDE_SESSION_ID}`    | ID текущей сессии                                                 |

## Управление вызовом навыков

| Frontmatter                      | Вы можете вызвать | Claude может вызвать |
| :------------------------------- | :---------------- | :------------------- |
| (по умолчанию)                   | Да                | Да                   |
| `disable-model-invocation: true` | Да                | Нет                  |
| `user-invocable: false`          | Нет               | Да                   |

### Передача аргументов

```yaml
---
name: fix-issue
description: Fix a GitHub issue
disable-model-invocation: true
---

Fix GitHub issue $ARGUMENTS following our coding standards.
1. Read the issue description
2. Implement the fix
3. Write tests
4. Create a commit
```

Вызов: `/fix-issue 123`

## Продвинутые паттерны

### Внедрение динамического контекста

Синтаксис `` !`command` `` выполняет shell-команды перед отправкой контента Claude:

```yaml
---
name: pr-summary
description: Summarize changes in a pull request
context: fork
agent: Explore
---

## Pull request context
- PR diff: !`gh pr diff`
- PR comments: !`gh pr view --comments`
- Changed files: !`gh pr diff --name-only`

## Your task
Summarize this pull request...
```

### Запуск навыков в подагенте

Добавьте `context: fork` для запуска навыка в изоляции:

```yaml
---
name: deep-research
description: Research a topic thoroughly
context: fork
agent: Explore
---

Research $ARGUMENTS thoroughly:
1. Find relevant files using Glob and Grep
2. Read and analyze the code
3. Summarize findings with specific file references
```

### Визуальный вывод

Навыки могут генерировать интерактивные HTML-файлы:

```yaml
---
name: codebase-visualizer
description: Generate an interactive tree visualization of your codebase
allowed-tools: Bash(python *)
---

Run the visualization script:
```bash
python ~/.claude/skills/codebase-visualizer/scripts/visualize.py .
```

## Распространение навыков

- **Проектные навыки**: закоммитьте `.claude/skills/` в систему контроля версий
- **Плагины**: создайте `skills/` в вашем плагине
- **Managed**: развёртывание через managed settings для организации

## Связанные ресурсы

- **[Подагенты](/en/sub-agents)**: делегирование задач специализированным агентам
- **[Плагины](/en/plugins)**: упаковка и распространение навыков
- **[Хуки](/en/hooks)**: автоматизация рабочих процессов
- **[Память](/en/memory)**: управление файлами CLAUDE.md
