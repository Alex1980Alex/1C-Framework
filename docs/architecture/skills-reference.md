# Skills Reference

## Обзор

9 skills в `.claude/skills/`:

| Категория | Skills | Тип |
|-----------|--------|-----|
| **Procedural** (4) | triad-factory, create-hook, doc-to-skill, task-evaluation | Алгоритмы и шаблоны |
| **Knowledge** (4) | 1c-doc-research, tech-research, architecture-research, hooks-skills-mcp-triad | Домены знаний + кеш |
| **Project** (1) | pdf-knowledge | Специфичные для PDF Framework |

## Procedural Skills

### triad-factory
| | |
|---|---|
| **Trigger** | "фабрика", "factory", "создать компонент", "новый домен", "Q1-Q5" |
| **Тип** | Program (алгоритм) |

Универсальный шаблон создания компонентов. Алгоритм:

1. **Classify** (5 вопросов):
   - Q1: Нужна автоматизация? → Hook
   - Q2: Нужна процедура? → Skill
   - Q3: Нужен инструмент? → MCP
   - Q4: Нужен кеш? → Cache structure
   - Q5: Нужен enforcer? → Guard hook

2. **Formula**: Комбинация Hook/Skill/MCP/Cache/Enforcer
3. **Generate**: Создать файлы по шаблонам
4. **Connect**: settings.json, registries, MEMORY.md
5. **Verify**: Тесты

---

### create-hook
| | |
|---|---|
| **Trigger** | "создай hook", "новый хук", "hook for" |
| **Тип** | Procedural (шаблон + чеклист) |

Шаблон для создания нового hook с BaseHook protocol. Включает:
- Python template с auto-discovery sys.path
- Чеклист регистрации (settings.json, MANDATORY_HOOKS)
- Примеры тестирования (`echo | python hook.py`)

---

### doc-to-skill
| | |
|---|---|
| **Trigger** | "сделай скилл из", "оформи как скилл", "превратить в скилл" |
| **Тип** | Procedural (конвертер) |

Конвертирует сырую документацию/статьи/README в структурированный SKILL.md для Claude Code.

---

### task-evaluation
| | |
|---|---|
| **Trigger** | "research или brainstorm", "тип задачи", "придумай", "как улучшить" |
| **Тип** | Classifier |

Классифицирует задачи на 3 типа:

| Тип | Сигналы | Workflow |
|-----|---------|---------|
| **Research** | "найди", "расскажи", "что такое" | Domain skill (5 фаз) |
| **Brainstorm** | "придумай", "предложи", "спроектируй" | 5 фаз: Problem → Ideation → Matrix → Recommendation → ADR |
| **Hybrid** | "как улучшить", "как оптимизировать" | Research фазы → Brainstorm фазы |

---

## Knowledge Skills

> Cache в `.claude/skills/<skill>/cache/`.

### 1c-doc-research
| | |
|---|---|
| **Trigger** | "расскажи про [1С-объект]", "справочники", "документы", "регистры", "BSL" |
| **Тип** | Domain (5-фазный цикл) |
| **Домен** | Платформа 1С:Предприятие 8.3.27 |

**8 категорий знаний** в cache:
1. Определение и назначение
2. Структура (реквизиты, табличные части)
3. Программный интерфейс (методы, свойства)
4. Особенности поведения
5. Типичные ошибки
6. Best practices
7. Связи с другими объектами
8. Примеры кода (BSL)

**Cache**: `.claude/skills/1c-doc-research/cache/<тема>.md`

**Приоритет источников**: Индексированная документация (local search) > its.1c.ru > infostart.ru

---

### tech-research
| | |
|---|---|
| **Trigger** | "RAG", "embedding", "LangChain", "Qdrant", "vector search", "BM25" |
| **Тип** | Domain (5-фазный цикл) |
| **Домен** | RAG/ML/Python технологии |

**7 категорий знаний** в cache:
1. Описание технологии
2. Архитектура / принцип работы
3. API / интерфейс
4. Конфигурация
5. Производительность / бенчмарки
6. Интеграция с фреймворком
7. Ссылки на источники

**Cache**: `.claude/skills/tech-research/cache/<тема>.md`

---

### architecture-research
| | |
|---|---|
| **Trigger** | "как лучше сделать", "какой подход", "best practices", "архитектура" |
| **Тип** | Domain (3-tier: facts + ADR + procedure) |
| **Домен** | Архитектурные решения PDF Framework |

**3-уровневая структура**:
- `cache/` — факты (исследования, сравнения)
- `adr/` — Architecture Decision Records (Context → Decision → Consequences)
- `SKILL.md` — процедура принятия решений

**ADR lifecycle**: proposed → accepted → superseded → deprecated

---

### hooks-skills-mcp-triad
| | |
|---|---|
| **Trigger** | "триада", "hooks skills mcp", "архитектура хуков" |
| **Тип** | Knowledge (reference) |

Документация по архитектуре триады. Таблицы всех hooks, skills, MCP tools. Правила создания новых компонентов.

---

## Project-Specific Skills

### pdf-knowledge
| | |
|---|---|
| **Trigger** | Работа с PDF Framework |
| **Тип** | Domain (usage guide) |

Инструкции по использованию MCP tools фреймворка:
- Как индексировать PDF (`index_pdf`)
- Как искать (`search_documents`, стратегии)
- Как использовать RAG agent (`ask_question`)
- Как работать с графом знаний (`graph_query`)

---

## 5-фазный цикл (Research Skills)

```
Phase 0: Проверить кеш
         ↓ HIT → вернуть из кеша
Phase 1: Локальный поиск (MCP tool search_documents)
         ↓
Phase 2: Веб-поиск (WebSearch / WebFetch)
         ↓
Phase 3: Верификация (язык, терминология, факты)
         ↓
Phase 4: Атрибуция (каждый факт → источник + URL)
         ↓
Phase 5: Сохранение в кеш
         → Write cache/<тема>.md
         → Update _index.json
         → Hook task-enforcer блокирует выход до завершения
```

## Cache Structure

```
.claude/skills/<domain-skill>/
├── SKILL.md                     # Инструкции (5 фаз, категории)
├── cache/
│   ├── _index.json              # keywords → file mapping
│   ├── <тема-1>.md              # Структурированные знания
│   ├── <тема-2>.md
│   └── _topic_template.md       # Шаблон (опционально)
└── references/                  # Внешние документы (опционально)
```

**_index.json** формат:
```json
{
  "entries": [
    {
      "file": "справочники.md",
      "title": "Справочники в 1С",
      "keywords": ["справочник", "предопределённые элементы", "иерархия"],
      "last_verified": "2026-02-14",
      "sources_count": 3
    }
  ]
}
```

## Создание нового skill

Использовать skill `/doc-to-skill` или `/triad-factory` (Q2).

Минимальный SKILL.md:
```markdown
# Skill Name

## Когда использовать
- Триггеры...

## Процедура
1. Phase 0: проверь кеш
2. Phase 1: ...
...

## Cache
- Путь: .claude/skills/<name>/cache/
- Формат: markdown с категориями
```

## См. также

- [Triad Architecture](triad-architecture.md)
- [Hooks Reference](hooks-reference.md)
- [Ralph Wiggum](ralph-wiggum.md)
