---
name: hooks-skills-mcp-triad
description: "Используй этот скилл для понимания архитектуры Hooks + Skills + MCP в PDF Framework. Триггеры: 'триада', 'triad', 'hooks skills mcp', 'как работают хуки', 'автоматизация фреймворка', 'как устроена интеграция', 'архитектура хуков', 'hook architecture'."
---

# Hooks + Skills + MCP — Реализация в PDF Framework

**Этот файл — знание.** Описывает конкретную реализацию триады в этом проекте: какие хуки, скиллы и MCP-инструменты существуют, как они связаны, как работают вместе.

Для создания нового компонента — используй Фабрику: skill `triad-factory` (ШАГ 1-5, Q1-Q5, формулы).

---

## Текущая конфигурация

### Hooks (6 шт.) — КОГДА

| Hook | Event | Matcher | Назначение |
|------|-------|---------|-----------|
| `research-task-detector.py` | UserPromptSubmit | — | Детекция ВОПРОСОВ → роутинг: 1С → `1c-doc-research`, Tech → `tech-research` |
| `decision-to-triad.py` | UserPromptSubmit | — | Детекция РЕШЕНИЙ/ИДЕЙ → роутинг через Фабрику (`triad-factory`, Q1-Q5) |
| `knowledge-cache-reminder.py` | PostToolUse | WebSearch\|WebFetch | Напоминание сохранить в кеш: 1С или Tech |
| `search-optimizer.py` | PreToolUse | Bash | Оптимизация параметров Search API |
| `task-enforcer.py` | Stop | — | Блокировка без выполнения mandatory задач |
| `ralph_wiggum_stop.py` | Stop | — | Контроль итеративного цикла Ralph |

### Skills (7 шт.) — КАК / ЧТО

| Skill | Тип | Домен | Назначение |
|-------|-----|-------|-----------|
| `1c-doc-research` | Доменный | 1С | Исследование 1С: 5 фаз, кеш знаний (8 категорий), атрибуция |
| `tech-research` | Доменный | RAG/ML/Python | Исследование технологий: 5 фаз, кеш знаний (7 категорий) |
| `doc-to-skill` | Процедурный | — | Конвертер документации в SKILL.md |
| `pdf-knowledge` | Доменный | PDF | Работа с MCP-инструментами PDF |
| `create-hook` | Процедурный | — | Создание новых хуков (шаблон, чеклист) |
| `triad-factory` | Программа | — | Фабрика: универсальный алгоритм создания компонентов (ШАГ 1-5) |
| `hooks-skills-mcp-triad` | Знание | — | Этот документ — реализация триады в проекте |

### MCP Server (1 сервер, 12 инструментов) — ЧЕМ

| Инструмент | Назначение |
|-----------|-----------|
| `index_pdf` | Индексация PDF в vector + graph store |
| `search_documents` | Семантический поиск (vector/graph/hybrid/bm25) |
| `ask_question` | RAG-ответ с цитированием |
| `graph_query` | Запрос к графу знаний |
| `analyze` | Аналитический RAG (multi-round evidence) |
| `research` | Deep research с верификацией |
| `web_search` | Поиск в интернете (Tavily/SerpAPI/DuckDuckGo) |
| `search_with_fallback` | Локальный + веб с fusion |
| `list_collections` | Список коллекций |
| `list_documents` | Список документов |
| `get_toc` | Оглавление документа |
| `get_stats` | Статистика индекса |

---

## Рабочие pipeline (как триада работает)

### Pipeline 1: 1С Research

```
ПОЛЬЗОВАТЕЛЬ: "что такое справочники в 1С?"
     │
     ▼
[КОГДА] research-task-detector.py (UserPromptSubmit)
     │  Keyword scoring: "что такое" + "справочники" + "1С" → strong signal
     │  → systemMessage: "используй 1c-doc-research"
     ▼
[КАК] Skill: 1c-doc-research
     │  Фаза 0: проверка кеша (_index.json)
     │  Фаза 1: POST /search/ask ─────────── [ЧЕМ] MCP: pdf-vector-graph
     │  Фаза 2: WebSearch (its.1c.ru, infostart.ru)
     │  Фаза 3: верификация + терминология
     │  Фаза 4: атрибуция каждого факта
     ▼
[КОГДА] knowledge-cache-reminder.py (PostToolUse:WebSearch)
     │  Результаты содержат 1С-термины → score >= 2
     │  → add_task("Сохранить в кеш") в hook-todos.json
     │  → systemMessage: "Фаза 5: сохрани в кеш"
     ▼
[КАК] Skill: 1c-doc-research (Фаза 5)
     │  → cache/<справочники>.md по шаблону (8 категорий)
     │  → _index.json обновлён
     ▼
ОТВЕТ ПОЛЬЗОВАТЕЛЮ с атрибуцией
```

### Pipeline 2: Tech Research

```
ПОЛЬЗОВАТЕЛЬ: "как работает ColBERT reranking?"
     │
     ▼
[КОГДА] research-task-detector.py (UserPromptSubmit)
     │  Keyword scoring: "как работает" + "colbert" + "reranking" → tech signal
     │  → systemMessage: "используй tech-research"
     ▼
[КАК] Skill: tech-research
     │  Фаза 0: проверка кеша (tech-research/cache/_index.json)
     │  Фаза 1: WebSearch official docs (sbert.net, GitHub)
     │  Фаза 2: WebSearch papers (arxiv), benchmarks
     │  Фаза 3: верификация + наш опыт (MEMORY.md)
     │  Фаза 4: атрибуция каждого факта
     ▼
[КОГДА] knowledge-cache-reminder.py (PostToolUse:WebSearch)
     │  Результаты содержат tech-термины → score >= 2
     │  → add_task("Сохранить в кеш (Tech)") в hook-todos.json
     │  → systemMessage: "Фаза 5: сохрани в tech-research/cache/"
     ▼
[КАК] Skill: tech-research (Фаза 5)
     │  → cache/<colbert-reranking>.md по шаблону (7 категорий)
     │  → _index.json обновлён
     ▼
ОТВЕТ ПОЛЬЗОВАТЕЛЮ с атрибуцией
```

### Pipeline 3: Decision → Artifact (мета-цикл)

```
ПОЛЬЗОВАТЕЛЬ: "давай создадим новый домен для DevOps"
     │
     ▼
[КОГДА] decision-to-triad.py (UserPromptSubmit)
     │  Keyword scoring: "давай создадим" + "новый домен" → strong signal
     │  → systemMessage: "Прогони через ФАБРИКУ ТРИАДЫ (skill triad-factory)"
     ▼
[КАК] Skill: triad-factory (Фабрика, ШАГ 1-5)
     │  Q1=Да → Hook   Q2=Да → Skill   Q3=Да → MCP
     │  Q4=Да → Cache  Q5=Да → Enforcer
     │  ФОРМУЛА: Hook + Skill + MCP + Cache + Enforcer
     ▼
[ЧЕМ] Claude создаёт артефакты (Write/Edit + MCP):
     │  skills/devops-research/SKILL.md
     │  skills/devops-research/cache/_index.json
     │  DEVOPS_TERMS в research-task-detector.py
     │  DEVOPS_SIGNALS в knowledge-cache-reminder.py
     │  settings.json, MEMORY.md обновлены
     ▼
ВЕРИФИКАЦИЯ → echo '{"prompt":"как работает helm?"}' | python detector
```

### Pipeline 4: Stop Enforcement

```
knowledge-cache-reminder ──[add_task()]──→ hook-todos.json
                                               │
                                          [read on Stop]
                                               │
                                               ▼
                                        task-enforcer.py
                                          │         │
                                    pending?     no pending
                                          │         │
                                    exit(2)      exit(0)
                                    BLOCK        ALLOW
```

---

## Инфраструктура

### Файловая структура

```
.claude/
├── hooks/
│   ├── base/
│   │   ├── __init__.py          (BaseHook, HookInput, HookOutput)
│   │   └── protocol.py          (протокол stdin/stdout JSON)
│   ├── shared/
│   │   ├── __init__.py          (re-exports)
│   │   ├── task_master.py       (задачи: add, complete, pending, cooldown)
│   │   └── hook_lock.py         (межхуковая синхронизация)
│   ├── research-task-detector.py   (ВОПРОСЫ → skill routing)
│   ├── decision-to-triad.py       (РЕШЕНИЯ → triad-factory Q1-Q5)
│   ├── knowledge-cache-reminder.py
│   ├── task-enforcer.py
│   ├── search-optimizer.py
│   └── ralph_wiggum_stop.py
├── skills/
│   ├── 1c-doc-research/         (+ cache/ — 8 категорий, 1С-домен)
│   ├── tech-research/           (+ cache/ — 7 категорий, RAG/ML/Python)
│   ├── doc-to-skill/            (+ references/)
│   ├── pdf-knowledge/
│   ├── create-hook/
│   ├── triad-factory/           (ПРОГРАММА: Фабрика ШАГ 1-5)
│   └── hooks-skills-mcp-triad/  (ЗНАНИЕ: этот файл)
├── cache/
│   └── hook-todos.json          (задачи от хуков)
├── settings.json                (регистрация хуков)
└── commands/
    └── pdf-search.md
```

### Коммуникация между хуками

Хуки общаются через `hook-todos.json`:
- **knowledge-cache-reminder** создаёт задачу → **task-enforcer** читает и блокирует stop
- Файл защищён file lock (Windows msvcrt / Unix fcntl)
- Atomic writes предотвращают corruption

---

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| `except: pass` без logging | Скрывает ошибки | `BaseHook.run()` уже обрабатывает — не нужно дополнительно |
| Hook вызывает тот же инструмент | Зацикливание (PreToolUse:Read → Read) | Использовать альтернативный инструмент |
| Блокировка без причины | Claude не понимает что делать | Всегда указывать `reason` в `block()` |
| Относительные пути в settings.json | Не находит python.exe | Абсолютные: `D:\\1С-Framework\\.venv\\Scripts\\python.exe` |
| Тяжёлые вычисления в хуке | Timeout (3-5s) | Хуки должны быть лёгкими (keyword matching, file read) |
