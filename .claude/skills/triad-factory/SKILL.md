---
name: triad-factory
description: "Универсальный шаблон Фабрики триады. Используй когда нужно создать новый компонент (hook, skill, MCP tool, домен). Триггеры: 'фабрика', 'factory', 'создать компонент', 'новый домен', 'Q1-Q5', 'классификация решения', 'формула триады'."
---

# Фабрика Триады — порождающий паттерн (Abstract Factory + Builder)

**Тип:** Порождающий (Creational)
**Этот файл — программа.** Алгоритм, который превращает решение в работающую автоматизацию. Не привязан к конкретному проекту — описывает общий механизм создания компонентов триады.

Текущее состояние компонентов (что уже существует) — см. skill `hooks-skills-mcp-triad`.

---

## Назначение (Intent)

Предоставить интерфейс для создания семейств связанных компонентов автоматизации (Hook, Skill, MCP, Cache, ADR, Enforcer) без привязки к конкретным реализациям. Классификация Q1-Q6 определяет формулу — какие продукты порождает фабрика.

---

## Мотивация (Motivation)

**Проблема:** Решения, принятые в чате, теряются. Claude даёт ответ → пользователь доволен → следующая сессия не знает о решении. Знания не накапливаются, автоматизация не строится, одни и те же вопросы обсуждаются повторно.

**Без паттерна:**
```
Сессия 1: "Какой фреймворк использовать?" → ответ в чате → потеряно
Сессия 2: "Какой фреймворк использовать?" → тот же вопрос заново
Сессия 3: "Обработай 1С-вопрос" → забыли использовать скилл → неполный ответ
```

**С паттерном:**
```
Сессия 1: Вопрос → Фабрика (Q1-Q6) → Hook (auto-detect) + Skill (procedure) + Cache (facts) + ADR (decision)
Сессия 2: Тот же вопрос → Hook срабатывает → Skill загружает Cache → мгновенный ответ
Сессия 3: 1С-вопрос → Hook автоматически роутит → Skill + MCP → полный ответ с атрибуцией
```

**Ключевое правило:** Если в разговоре принято решение — оно ДОЛЖНО стать артефактом. Если решение осталось только в чате — оно потеряно.

---

## Когда применять (Applicability)

| Ситуация | Применять? | Формула |
|----------|-----------|---------|
| Новая предметная область знаний | Да | Hook + Skill + MCP + Cache + Enforcer (+ ADR если Q6) |
| Архитектурное решение по фреймворку | Да | Skill + Cache + ADR |
| Автоматизация повторяющегося действия | Да | Hook (+ Skill если нужна процедура) |
| Однократная задача (баг, фикс) | Нет | MEMORY-only или ничего |
| Информационный вопрос без последствий | Нет | Прямой ответ |

---

## Структура (Structure) — Принцип триады

```
СОБЫТИЕ (что произошло?)  →  ЗНАНИЕ (что делать?)  →  ИНСТРУМЕНТ (чем сделать?)
```

| Компонент | Роль | Вопрос | Формат |
|-----------|------|--------|--------|
| **Hooks** | Событие в чате → триггер | КОГДА делать? | Python скрипты (.py) |
| **Skills** | Процедурное знание | КАК / ЧТО делать? | Markdown (SKILL.md) |
| **Инструменты** | Нативные (Write/Edit) + MCP | ЧЕМ делать? | Claude Code tools + JSON-RPC серверы |

Hook срабатывает **ВНУТРИ** разговора — ловит что пользователь написал и превращает в действие. Хук = событие чата, закодированное в `.py`.

---

## Участники (Participants) — ФАБРИКА

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
| Q6 | Нужно **фиксировать решения** (не только факты)? | → **ADR** нужен (в Skill) |

**Примеры классификации:**

```
"Исследование новой технологии" →
  Q1=Да (при вопросе автоматически роутить) → Hook
  Q2=Да (5-фазный research workflow) → Skill
  Q3=Да (WebSearch, MCP search) → MCP
  Q4=Да (кеш знаний) → Cache
  Q5=Да (обязательно кешировать) → Enforcer
  Q6=Нет (факты, не решения) → —
  ФОРМУЛА: Hook + Skill + MCP + Cache + Enforcer

"Архитектурное решение по фреймворку" →
  Q1=Да (при вопросе автоматически роутить) → Hook
  Q2=Да (6-фазный research + решение) → Skill
  Q3=Да (WebSearch, MCP search) → MCP
  Q4=Да (кеш фактов) → Cache
  Q5=Да (обязательно кешировать) → Enforcer
  Q6=Да (фиксировать решение) → ADR
  ФОРМУЛА: Hook + Skill + MCP + Cache + Enforcer + ADR

"Шаблон создания хуков" →
  Q1=Нет (только по запросу) → —
  Q2=Да (шаблон, чеклист) → Skill
  Q3=Нет (работа с файлами) → —
  Q4=Нет → —
  Q5=Нет → —
  Q6=Нет → —
  ФОРМУЛА: Skill-only

"Оптимизация параметров поиска" →
  Q1=Да (перед каждым вызовом API) → Hook
  Q2=Нет (простая проверка) → —
  Q3=Нет → —
  Q4=Нет → —
  Q5=Нет → —
  Q6=Нет → —
  ФОРМУЛА: Hook-only
```

---

### ШАГ 2: ФОРМУЛА

По ответам на Q1-Q5 определяется формула — комбинация компонентов:

| Формула | Когда | Создаваемые файлы |
|---------|-------|--------------------|
| **Hook + Skill + MCP + Cache + ADR + Enforcer** | Домен знаний + решения | skill/, cache/, adr/, detector, reminder, enforcer, MCP tool |
| **Hook + Skill + MCP + Cache + Enforcer** | Домен знаний (только факты) | skill/, cache/, detector, reminder, enforcer, MCP tool |
| **Skill + Cache + ADR** | Решения по запросу (без автоматики) | SKILL.md, cache/, adr/ |
| **Hook + Skill + MCP** | Автоматизация + инструмент | hook.py, SKILL.md, MCP tool |
| **Hook + Skill** | Автоматизация workflow | hook.py, SKILL.md (или фаза в существующем) |
| **Skill + MCP** | Инструмент по запросу | SKILL.md, MCP tool |
| **Skill + Cache** | Доменное знание без решений | SKILL.md, cache/ |
| **Skill-only** | Процедура / шаблон | SKILL.md |
| **Hook-only** | Простой триггер / валидация | hook.py |
| **MEMORY-only** | Баг / workaround / факт | MEMORY.md запись |

**Паттерн 3-tier Knowledge** (структурный):
- Q4=Да + Q6=Нет → **cache/** only (факты, переиспользуемые)
- Q4=Да + Q6=Да → **cache/** + **adr/** (факты отделены от решений)
- Q6=Да без Q4 → НЕ бывает (решение всегда основано на исследовании → нужен cache)

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

#### Если нужен ADR (Q6=Да):

ADR — **структурный паттерн** отделения решений от фактов. Факты (cache/) переиспользуемы, решения (adr/) контекстны и версионируемы.

```
Директория: .claude/skills/<domain>-research/adr/
  → _index.json (реестр: id, file, title, status, date, research link)
  → NNN-<название>.md (ADR формат)
```

**Шаблон ADR:**
```markdown
# ADR-NNN: [Название решения]

**Дата:** YYYY-MM-DD
**Статус:** proposed | accepted | superseded | deprecated
**Исследование:** [ссылка на cache-файл с фактами]

## Контекст
[Почему возник вопрос]

## Решение
[Что решили + обоснование с атрибуцией [docs/web/exp/own]]

## Последствия
### Положительные / Отрицательные

## Альтернативы
[Что рассматривали и почему отклонили]

## Связанные файлы
[Какие файлы фреймворка затрагивает]
```

**Жизненный цикл ADR:** proposed → accepted → superseded | deprecated

**Критерий Q6:** Отвечай "Да" если исследование приводит к выбору (framework A vs B, подход X vs Y, использовать или нет). Отвечай "Нет" если исследование чисто информационное (как работает X, что такое Y).

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
| Cache | Инициализировать `cache/_index.json`, добавить инвалидацию |
| ADR | Инициализировать `adr/_index.json`, связать с cache через `research` поле |
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
| Cache | Проверить `cache/_index.json` обновился после исследования |
| ADR | Проверить `adr/_index.json` содержит запись, ADR ссылается на cache-файл |
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
  Q6=? (фиксировать решения?) → зависит от домена

ШАГ 2: ФОРМУЛА
  Q6=Нет → Hook + Skill + MCP + Cache + Enforcer
  Q6=Да  → Hook + Skill + MCP + Cache + Enforcer + ADR

ШАГ 3: ГЕНЕРАЦИЯ
  Skill:  skills/<domain>-research/SKILL.md (5-6 фаз, N категорий)
  Cache:  skills/<domain>-research/cache/_topic_template.md
          skills/<domain>-research/cache/_index.json
  ADR:    skills/<domain>-research/adr/_index.json (если Q6=Да)
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

- [ ] Skill: `skills/<domain>-research/SKILL.md` создан (5-6 фаз)
- [ ] Skill: `cache/_topic_template.md` создан (категории)
- [ ] Skill: `cache/_index.json` создан (пустой)
- [ ] Q6: если Да → `adr/_index.json` создан, Фаза 6 в SKILL.md
- [ ] Hook: `DOMAIN_TERMS` добавлен в `research-task-detector.py`
- [ ] Hook: `DOMAIN_SIGNALS` добавлен в `knowledge-cache-reminder.py`
- [ ] Реестр: обновлена таблица Skills в `hooks-skills-mcp-triad`
- [ ] CLAUDE.md: обновлён раздел Knowledge Cache
- [ ] MEMORY.md: добавлена запись о новом домене

---

## Примеры готовых формул (справочник)

| Решение | Формула | Артефакты |
|---------|---------|-----------|
| Домен знаний + решения | Hook+Skill+MCP+Cache+ADR+Enforcer | SKILL.md, cache/, adr/, TERMS в детекторе |
| Домен знаний (только факты) | Hook+Skill+MCP+Cache+Enforcer | SKILL.md, cache/, TERMS в детекторе |
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

## Последствия (Consequences)

### Положительные

1. **Знания не теряются** — каждое решение из чата становится артефактом (файлом)
2. **Самоусиливающийся цикл** — работа → артефакт → следующая сессия использует его → лучшая работа → новый артефакт
3. **Единообразие** — все компоненты создаются через один процесс (Q1-Q6 → формула → генерация)
4. **Модульность** — компоненты слабо связаны (Hook → systemMessage → Claude → Skill), легко добавлять/удалять
5. **Graceful degradation** — сбой хука не ломает workflow (исключение → pass through)
6. **Разделение ответственности** — Hook (когда) / Skill (как) / MCP (чем) / Cache (факты) / ADR (решения)

### Отрицательные

1. **Overhead на простых задачах** — Q1-Q6 для однострочного фикса = лишний шаг (используй MEMORY-only)
2. **Сложность навигации** — 7+ hooks, 8+ skills, множество файлов — нужен реестр (`hooks-skills-mcp-triad`)
3. **Зависимость от stdin/stdout JSON** — хуки привязаны к Claude Code protocol, не портируемы
4. **Timeout-ограничения** — хуки должны выполняться за 3-5s, нельзя делать тяжёлые вычисления
5. **Windows-специфика** — абсолютные пути в settings.json, UTF-8 фикс через `sys.stdin.buffer`

---

## Принципы (Design Decisions)

1. **Hooks легковесны** — keyword matching, file read, не тяжёлые вычисления (3-5s timeout)
2. **Skills информативны** — полные инструкции, шаблоны, примеры, антипаттерны
3. **MCP мощные** — тяжёлая работа (поиск, индексация, RAG) в MCP серверах
4. **Graceful degradation** — хуки никогда не ломают workflow (исключение → pass through)
5. **Separate state** — hook-todos.json отделён от Claude TodoWrite (нет race conditions)
6. **Фабрика как процесс** — каждое решение проходит через ШАГ 1-6, а не ad-hoc
7. **Знание и программа раздельны** — шаблон (этот файл) не зависит от реализации (`hooks-skills-mcp-triad`)
8. **Факты и решения раздельны** — cache/ (переиспользуемые данные) отделён от adr/ (контекстные решения)

---

## Связанные паттерны (Related Patterns)

### GoF-паттерны в составе

| Паттерн | Русское название | Где используется | Как |
|---------|-----------------|-----------------|-----|
| **Abstract Factory** | Абстрактная фабрика | Фабрика целиком | Q1-Q6 → формула → семейство продуктов (Hook + Skill + Cache + ADR + ...) |
| **Builder** | Строитель | ШАГ 1-5 | Пошаговая конструкция: классификация → формула → генерация → связывание → верификация |
| **Strategy** | Стратегия | Hooks (PreToolUse, PostToolUse, Stop) | Подстановка разных обработчиков событий через matcher |
| **Chain of Responsibility** | Цепочка обязанностей | Hook pipeline | detector → reminder → enforcer — каждый обрабатывает своё или пропускает |
| **Observer** | Наблюдатель | Claude Code Events | Hooks подписаны на события (UserPromptSubmit, PostToolUse, Stop) |
| **Template Method** | Шаблонный метод | BaseHook.run() | Фиксированный алгоритм: read stdin → execute() → emit stdout. Подклассы определяют execute() |
| **Composite** | Компоновщик | SuperComponent / SearchManager | Pipeline из компонентов, каждый обрабатывает свою часть |

### Подпаттерны триады

| Паттерн | Русское название | Тип | Где |
|---------|-----------------|-----|-----|
| **3-tier Knowledge** | Трёхуровневые знания | Структурный | cache/ (факты) + adr/ (решения) + SKILL.md (процедура). Q4+Q6 |
| **Enforcer Loop** | Цикл принуждения | Поведенческий | PostToolUse → add_task() → hook-todos.json → Stop → check pending → BLOCK/ALLOW |
| **Skill Routing** | Маршрутизация скиллов | Поведенческий | UserPromptSubmit → keyword scoring → systemMessage → Claude читает Skill |
| **Domain Extension** | Расширение домена | Порождающий | Добавление нового домена: TERMS в detector + SIGNALS в reminder + Skill + Cache |

### Антипаттерны

| Антипаттерн | Почему плохо | Правильно |
|-------------|-------------|-----------|
| Решение без артефакта | Потеряется в следующей сессии | Минимум MEMORY-only, лучше Cache/ADR |
| Hook вызывает тот же инструмент | Зацикливание (PreToolUse:Read → Read) | Другой инструмент или systemMessage |
| Выводы в cache-файле | Нельзя переиспользовать факты для другого решения | Факты в cache/, решения в adr/ |
| Ad-hoc компонент без Фабрики | Не связан с реестром, не верифицирован | Всегда через Q1-Q6 → ШАГ 1-5 |
| Тяжёлые вычисления в хуке | Timeout 3-5s | Только keyword matching, file read |
