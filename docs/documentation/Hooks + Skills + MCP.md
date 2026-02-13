# Концепция: Hooks + Skills + MCP

> **Версия:** 1.0.0
> **Дата:** 2026-01-20
> **Статус:** АКТИВНЫЙ ДОКУМЕНТ

## 📋 Содержание

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Компоненты системы](#компоненты-системы)
3. [Hooks — Система событий](#hooks--система-событий)
4. [Skills — Контейнеры знаний](#skills--контейнеры-знаний)
5. [MCP — Внешние инструменты](#mcp--внешние-инструменты)
6. [Триада: Интеграция компонентов](#триада-интеграция-компонентов)
7. [Поиск: Как находить информацию](#поиск-как-находить-информацию)
8. [Нюансы и лучшие практики](#нюансы-и-лучшие-практики)
9. [Примеры из фреймворка](#примеры-из-фреймворка)

---

## Обзор архитектуры

### Концептуальная модель

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLAUDE CODE RUNTIME                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐      │
│   │   HOOKS     │ ──────▶ │   SKILLS    │ ──────▶ │    MCP      │      │
│   │  (Когда?)   │         │   (Как?)    │         │   (Чем?)    │      │
│   └─────────────┘         └─────────────┘         └─────────────┘      │
│         │                       │                       │               │
│         ▼                       ▼                       ▼               │
│   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐      │
│   │ Событийная  │         │ Процедурное │         │  Внешние    │      │
│   │ автоматизац.│         │   знание    │         │ серверы API │      │
│   └─────────────┘         └─────────────┘         └─────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Принцип триады

| Компонент | Роль | Вопрос | Формат |
|-----------|------|--------|--------|
| **Hooks** | Событийный триггер | КОГДА выполнять? | Python/Bash скрипты |
| **Skills** | Процедурное знание | КАК выполнять? | Markdown + YAML |
| **MCP** | Внешние инструменты | ЧЕМ выполнять? | JSON-RPC серверы |

---

## Компоненты системы

### Текущее состояние фреймворка

| Тип | Количество | Расположение |
|-----|------------|--------------|
| Hooks | 12 | `.claude/hooks/*.py` |
| Skills | 12 | `.claude/skills/*/SKILL.md` |
| Commands | 37+ | `.claude/commands/*.md` |
| MCP Servers | 20+ | `.claude.json` |

---

## Hooks — Система событий

### 10 типов хуков Claude Code

```
┌─────────────────────────────────────────────────────────────────┐
│                        ЖИЗНЕННЫЙ ЦИКЛ                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SessionStart ──▶ UserPromptSubmit ──▶ PreToolUse ──▶ TOOL     │
│                                                    │            │
│                                                    ▼            │
│  SessionEnd ◀── Stop ◀── PostToolUse ◀────────────┘            │
│                                                                 │
│  Специальные: Notification, PreCompact, SubagentStop           │
│               PermissionRequest                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Описание каждого хука

| Хук | Когда срабатывает | Может блокировать | Типичное применение |
|-----|-------------------|-------------------|---------------------|
| **PreToolUse** | До вызова инструмента | ✅ Да | Валидация, логирование, роутинг |
| **PostToolUse** | После вызова инструмента | ❌ Нет | Анализ результатов, напоминания |
| **UserPromptSubmit** | При отправке сообщения | ✅ Да | Контекст, валидация, активация |
| **Notification** | При уведомлениях | ❌ Нет | Логирование, мониторинг |
| **Stop** | При остановке Claude | ❌ Нет | Сохранение состояния, отчёты |
| **SubagentStop** | При остановке субагента | ❌ Нет | Агрегация результатов |
| **SessionStart** | В начале сессии | ❌ Нет | Инициализация, приветствие |
| **SessionEnd** | В конце сессии | ❌ Нет | Сохранение, очистка |
| **PreCompact** | Перед компактификацией | ❌ Нет | Backup контекста |
| **PermissionRequest** | При запросе разрешений | ✅ Да | Безопасность |

### Формат конфигурации хуков

```json
// settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read|Write|Glob|Grep",
        "hooks": [
          {
            "type": "command",
            "command": "python path/to/hook.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "mcp__serena__activate_project",
        "hooks": [
          {
            "type": "command",
            "command": "python path/to/checker.py"
          }
        ]
      }
    ]
  }
}
```

### Входные данные хука (stdin JSON)

```json
{
  "session_id": "abc123",
  "tool_name": "Read",
  "tool_input": {
    "file_path": "/path/to/file.txt"
  },
  "tool_result": "содержимое файла..."  // только для PostToolUse
}
```

### Выходные данные хука (stdout JSON)

```json
{
  "continue": true,           // false = блокировать
  "decision": "allow",        // allow/block/modify/skip
  "reason": "Файл безопасен",
  "systemMessage": "📋 [HOOK MESSAGE] Информация для Claude",
  "modifiedInput": {},        // изменённые параметры (опционально)
  "claudeFallback": {         // если нужен fallback к Claude
    "hook_name": "my-hook",
    "prompt": "Что сделать вручную",
    "priority": "high"
  }
}
```

### Хуки в текущем фреймворке

| Хук | Назначение |
|-----|------------|
| `zai-router-mcpo.py` | Роутинг Read/Write/Glob/Grep через Z.AI |
| `serena-path-normalizer.py` | Нормализация путей Serena |
| `serena-index-checker.py` | Проверка индексации при активации |
| `git-commit-reminder.py` | Напоминание о коммите |
| `documentation-blocker.py` | Блокировка без документации |
| `pre-session-validator.py` | Валидация начала сессии |
| `post-commit-completer.py` | Завершение после коммита |

---

## Skills — Контейнеры знаний

### Структура SKILL.md

```yaml
---
name: skill-name                    # Уникальный идентификатор
description: Описание навыка        # Для каталога и авто-активации
allowed-tools:                      # Разрешённые инструменты
  - mcp__server__tool1
  - mcp__server__tool2
triggers:                           # Условия авто-активации
  - keywords: ["ключевое", "слово"]
    context: ["контекст"]
---

# Заголовок навыка

## 🎯 Purpose
Для чего этот навык...

## 🔄 Как использовать
Пошаговые инструкции...

## 📊 Примеры
Конкретные примеры применения...
```

### Типы навыков

#### 1. Процедурные навыки
Описывают **КАК** выполнять конкретные задачи:

```
- git-commit-message     → КАК формировать коммиты
- create-skill           → КАК создавать навыки
- create-hook            → КАК создавать хуки
- bsl-string-formatting  → КАК форматировать строки BSL
```

#### 2. Проактивные навыки
Автоматически активируются **ДО** выполнения задачи:

```
- proactive-rules     → Поиск правил ПЕРЕД задачей
- proactive-docs      → Поиск документации
- proactive-security  → Проверка безопасности
```

#### 3. Доменные навыки
Содержат знания о конкретной области:

```
- 1c-development              → Разработка 1С
- claude-code-self-knowledge  → Возможности Claude Code
- code-documentation-standard → Стандарты документирования
```

### Skills в текущем фреймворке

| Skill | Тип | Назначение |
|-------|-----|------------|
| `1c-development` | Доменный | Комплексная работа с 1С |
| `proactive-rules` | Проактивный | Поиск правил перед задачей |
| `proactive-docs` | Проактивный | Поиск документации |
| `create-skill` | Процедурный | Создание новых навыков |
| `create-hook` | Процедурный | Создание новых хуков |
| `git-commit-message` | Процедурный | Форматирование коммитов |

---

## MCP — Внешние инструменты

### Архитектура MCP

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────┐     stdio/HTTP     ┌──────────────────┐         │
│   │  Claude  │ ◀═══════════════▶  │   MCP Server     │         │
│   │  (Host)  │     JSON-RPC       │  (Tools/Resrc)   │         │
│   └──────────┘                    └──────────────────┘         │
│                                                                 │
│   Протокол: JSON-RPC 2.0 over stdio                            │
│   Формат: tools/call, resources/read, prompts/get              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Категории MCP серверов

#### 1. Анализ кода (1C/BSL)
```
- ast-grep-mcp          → AST анализ BSL кода
- bsl-platform-context  → API платформы 1С
- bsl-semantic-search   → Семантический поиск кода
- serena                → LSP для Python/JS/TS
```

#### 2. Документация и знания
```
- 1c-docs-rag           → RAG по документации
- auto-documenter       → Генерация документации
```

#### 3. Память и контекст
```
- memory-ai             → Важные сообщения
- conversation-memory   → Память сессий
- vector-memory         → Векторные паттерны
```

#### 4. Файловые операции
```
- ripgrep               → Быстрый поиск (rg)
- filesystem            → Файловые операции
```

#### 5. Утилиты
```
- markitdown            → Конвертация в Markdown
- lazy-mcp              → Динамическая загрузка
```

### Ключевые MCP серверы для поиска

#### 1c-docs-rag (RAG-поиск)

```python
# Поиск по документации и коду
mcp__1c-docs-rag__search_docs(
    query="правила BSL документирование",
    limit=5,
    search_type="hybrid"  # fulltext | semantic | hybrid
)

# RAG-ответ на вопрос
mcp__1c-docs-rag__ask_docs(
    question="Как использовать ast-grep для BSL?",
    top_k=5
)

# Валидация решения
mcp__1c-docs-rag__validate_solution(
    solution="код решения",
    check_type="all"  # standards | security | performance | best_practices
)
```

#### bsl-semantic-search (Поиск по коду)

```python
# Базовый семантический поиск
mcp__bsl-semantic-search__search_bsl_code(
    query="ОбработкаПроведения",
    limit=10,
    mode="semantic"  # semantic | fulltext | hybrid
)

# Интеллектуальный поиск с контекстом
mcp__bsl-semantic-search__intelligent_search(
    query="валидация документа перед записью",
    context_type="code_search",  # code_search | debugging | refactoring
    max_results=10
)

# Анализ графа зависимостей
mcp__bsl-semantic-search__analyze_graph(
    file_path="path/to/module.bsl",
    analysis_type="dependencies"  # dependencies | centrality | communities
)
```

#### ast-grep-mcp (AST-анализ)

```python
# Поиск по AST-паттерну
mcp__ast-grep-mcp__ast_grep(
    pattern="Процедура $NAME($$$PARAMS)",
    language="bsl",
    path="src/"
)

# Поиск с заменой (рефакторинг)
mcp__ast-grep-mcp__ast_grep(
    pattern="СтрНайти($STR, $SUB)",
    replacement="СтрНайти($STR, $SUB, 1)",
    mode="replace",
    dry_run=True
)
```

---

## Триада: Интеграция компонентов

### Паттерн 1: Событийная автоматизация

```
┌─────────────────────────────────────────────────────────────────┐
│  СОБЫТИЕ               ЛОГИКА                ДЕЙСТВИЕ          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PreToolUse:Write  →  Hook проверяет  →  MCP сохраняет        │
│                       документацию        в память              │
│                                                                 │
│  PostToolUse:Edit  →  Hook напоминает →  Claude коммитит      │
│                       о коммите                                 │
│                                                                 │
│  UserPromptSubmit  →  Hook ищет       →  Skill применяется    │
│                       правила                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Паттерн 2: Проактивный поиск знаний

```
USER MESSAGE
     │
     ▼
┌────────────────────┐
│ UserPromptSubmit   │  ← Hook активируется
│ Hook               │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Skill: proactive-  │  ← Skill определяет что искать
│ rules              │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ MCP: 1c-docs-rag   │  ← MCP выполняет поиск
│ search_docs()      │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ Claude применяет   │  ← Результат используется
│ найденные правила  │
└────────────────────┘
```

### Паттерн 3: Контекстная валидация

```python
# 1. PostToolUse хук срабатывает после activate_project
@PostToolUse(matcher="mcp__serena__activate_project")
def serena_index_checker(tool_result):
    project = extract_project_name(tool_result)

    # 2. Проверяем индексацию через MCP
    indexed = check_1c_docs_rag_index(project)

    if not indexed:
        # 3. Возвращаем systemMessage с инструкцией
        return {
            "continue": True,
            "systemMessage": f"""
            ⚠️ [INDEX PENDING] Проект {project} НЕ проиндексирован!

            Выполните: /index-project {project_path}
            """
        }
```

### Паттерн 4: Цепочка обработки

```
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE: Ticket → PR                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. UserPromptSubmit                                           │
│     └─▶ Hook: Загрузка контекста из memory-ai                  │
│                                                                 │
│  2. PreToolUse:Read                                            │
│     └─▶ Hook: Роутинг через zai-router (оптимизация)          │
│                                                                 │
│  3. Claude анализирует код                                     │
│     └─▶ Skill: proactive-rules → MCP: 1c-docs-rag             │
│                                                                 │
│  4. PostToolUse:Edit                                           │
│     └─▶ Hook: Напоминание о документации                       │
│                                                                 │
│  5. PostToolUse:Write                                          │
│     └─▶ Hook: Напоминание о коммите                            │
│                                                                 │
│  6. Stop                                                        │
│     └─▶ Hook: Сохранение в память + отчёт                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Поиск: Как находить информацию

### 🔴 КРИТИЧЕСКОЕ ПРАВИЛО ПОИСКА

**ПЕРЕД началом ЛЮБОЙ задачи Claude ОБЯЗАН выполнить поиск:**

```python
# 1. Поиск ПРАВИЛ (КАК делать)
mcp__1c-docs-rag__search_docs(
    query="правила {тип_задачи}",
    limit=3,
    search_type="hybrid"
)

# 2. Поиск ИНСТРУМЕНТОВ (ЧЕМ делать)
mcp__1c-docs-rag__search_docs(
    query="MCP tools {тип_задачи}",
    limit=3,
    search_type="hybrid"
)
```

### Типы поиска

| Тип | Описание | Когда использовать |
|-----|----------|-------------------|
| **fulltext** | FTS5 полнотекстовый | Точные термины, ключевые слова |
| **semantic** | Векторный по смыслу | Концепции, вопросы |
| **hybrid** | FTS5 + Semantic | Универсальный (рекомендуется) |

### Формирование поисковых запросов

#### Формат запроса
```
[действие] [технология] [контекст] [спецификация]
```

#### Примеры запросов

| Задача пользователя | Запрос для поиска |
|---------------------|-------------------|
| "Проанализируй BSL код" | `"анализ BSL AST-grep инструменты"` |
| "Создай документацию 1С" | `"документирование 1С auto-documenter outputDir"` |
| "Найди процедуру" | `"поиск процедура BSL паттерн ast-grep"` |
| "Исправь ошибку" | `"отладка debugging BSL инструменты"` |
| "Какой инструмент?" | `"выбор инструмент файл Read Write Edit"` |

### Поиск по проиндексированным проектам

#### Индексация проекта
```python
# 1. BSL файлы (smart mode - рекомендуется)
mcp__1c-docs-rag__index_bsl_project(
    project_path="D:/path/to/project",
    chunk_mode="smart",  # full | procedures | smart
    force=False          # True = переиндексация
)

# 2. XML метаданные
mcp__1c-docs-rag__index_xml_project(
    project_path="D:/path/to/project/src",
    xml_types=["subsystems", "forms", "rights", "languages"]
)
```

#### Поиск в проекте
```python
# Семантический поиск по коду
mcp__bsl-semantic-search__search_bsl_code(
    query="обработка проведения документа",
    limit=10,
    mode="hybrid"
)

# Интеллектуальный поиск с контекстом
mcp__bsl-semantic-search__intelligent_search(
    query="валидация перед записью",
    context_type="code_search"
)
```

#### Проверка индексации
```python
# Список проиндексированных проектов
mcp__1c-docs-rag__get_indexed_projects()

# Статистика индекса
mcp__1c-docs-rag__get_stats()
```

### Поиск в памяти

```python
# Важные сообщения из Memory-AI
mcp__memory-ai__get_important_messages(
    limit=5,
    min_importance=0.7
)

# Поиск по памяти
mcp__memory-ai__search_messages(
    query="последняя задача BSL"
)

# Контекст сессии
mcp__conversation-memory__get_session_context(
    limit=20
)
```

---

## Нюансы и лучшие практики

### 1. Порядок поиска инструментов

```
ПРИОРИТЕТ ВЫБОРА ИНСТРУМЕНТА
────────────────────────────
1. Native Tools (Read, Write, Edit) — первый выбор
2. Serena MCP (LSP, символы) — структурный анализ Python/JS/TS
3. AST-grep MCP — структурный анализ BSL ⭐
4. Ripgrep MCP — быстрый текстовый поиск
5. 1c-docs-rag — RAG поиск по документации
```

### 2. BSL анализ: ТОЛЬКО ast-grep

```
⭐⭐⭐ КРИТИЧЕСКОЕ ПРАВИЛО
─────────────────────────
Для анализа BSL кода ВСЕГДА использовать:
  mcp__ast-grep-mcp__ast_grep(language="bsl")

НЕ использовать Serena для BSL (30-40% надёжность)
```

### 3. Обработка результатов хуков

```python
# Правильная обработка systemMessage
if hook_result.get("systemMessage"):
    # Claude ОБЯЗАН прочитать и выполнить инструкции
    pass

# Обработка блокировки
if not hook_result.get("continue", True):
    # Инструмент заблокирован, использовать альтернативу
    pass

# Claude Fallback
if hook_result.get("claudeFallback"):
    fallback = hook_result["claudeFallback"]
    # Выполнить prompt из fallback
    execute_fallback(fallback["prompt"])
```

### 4. Matcher паттерны в hooks

```json
{
  "hooks": {
    "PreToolUse": [
      // Несколько инструментов через |
      {"matcher": "Read|Write|Glob|Grep", "hooks": [...]},

      // MCP инструменты с префиксом
      {"matcher": "mcp__serena__.*", "hooks": [...]},

      // Все инструменты
      {"matcher": ".*", "hooks": [...]}
    ]
  }
}
```

### 5. Избегайте зацикливания

```
⚠️ ПРОБЛЕМА: Hook вызывает тот же инструмент
───────────────────────────────────────────
PreToolUse:Read → Hook использует Read → ЗАЦИКЛИВАНИЕ!

✅ РЕШЕНИЕ: Использовать альтернативные инструменты
───────────────────────────────────────────
PreToolUse:Read → Hook использует mcp__ripgrep__search
```

### 6. Skill triggers vs manual invocation

```yaml
# YAML frontmatter в SKILL.md
triggers:
  - keywords: ["создай", "добавь"]    # Авто-активация по словам
    context: ["код", "модуль"]        # + контекст

# Ручной вызов через slash command
/skill-name arguments
```

### 7. MCP Server lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP SERVER LIFECYCLE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Cold Start (~3 сек) → Ready → Tool Calls → Idle → Shutdown   │
│                                                                 │
│  ⚠️ Первый вызов может быть медленным (cold start)            │
│  ✅ Последующие вызовы быстрые (server ready)                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 8. Фильтрация результатов поиска

```python
# Фильтрация по проекту в 1c-docs-rag
mcp__1c-docs-rag__search_docs_with_facets(
    query="обработка проведения",
    source="260119_GKSTCPLK-1981",  # Фильтр по проекту
    doc_type="bsl",                  # Фильтр по типу
    limit=10
)

# Поиск с фасетами
mcp__1c-docs-rag__get_available_facets()
# → Возвращает доступные doc_type, tags, source, date_range
```

---

## Примеры из фреймворка

### Пример 1: Проверка индексации при активации проекта

**Файл:** `.claude/hooks/serena-index-checker.py`

```python
# PostToolUse хук на mcp__serena__activate_project
def main():
    tool_input = json.loads(sys.stdin.read())
    project_name = tool_input.get("tool_input", {}).get("project", "")

    # Проверить индексацию
    indexed = check_project_indexed(project_name)

    if not indexed:
        result = {
            "continue": True,
            "systemMessage": f"""
            ⚠️ [INDEX PENDING] Проект {project_name} НЕ проиндексирован!

            Выполните: /index-project {project_path}
            """
        }
    else:
        result = {
            "continue": True,
            "systemMessage": f"✅ Проект {project_name} проиндексирован"
        }

    print(json.dumps(result))
```

### Пример 2: Проактивный поиск правил

**Файл:** `.claude/skills/proactive-rules/SKILL.md`

```markdown
## 🔄 Как использовать

### Step 1: Определить тип задачи
От сообщения пользователя определить:
- Технология: BSL, Python, MCP, Docker
- Операция: create, analyze, modify, document

### Step 2: Сформировать запрос
Query format: `[operation] [technology] [context]`
Пример: "анализ BSL AST-grep инструменты"

### Step 3: Выполнить поиск
```python
mcp__1c-docs-rag__search_docs({
  query: "<formed_query>",
  limit: 5,
  search_type: "hybrid"
})
```

### Step 4: Применить правила
Приоритет:
- ⭐⭐⭐ Critical → ОБЯЗАТЕЛЬНО применить
- ⭐⭐ Important → РЕКОМЕНДУЕТСЯ
- ⭐ Informational → ПО ЖЕЛАНИЮ
```

### Пример 3: Z.AI Router для оптимизации

**Файл:** `.claude/hooks/zai-router-mcpo.py`

```python
# PreToolUse хук на Read|Write|Glob|Grep
def main():
    input_data = json.loads(sys.stdin.read())
    tool_name = input_data.get("tool_name")
    tool_input = input_data.get("tool_input")

    # Проверить путь на кириллицу
    path = tool_input.get("file_path") or tool_input.get("path")
    if has_cyrillic(path):
        # Пропустить - native tool справится лучше
        return {"continue": True}

    # Роутинг через MCPO (Model Context Protocol Optimizer)
    result = call_mcpo(tool_name, tool_input)

    if result.success:
        return {
            "continue": False,  # Блокируем оригинальный вызов
            "decision": "skip",
            "systemMessage": f"[ZAI+MCPO] Result: {result.output}"
        }
    else:
        return {"continue": True}  # Fallback к native
```

---

## Чеклист создания интеграции

### Создание нового Hook

```
□ Определить тип хука (Pre/Post/UserPrompt/etc)
□ Определить matcher (регулярка для инструментов)
□ Создать Python скрипт в .claude/hooks/
□ Добавить в settings.json
□ Протестировать с реальными вызовами
□ Документировать в CLAUDE.md
```

### Создание нового Skill

```
□ Определить тип (процедурный/проактивный/доменный)
□ Создать SKILL.md с YAML frontmatter
□ Описать triggers (keywords + context)
□ Добавить allowed-tools
□ Написать пошаговые инструкции
□ Добавить примеры использования
```

### Подключение MCP Server

```
□ Добавить конфигурацию в .claude.json
□ Проверить доступность (stdio/HTTP)
□ Протестировать инструменты
□ Добавить в lazy-mcp для динамической загрузки
□ Документировать инструменты
```

---

## Заключение

Триада **Hooks + Skills + MCP** образует мощную систему автоматизации:

| Компонент | Роль | Ключевое преимущество |
|-----------|------|----------------------|
| **Hooks** | Событийный триггер | Автоматизация без ручного запуска |
| **Skills** | Процедурное знание | Консистентность выполнения задач |
| **MCP** | Внешние инструменты | Расширяемость возможностей |

**Главный принцип:**
```
HOOKS определяют КОГДА →
SKILLS определяют КАК →
MCP определяют ЧЕМ
```

---

**Версия:** 1.0.0
**Дата создания:** 2026-01-20
**Автор:** Claude Code
**Проект:** 1C-Enterprise_Framework
