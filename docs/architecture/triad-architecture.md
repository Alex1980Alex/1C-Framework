# Hooks + Skills + MCP Triad Architecture

## Три слоя

```
HOOKS (событийная автоматизация)     ← КОГДА делать     (3-5 сек)
   ↓  systemMessage
SKILLS (оркестрация + знания)        ← КАК делать       (persistent cache)
   ↓  tool calls
MCP TOOLS (исполнение)               ← ЧЕМ делать       (stateless JSON-RPC)
```

Каждый слой решает одну задачу. Ни один не заменяет другой.

## Hooks — решения (КОГДА)

**Протокол**: stdin JSON → stdout JSON. Timeout 3-5 сек.

```
Claude Code Event  →  Hook  →  { continue: true/false, systemMessage?, decision? }
```

**События**:
- `UserPromptSubmit` — пользователь отправил промпт
- `PreToolUse` — Claude собирается вызвать tool (можно заблокировать)
- `PostToolUse` — tool выполнен (можно создать задачу)
- `Stop` — Claude завершает работу (можно заблокировать)

**Что hooks НЕ делают**: не выполняют поиск, не вызывают LLM, не модифицируют файлы.

## Skills — знания (КАК)

**Формат**: Markdown файл `SKILL.md` с инструкциями для Claude.

**5-фазный цикл** (research skills):
```
Phase 0: Проверить кеш (_index.json)
Phase 1: Поиск в локальных данных (MCP tool)
Phase 2: Дополнительный веб-поиск (WebSearch)
Phase 3: Верификация (факты, терминология)
Phase 4: Атрибуция (каждый факт с источником)
Phase 5: Сохранение в кеш
```

**Типы skills**:
| Тип | Пример | Описание |
|-----|--------|----------|
| Domain | 1c-doc-research, tech-research | 5-фазный цикл + cache |
| Procedural | create-hook, doc-to-skill | Шаблон + чеклист |
| Program | triad-factory | Алгоритм Q1-Q5 → ШАГ 1-6 |
| Classifier | task-evaluation | Research/Brainstorm/Hybrid |

## MCP Tools — исполнение (ЧЕМ)

**Протокол**: JSON-RPC через stdio/SSE. Stateless.

**12 tools** (`src/mcp_server/server.py`):

| Tool | Назначение |
|------|-----------|
| `index_pdf` | Загрузка, разбиение, embedding, индексация PDF |
| `search_documents` | Семантический/vector/graph/BM25/hybrid поиск |
| `ask_question` | RAG Q&A с цитатами |
| `graph_query` | Запрос к графу знаний |
| `analyze` | Аналитический RAG agent |
| `research` | Deep research с верификацией |
| `web_search` | Интернет-поиск |
| `search_with_fallback` | Локальный + веб с fusion |
| `list_collections` | Список коллекций |
| `list_documents` | Список документов |
| `get_toc` | Оглавление документа |
| `get_stats` | Статистика индекса |

## Поток данных: пример

### "Что такое справочники в 1С?"

```
USER: "что такое справочники в 1С?"
         │
         ▼
[Hook] research-task-detector (UserPromptSubmit)
         │ keyword: "что такое" + "справочники" + "1С"
         │ → systemMessage: "Используй skill 1c-doc-research"
         ▼
[Skill] 1c-doc-research
         │ Phase 0: cache/_index.json → miss
         │ Phase 1: MCP tool search_documents(strategy=hybrid, k=10)
         │ Phase 2: WebSearch(its.1c.ru)
         │ Phase 3-4: verify + cite
         ▼
[Hook] knowledge-cache-reminder (PostToolUse:WebSearch)
         │ → add_task("сохрани в кеш")
         ▼
[Skill] 1c-doc-research Phase 5
         │ → Write cache/справочники.md
         │ → Update _index.json
         ▼
[Hook] task-enforcer (Stop)
         │ hook-todos.json: pending=0
         │ → allow exit
         ▼
ОТВЕТ С АТРИБУЦИЕЙ
```

### "Давай создадим новый домен для DevOps"

```
USER: "давай создадим новый домен для DevOps"
         │
         ▼
[Hook] decision-to-triad (UserPromptSubmit)
         │ fuzzy: "давай создадим" + "новый домен"
         │ → systemMessage: "Используй skill triad-factory"
         ▼
[Skill] triad-factory
         │ Q1: Hook нужен? → Да
         │ Q2: Skill нужен? → Да
         │ Q3: MCP tool? → Да
         │ Q4: Cache? → Да
         │ Q5: Enforcer? → Да
         │ → ШАГ 1-3: создать артефакты
         ▼
[Hook] factory-enforcer (PostToolUse:Write)
         │ → add_task("ШАГ 4: Register")
         │ → add_task("ШАГ 5: Test")
         ▼
[Claude] ШАГ 4-5: settings.json + test
         ▼
[Hook] task-enforcer (Stop)
         │ hook-todos.json: pending=0
         │ → allow exit
         ▼
АРТЕФАКТ ИНТЕГРИРОВАН
```

### Автоматический коммит изменений

```
Claude завершает работу
         │
         ▼
[Hook] git-commit-enforcer (Stop)
         │ git status --porcelain
         │ фильтр: WATCHED_PATHS = [".claude/"]
         │ статусы: M, A, D, R, C, U, T (не ??)
         │
         ├─ нет изменений → allow exit
         │
         └─ есть изменения → BLOCK (exit 2)
            │ reason: "13 файлов в .claude/"
            │ инструкция: git add + git commit
            ▼
[Claude] создаёт коммит
            ▼
[Hook] git-commit-enforcer (Stop, повтор)
            │ git status → чисто
            │ → allow exit
            ▼
СЕССИЯ ЗАВЕРШЕНА, ИЗМЕНЕНИЯ СОХРАНЕНЫ
```

## Коммуникация между слоями

```
Hook ←→ Hook:     через hook-todos.json (file-based, locked)
Hook  → Skill:    через systemMessage ("используй skill X")
Skill → MCP:      через tool call (search_documents, ask_question)
Hook  → MCP:      нет прямой связи
```

## Почему не объединить в один MCP

| Возможность | Hook | Skill | MCP |
|-------------|------|-------|-----|
| Event triggers (UserPromptSubmit) | да | нет | нет |
| Блокировка выхода (Stop) | да | нет | нет |
| Persistent cache | нет | да | нет |
| Tool execution | нет | нет | да |
| Domain knowledge | нет | да | нет |
| Workflow enforcement | да | нет | нет |

MCP — это tools. Hooks — это events. Skills — это knowledge. Три разных механизма для трёх разных задач.

## См. также

- [Core/Framework Separation](core-framework-separation.md)
- [Hooks Reference](hooks-reference.md)
- [Skills Reference](skills-reference.md)
- [Ralph Wiggum](ralph-wiggum.md)
