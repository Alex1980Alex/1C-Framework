---
name: triad-factory
description: "Универсальный шаблон Фабрики триады. Используй когда нужно создать новый компонент (hook, skill, MCP tool, домен). Триггеры: 'фабрика', 'factory', 'создать компонент', 'новый домен', 'Q1-Q5', 'классификация решения', 'формула триады'."
---

# Фабрика Триады — универсальный шаблон

**Этот файл — программа.** Алгоритм, который превращает решение в работающую автоматизацию. Не привязан к конкретному проекту — описывает общий механизм создания компонентов триады.

Текущее состояние компонентов (что уже существует) — см. skill `hooks-skills-mcp-triad`.

---

## Принцип триады

```
СОБЫТИЕ (что произошло?)  →  ЗНАНИЕ (что делать?)  →  ИНСТРУМЕНТ (чем сделать?)
```

| Компонент | Роль | Вопрос | Формат |
|-----------|------|--------|--------|
| **Hooks** | Событие в чате → триггер | КОГДА делать? | Python скрипты (.py) |
| **Skills** | Процедурное знание | КАК / ЧТО делать? | Markdown (SKILL.md) |
| **Инструменты** | Нативные (Write/Edit) + MCP | ЧЕМ делать? | Claude Code tools + JSON-RPC серверы |

Hook — это **не абстрактная автоматизация рядом с чатом**. Хук срабатывает **ВНУТРИ** разговора. Он ловит то, что пользователь написал, и превращает это в действие. Хук = событие чата, закодированное в `.py`.

**Ключевое правило:** Если в разговоре принято решение — оно ДОЛЖНО стать артефактом. Если решение осталось только в чате — оно потеряно.

---

## ФАБРИКА — главный процесс

**Любое новое решение, задача или требование проходит через эту фабрику.** Результат — набор артефактов (hooks, skills, MCP tools), которые система использует автоматически.

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
- Таблица Hooks в skill `hooks-skills-mcp-triad`
- Таблица Skills в skill `hooks-skills-mcp-triad`
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

## Сквозной пример: Фабрика порождает домен

Пошаговое применение фабрики к реальному решению:

```
ВХОД: "Нужен отдельный домен знаний для новой области"

ШАГ 1: КЛАССИФИКАЦИЯ
  Q1=Да (автоматически роутить при вопросе) → Hook
  Q2=Да (5-фазный research) → Skill
  Q3=Да (WebSearch, MCP search) → MCP
  Q4=Да (кеш знаний) → Cache
  Q5=Да (обязательно кешировать) → Enforcer

ШАГ 2: ФОРМУЛА = Hook + Skill + MCP + Cache + Enforcer

ШАГ 3: ГЕНЕРАЦИЯ
  Skill:  skills/<domain>-research/SKILL.md (5 фаз, N категорий)
  Cache:  skills/<domain>-research/cache/_topic_template.md
          skills/<domain>-research/cache/_index.json
  Hook:   DOMAIN_TERMS добавлен в research-task-detector.py
          DOMAIN_SIGNALS добавлен в knowledge-cache-reminder.py
  MCP:    search_documents уже есть (переиспользование)
  Enforcer: task-enforcer.py уже есть (переиспользование)

ШАГ 4: СВЯЗЫВАНИЕ
  detector → systemMessage "используй <domain>-research"
  reminder → add_task("Сохрани в <domain>-кеш")
  enforcer → читает hook-todos.json (без изменений)
  Обновлены: hooks-skills-mcp-triad, CLAUDE.md, MEMORY.md

ШАГ 5: ВЕРИФИКАЦИЯ
  echo '{"prompt":"вопрос по домену"}' | python research-task-detector.py
  → {"continue":true,"systemMessage":"[DOMAIN-RESEARCH-DETECTED]..."}  ✓
```

---

## Паттерн: Расширение домена

Когда появляется **новая предметная область** (домен), нужно обновить хуки роутинга:

### Анализ домена

| Критерий | Выделенный | Общий (расширить существующий) |
|----------|-----------|-------------------------------|
| Уникальные источники (URL) | Свои авторитетные сайты | Пересекается с имеющимися |
| Уникальная терминология | Не пересекается | Общие термины |
| Уникальный workflow | Свои этапы | Стандартный 5-фазный research |

### Если НОВЫЙ домен — создать skill + обновить хуки

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

### Если расширение СУЩЕСТВУЮЩЕГО — добавить термины

```python
# Пример: добавить новый фреймворк в tech-research
TECH_TERMS = [
    ...,
    "new_framework", "new_tool",  # ← новые
]
```

### Чеклист расширения домена

- [ ] Skill: `skills/<domain>-research/SKILL.md` создан (5 фаз)
- [ ] Skill: `cache/_topic_template.md` создан (категории)
- [ ] Skill: `cache/_index.json` создан (пустой)
- [ ] Hook: `DOMAIN_TERMS` добавлен в `research-task-detector.py`
- [ ] Hook: `DOMAIN_SIGNALS` добавлен в `knowledge-cache-reminder.py`
- [ ] Реестр: обновлена таблица Skills в `hooks-skills-mcp-triad`
- [ ] CLAUDE.md: обновлён раздел Knowledge Cache
- [ ] MEMORY.md: добавлена запись о новом домене

---

## Примеры готовых формул (справочник)

| Решение | Формула | Артефакты |
|---------|---------|-----------|
| Новый домен знаний | Hook+Skill+MCP+Cache+Enforcer | SKILL.md, cache/, TERMS в детекторе |
| Автоматизация кеширования | Hook+Hook+Skill | reminder.py, enforcer.py, Фаза 5 |
| Захват решений из чата | Hook+Skill | meta-router.py, triad/factory skill |
| Документирование workflow | Skill-only | doc-to-skill/SKILL.md |
| Простая валидация | Hook-only | validator.py |
| Баг/workaround | MEMORY-only | MEMORY.md запись |

---

## Протокол hook stdin/stdout

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

---

## Принципы

1. **Hooks легковесны** — keyword matching, file read, не тяжёлые вычисления (3-5s timeout)
2. **Skills информативны** — полные инструкции, шаблоны, примеры, антипаттерны
3. **MCP мощные** — тяжёлая работа (поиск, индексация, RAG) в MCP серверах
4. **Graceful degradation** — хуки никогда не ломают workflow (исключение → pass through)
5. **Separate state** — hook-todos.json отделён от Claude TodoWrite (нет race conditions)
6. **Фабрика как процесс** — каждое решение проходит через ШАГ 1-5, а не ad-hoc
7. **Знание и программа раздельны** — шаблон (этот файл) не зависит от реализации (`hooks-skills-mcp-triad`)
