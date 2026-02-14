---
name: hooks-skills-mcp-triad
description: "Используй этот скилл для понимания архитектуры Hooks + Skills + MCP в PDF Framework. Триггеры: 'триада', 'triad', 'hooks skills mcp', 'как работают хуки', 'автоматизация фреймворка', 'как устроена интеграция', 'архитектура хуков', 'hook architecture'."
---

# Hooks + Skills + MCP — Триада PDF Framework

## Обзор

**Этот файл — и знание, и программа.** Skill, который описывает как создавать другие skills, hooks и инструменты. Мета-уровень: триада, описывающая саму триаду. Когда хук `decision-to-triad.py` ловит решение в чате, он направляет сюда — и Фабрика (ШАГ 1-5) исполняется как алгоритм.

Триада — универсальный цикл принятия и закрепления решений на **любом** уровне:

```
СОБЫТИЕ (что произошло?)  →  ЗНАНИЕ (что делать?)  →  ИНСТРУМЕНТ (чем сделать?)
```

Уровни не отдельные — **Hook связывает разговор и автоматизацию**. Пример ниже иллюстрирует общую концепцию; сама концепция (Фабрика, классификация, формулы) описана в этом файле далее:

```
Пользователь пишет в чат                     ← СОБЫТИЕ
     │
     ▼
Hook (.py)                                   ← Ловит событие, классифицирует
     │
     ▼
Skill (.md)                                  ← ЗНАНИЕ: КАК действовать
     │
     ▼
MCP Tool / API                               ← ИНСТРУМЕНТ: ЧЕМ сделать
     │
     ▼
Артефакт (cache / hook / skill / MEMORY)     ← РЕЗУЛЬТАТ → следующая сессия
```

Hook — это **не абстрактная автоматизация рядом с чатом**. Хук срабатывает **ВНУТРИ** разговора. Он ловит то, что пользователь написал, и превращает это в действие. Хук = событие чата, закодированное в `.py`.

| Компонент | Роль | Вопрос | Формат |
|-----------|------|--------|--------|
| **Hooks** | Событие в чате → триггер | КОГДА делать? | Python скрипты (.py) |
| **Skills** | Процедурное знание | КАК / ЧТО делать? | Markdown (SKILL.md) |
| **Инструменты** | Нативные (Write/Edit) + MCP | ЧЕМ делать? | Claude Code tools + JSON-RPC серверы |

**Ключевое правило:** Если в разговоре принято решение — оно ДОЛЖНО стать артефактом. Хук ловит событие чата. Skill описывает решение. MCP реализует инструментом. Если решение осталось только в чате — оно потеряно.

**Конкретные реализации** этого паттерна — см. Pipelines ниже (1С Research, Tech Research, Decision→Artifact, Stop Enforcement).

---

## ФАБРИКА ТРИАДЫ — главный процесс

**Любое новое решение, задача или требование проходит через эту фабрику.** Результат — набор артефактов (hooks, skills, MCP tools), которые система использует автоматически.

Фабрика превращает **разговор** в **работающую автоматизацию**:

```
ВХОД: Новое решение / требование / задача
  │
  ▼
ШАГ 1: КЛАССИФИКАЦИЯ — ответь на 5 вопросов
  │
  ▼
ШАГ 2: ФОРМУЛА — определи комбинацию компонентов
  │
  ▼
ШАГ 3: ГЕНЕРАЦИЯ — создай артефакты по шаблонам
  │
  ▼
ШАГ 4: СВЯЗЫВАНИЕ — подключи к существующей системе
  │
  ▼
ШАГ 5: ВЕРИФИКАЦИЯ — проверь что всё работает
  │
  ▼
ВЫХОД: Работающая автоматизация (или документированное знание)
```

---

### ШАГ 1: КЛАССИФИКАЦИЯ

Ответь на 5 вопросов (да/нет):

| # | Вопрос | Если ДА → компонент |
|---|--------|---------------------|
| Q1 | Это должно срабатывать **автоматически** на событие? | → **Hook** нужен |
| Q2 | Есть **процедура/знание** которое нужно описать? | → **Skill** нужен |
| Q3 | Нужен **внешний инструмент** (API, DB, поиск)? | → **MCP Tool** нужен |
| Q4 | Нужно **накапливать знания** по теме? | → **Cache** нужен (в Skill) |
| Q5 | Нужно **принудительно** выполнять (не пропускать)? | → **Enforcer** нужен (Hook Stop) |

**Примеры классификации:**

```
"Исследование новой технологии" →
  Q1=Да (при вопросе автоматически роутить) → Hook
  Q2=Да (5-фазный research workflow) → Skill
  Q3=Да (WebSearch, MCP search) → MCP
  Q4=Да (кеш знаний) → Cache
  Q5=Да (обязательно кешировать) → Enforcer
  ФОРМУЛА: Hook + Skill + MCP + Cache + Enforcer

"Шаблон создания хуков" →
  Q1=Нет (только по запросу) → —
  Q2=Да (шаблон, чеклист) → Skill
  Q3=Нет (работа с файлами) → —
  Q4=Нет → —
  Q5=Нет → —
  ФОРМУЛА: Skill-only

"Оптимизация параметров поиска" →
  Q1=Да (перед каждым вызовом API) → Hook
  Q2=Нет (простая проверка) → —
  Q3=Нет → —
  Q4=Нет → —
  Q5=Нет → —
  ФОРМУЛА: Hook-only
```

---

### ШАГ 2: ФОРМУЛА

По ответам на Q1-Q5 определяется формула — комбинация компонентов:

| Формула | Когда | Создаваемые файлы |
|---------|-------|--------------------|
| **Hook + Skill + MCP + Cache + Enforcer** | Новый домен знаний | skill/, detector, reminder, enforcer, MCP tool |
| **Hook + Skill + MCP** | Архитектурное решение + инструмент | hook.py, SKILL.md, MCP tool |
| **Hook + Skill** | Автоматизация workflow | hook.py, SKILL.md (или фаза в существующем) |
| **Skill + MCP** | Инструмент по запросу | SKILL.md, MCP tool |
| **Skill + Cache** | Доменное знание без автоматики | SKILL.md, cache/ |
| **Skill-only** | Процедура / шаблон | SKILL.md |
| **Hook-only** | Простой триггер / валидация | hook.py |
| **MEMORY-only** | Баг / workaround / факт | MEMORY.md запись |

---

### ШАГ 3: ГЕНЕРАЦИЯ

Для каждого компонента в формуле — конкретные файлы:

#### Если нужен Hook:

| Подтип | Event | Шаблон |
|--------|-------|--------|
| Детектор (роутер) | UserPromptSubmit | Keyword scoring → systemMessage с инструкцией skill |
| Мета-роутер | UserPromptSubmit | Keyword scoring → systemMessage с инструкцией Фабрики (Q1-Q5) |
| Напоминание | PostToolUse | Проверка результата → add_task() + systemMessage |
| Валидатор | PreToolUse | Проверка параметров → systemMessage или block() |
| Блокировщик | Stop | Проверка pending tasks → exit(2) если есть |

```
Файл: .claude/hooks/<name>.py
  → Наследует BaseHook из base/protocol.py
  → Регистрация в settings.json
  → См. skill `create-hook` для полного шаблона
```

#### Если нужен Skill:

| Подтип | Содержимое |
|--------|-----------|
| Доменный (research) | 5 фаз, source hierarchy, шаблон кеша, trigger keywords |
| Процедурный | Шаблон, чеклист, антипаттерны, примеры |
| Мета | Архитектура, диаграммы, связи между компонентами |

```
Директория: .claude/skills/<name>/
  → SKILL.md с YAML frontmatter (name, description, triggers)
  → См. skill `doc-to-skill` для конвертации
```

#### Если нужен Cache:

```
Директория: .claude/skills/<domain>-research/cache/
  → _topic_template.md (шаблон, N категорий)
  → _index.json (реестр тем: keywords, last_verified)
  → <topic-name>.md (каждая исследованная тема)
```

**Критерии домена для кеша:**
- Уникальные источники (URL, авторитеты) → **выделенный** домен
- Уникальная терминология (не пересекается) → **выделенный** домен
- Похожий workflow / пересекающиеся источники → **общий** домен (расширить существующий)

#### Если нужен MCP Tool:

```
Файл: src/mcp_server/server.py
  → @server.tool() декоратор
  → Обновить .vscode/mcp.json
  → Обновить таблицу MCP в этом скилле
```

#### Если нужен Enforcer:

```
Связка:
  1. Hook (PostToolUse/другой) вызывает add_task() → hook-todos.json
  2. Hook (Stop) task-enforcer.py читает hook-todos.json
  3. Если pending → exit(2) BLOCK
  4. Claude выполняет → complete_task() → Stop ALLOW
```

---

### ШАГ 4: СВЯЗЫВАНИЕ

После создания артефактов — подключить их к системе:

| Артефакт | Подключение |
|----------|-------------|
| Hook (.py) | Добавить в `.claude/settings.json` → hooks → EventName |
| Skill (SKILL.md) | Автоматически подхватывается Claude Code по triggers в frontmatter |
| MCP Tool | Регистрация через `@server.tool()` в server.py |
| Cache | Инициализировать `_index.json`, добавить инвалидацию |
| Enforcer | Связать с task-enforcer.py через hook-todos.json |

**Связи между компонентами:**
```
Hook (detector)    ──systemMessage──→ Claude ──читает──→ Skill (research)
Hook (meta-router) ──systemMessage──→ Claude ──читает──→ Skill (triad/factory)
                                          │
Skill (research) ──WebSearch──→ Hook (reminder) ──add_task──→ hook-todos.json
                                                                    │
Claude ──Stop──→ Hook (enforcer) ──reads──→ hook-todos.json ──pending?──→ BLOCK
```

**Обновить реестры:**
- Таблица Hooks в этом скилле
- Таблица Skills в этом скилле
- Таблица MCP tools (если менялась)
- CLAUDE.md → Knowledge Cache / Active Skills (если новый домен/skill)
- MEMORY.md → краткая запись

---

### ШАГ 5: ВЕРИФИКАЦИЯ

| Компонент | Тест |
|-----------|------|
| Hook | `echo '{"prompt":"тест"}' \| python hook.py` → проверить stdout JSON |
| Skill | Открыть новую сессию → задать вопрос по triggers → skill подхватился? |
| MCP Tool | `curl localhost:8000/...` или MCP client call |
| Cache | Проверить `_index.json` обновился после исследования |
| Enforcer | Создать pending task → попытаться остановиться → BLOCK? |
| Связки | Полный pipeline: вопрос → detector → skill → reminder → enforcer |

---

## Сквозной пример: Фабрика порождает домен tech-research

Пошаговое применение фабрики к реальному решению:

```
ВХОД: "RAG/ML/Python нужен отдельный домен знаний, не в 1С"

ШАГ 1: КЛАССИФИКАЦИЯ
  Q1=Да (автоматически роутить при вопросе) → Hook
  Q2=Да (5-фазный research) → Skill
  Q3=Да (WebSearch, MCP search) → MCP
  Q4=Да (кеш знаний) → Cache
  Q5=Да (обязательно кешировать) → Enforcer

ШАГ 2: ФОРМУЛА = Hook + Skill + MCP + Cache + Enforcer

ШАГ 3: ГЕНЕРАЦИЯ
  Skill:  skills/tech-research/SKILL.md (5 фаз, 7 категорий)
  Cache:  skills/tech-research/cache/_topic_template.md
          skills/tech-research/cache/_index.json
  Hook:   TECH_TERMS добавлен в research-task-detector.py
          TECH_SIGNALS добавлен в knowledge-cache-reminder.py
  MCP:    search_documents уже есть (переиспользование)
  Enforcer: task-enforcer.py уже есть (переиспользование)

ШАГ 4: СВЯЗЫВАНИЕ
  detector → systemMessage "используй tech-research"
  reminder → add_task("Сохрани в Tech-кеш")
  enforcer → читает hook-todos.json (без изменений)
  Обновлены: triad skill, CLAUDE.md, MEMORY.md

ШАГ 5: ВЕРИФИКАЦИЯ
  echo '{"prompt":"как работает ColBERT?"}' | python research-task-detector.py
  → {"continue":true,"systemMessage":"[TECH-RESEARCH-DETECTED]..."}  ✓
```

---

## Примеры готовых формул (справочник)

| Решение | Формула | Артефакты |
|---------|---------|-----------|
| Новый домен (tech-research) | Hook+Skill+MCP+Cache+Enforcer | SKILL.md, cache/, TERMS в детекторе |
| Автоматизация кеширования | Hook+Hook+Skill | reminder.py, enforcer.py, Фаза 5 |
| Захват решений из чата | Hook+Skill | decision-to-triad.py, hooks-skills-mcp-triad |
| Документирование workflow | Skill-only | doc-to-skill/SKILL.md |
| Простая валидация | Hook-only | search-optimizer.py |
| Баг/workaround | MEMORY-only | MEMORY.md запись |

---

## Текущая конфигурация

### Hooks (6 шт.) — КОГДА

| Hook | Event | Matcher | Назначение |
|------|-------|---------|-----------|
| `research-task-detector.py` | UserPromptSubmit | — | Детекция ВОПРОСОВ → роутинг: 1С → `1c-doc-research`, Tech → `tech-research` |
| `decision-to-triad.py` | UserPromptSubmit | — | Детекция РЕШЕНИЙ/ИДЕЙ → роутинг через Фабрику (Q1-Q5) |
| `knowledge-cache-reminder.py` | PostToolUse | WebSearch\|WebFetch | Напоминание сохранить в кеш: 1С или Tech |
| `search-optimizer.py` | PreToolUse | Bash | Оптимизация параметров Search API |
| `task-enforcer.py` | Stop | — | Блокировка без выполнения mandatory задач |
| `ralph_wiggum_stop.py` | Stop | — | Контроль итеративного цикла Ralph |

### Skills (6 шт.) — КАК / ЧТО

| Skill | Тип | Домен | Назначение |
|-------|-----|-------|-----------|
| `1c-doc-research` | Доменный | 1С | Исследование 1С: 5 фаз, кеш знаний (8 категорий), атрибуция |
| `tech-research` | Доменный | RAG/ML/Python | Исследование технологий: 5 фаз, кеш знаний (7 категорий) |
| `doc-to-skill` | Процедурный | — | Конвертер документации в SKILL.md |
| `pdf-knowledge` | Доменный | PDF | Работа с MCP-инструментами PDF |
| `create-hook` | Процедурный | — | Создание новых хуков (шаблон, чеклист) |
| `hooks-skills-mcp-triad` | Мета | — | Этот документ — архитектура триады + фабрика |

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
     │  → systemMessage: "Прогони через ФАБРИКУ ТРИАДЫ (Q1-Q5)"
     ▼
[КАК] Skill: hooks-skills-mcp-triad (Фабрика, ШАГ 1-5)
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

Это мета-цикл: хук ловит **саму идею** из чата и превращает её в работающую автоматизацию через Фабрику.

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
│   ├── decision-to-triad.py       (РЕШЕНИЯ → Factory Q1-Q5)
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
│   └── hooks-skills-mcp-triad/
├── cache/
│   └── hook-todos.json          (задачи от хуков)
├── settings.json                (регистрация хуков)
└── commands/
    └── pdf-search.md
```

### Протокол hook stdin/stdout

**Вход (stdin JSON):**
```json
{
  "session_id": "abc123",
  "prompt": "текст промпта",
  "tool_name": "Read",
  "tool_input": {"file_path": "..."},
  "tool_result": "..."
}
```

**Выход (stdout JSON) — два варианта:**

Подсказка (не блокирует):
```json
{"continue": true, "systemMessage": "Информация для Claude"}
```

Блокировка:
```json
{"continue": false, "decision": "block", "reason": "причина блокировки"}
```

### Коммуникация между хуками

Хуки общаются через `hook-todos.json`:
- **knowledge-cache-reminder** создаёт задачу → **task-enforcer** читает и блокирует stop
- Файл защищён file lock (Windows msvcrt / Unix fcntl)
- Atomic writes предотвращают corruption

---

## Принципы

1. **Hooks легковесны** — keyword matching, file read, не тяжёлые вычисления (3-5s timeout)
2. **Skills информативны** — полные инструкции, шаблоны, примеры, антипаттерны
3. **MCP мощные** — тяжёлая работа (поиск, индексация, RAG) в MCP серверах
4. **Graceful degradation** — хуки никогда не ломают workflow (исключение → pass through)
5. **Separate state** — hook-todos.json отделён от Claude TodoWrite (нет race conditions)
6. **Фабрика как процесс** — каждое решение проходит через ШАГ 1-5, а не ad-hoc
