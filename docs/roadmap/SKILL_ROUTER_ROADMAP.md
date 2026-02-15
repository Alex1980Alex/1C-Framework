# Дорожная карта: Intelligent Skill Router

**Дата создания:** 2026-02-12
**Статус:** Частично реализовано (Фазы 0, 1, 7, 9 для PDF Framework)
**Проекты:** PDF Framework + 1C-Enterprise (shared pattern)

## Проблема

При росте количества скиллов (>15-20) все загружаются в контекст LLM одновременно, создавая token bloat и снижая точность выбора. Нужна система маршрутизации: анализ промпта → загрузка только 2-5 релевантных скиллов.

**Текущее состояние:**
- PDF Framework: 12 скиллов (~4800 токенов, 2.4%) — приемлемо
- 1C-Enterprise: 29 скиллов (~12000 токенов, 6%) — нужен роутер

**Архитектура решения:** 3-уровневая

```
Level 0: Hook (UserPromptSubmit)       ~0 tokens в контексте
  │  Детектирует объект/область → определяет bundle
Level 1: Meta-Skill "object-map"       ~300 tokens
  │  Таблица маршрутизации: объект → скиллы
Level 2: Domain Skills (по запросу)    ~400-800 tokens × 3-5
  │  Загружаются ТОЛЬКО нужные
  ↓ Итого: 300 + 2000 = ~2300 tokens (1.2%)
```

---

## Фаза 0: Подготовка и проектирование

| # | Задача | Артефакт | Зависимости |
|---|--------|----------|-------------|
| 0.1 | Спроектировать JSON-схему конфига роутера | `skill-router-config.schema.json` | — |
| 0.2 | Определить формат systemMessage (шаблон) | Шаблон в коде хука | — |
| 0.3 | Определить стратегию scoring (keyword match + fuzzy) | ADR документ | — |
| 0.4 | Определить fallback при отсутствии совпадений | Решение: pass-through | — |
| 0.5 | Определить приоритет при пересечении bundles | Решение: top-2 по score | — |
| 0.6 | Ревизия существующих хуков — конфликты | Список конфликтов | 0.1 |

---

## Фаза 1: Universal Skill Router Engine

**Проект:** Shared (используется обоими проектами)
**Файл:** `.claude/hooks/skill-router.py`

| # | Задача | Детали | Строк |
|---|--------|--------|-------|
| 1.1 | Создать `skill-router.py` — каркас | BaseHook, чтение конфига, stdin parse | ~30 |
| 1.2 | Реализовать загрузку конфига | `skill-router-config.json` из текущего проекта | ~15 |
| 1.3 | Реализовать keyword matching | Lowercase prompt → scan bundles → score | ~25 |
| 1.4 | Добавить fuzzy matching (опционально) | Reuse `shared/fuzzy_match.py`, pymorphy3 лемматизация | ~20 |
| 1.5 | Реализовать bundle scoring & ranking | Score = count of matched keywords, sort desc | ~15 |
| 1.6 | Реализовать multi-bundle detection | Если 2+ bundles matched → объединить skills (dedup) | ~15 |
| 1.7 | Реализовать optional skills logic | Добавлять optional если доп. keywords совпали | ~10 |
| 1.8 | Генерация systemMessage | Шаблон: `[SKILL-ROUTER: {bundles}] Загрузи: {skills}` | ~15 |
| 1.9 | Cooldown (не спамить при каждом промпте) | `has_recent_completion()`, 3 мин | ~10 |
| 1.10 | Тест: keyword matching | echo prompt → проверить output | — |
| 1.11 | Тест: multi-bundle | "запрос для отчёта" → query + report | — |
| 1.12 | Тест: no match → pass-through | "привет" → exit 0, no output | — |
| 1.13 | Тест: fuzzy matching | "запросик" → лемма "запрос" → match | — |

**Итого:** ~155 строк кода, 4 теста

---

## Фаза 2: 1C-Enterprise — Meta-Skill (карта маршрутизации)

**Проект:** `D:\1C-Enterprise_Framework`

| # | Задача | Файл | Токены |
|---|--------|------|--------|
| 2.1 | Создать `1c-object-map/SKILL.md` | `.claude/skills/1c-object-map/SKILL.md` | ~300 |
| 2.2 | YAML frontmatter: triggers, description | Triggers: "1С", "конфигурация", "объект" | — |
| 2.3 | Таблица маршрутизации (объект → скиллы) | 9 строк: query, report, document, catalog, register, form, exchange, http, roles | — |
| 2.4 | Правило загрузки (инструкция для Claude) | "Загрузи ОБЯЗАТЕЛЬНЫЕ, по необходимости — optional" | — |
| 2.5 | Тест: Claude видит meta-skill при 1С вопросе | Manual test | — |

---

## Фаза 3: 1C-Enterprise — Domain Skills, приоритет 1 (топ-3)

Самые частые задачи: запросы, отчёты, формы.

### 3.1 Skill: `1c-query-language` (~600 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 3.1.1 | YAML frontmatter | triggers: "запрос", "выбрать", "query" |
| 3.1.2 | Синтаксис ВЫБРАТЬ | SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY |
| 3.1.3 | Соединения | INNER/LEFT/RIGHT/FULL JOIN, синтаксис ON |
| 3.1.4 | Функции | СУММА, КОЛИЧЕСТВО, МАКСИМУМ, ВЫРАЗИТЬ, ЕСТЬNULL |
| 3.1.5 | Параметры | &Параметр, синтаксис В ИЕРАРХИИ, В |
| 3.1.6 | Подзапросы | Вложенные, В (ВЫБРАТЬ...) |
| 3.1.7 | Примеры (2-3 реальных) | Типичные запросы к регистрам/справочникам |
| 3.1.8 | Anti-patterns | N+1, отсутствие индексов, звёздочка |

### 3.2 Skill: `1c-skd` (~700 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 3.2.1 | YAML frontmatter | triggers: "скд", "компоновка", "отчёт" |
| 3.2.2 | Наборы данных | Запрос, Объект, Объединение |
| 3.2.3 | Поля и ресурсы | Доступные поля, вычисляемые, ресурсы |
| 3.2.4 | Параметры СКД | Параметры данных, функциональные опции |
| 3.2.5 | Группировки и иерархия | Детальные/итоговые, иерархические |
| 3.2.6 | Условное оформление | Оформление, отборы, цвета |
| 3.2.7 | Вывод результата | ТабличныйДокумент, макеты, области |
| 3.2.8 | Программное управление | КомпоновщикНастроекКомпоновкиДанных |
| 3.2.9 | Примеры (2 реальных) | Отчёт по продажам, оборотная ведомость |

### 3.3 Skill: `1c-forms` (~600 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 3.3.1 | YAML frontmatter | triggers: "форма", "управляемая форма", "команда" |
| 3.3.2 | Архитектура управляемых форм | Клиент-сервер, директивы компиляции |
| 3.3.3 | Реквизиты формы | Основной, добавленные, привязка к данным |
| 3.3.4 | Команды формы | Стандартные, пользовательские, действие |
| 3.3.5 | Обработчики событий | ПриСозданииНаСервере, ПриОткрытии, ПередЗаписью |
| 3.3.6 | Директивы компиляции | &НаКлиенте, &НаСервере, &НаСервереБезКонтекста |
| 3.3.7 | Таблица формы | ДинамическийСписок, ТаблицаЗначений |
| 3.3.8 | Примеры (2 реальных) | Форма документа, форма обработки |

### Тесты Фазы 3

| # | Тест | Ввод | Ожидание |
|---|------|------|----------|
| 3.T1 | Загрузка query skill | "написать запрос" | `Skill("1c-query-language")` |
| 3.T2 | Загрузка skd skill | "создать отчёт с СКД" | `Skill("1c-skd")` + `Skill("1c-query-language")` |
| 3.T3 | Загрузка forms skill | "добавить команду на форму" | `Skill("1c-forms")` |
| 3.T4 | Multi-bundle | "запрос в форме отчёта" | query + skd + forms |

---

## Фаза 4: 1C-Enterprise — Domain Skills, приоритет 2

Работа с объектами конфигурации.

### 4.1 Skill: `1c-document-posting` (~500 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 4.1.1 | Модуль объекта документа | ОбработкаПроведения, ОбработкаЗаполнения |
| 4.1.2 | Движения по регистрам | Движения.ИмяРегистра.Добавить() |
| 4.1.3 | Контроль остатков | Блокировка, проверка, откат |
| 4.1.4 | Перепроведение и отмена | УдалениеДвижений, ДополнительныеСвойства |
| 4.1.5 | Примеры: проведение реализации | Полный пример с движениями |

### 4.2 Skill: `1c-registers` (~500 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 4.2.1 | Регистры накопления | Остатки vs Обороты, измерения/ресурсы |
| 4.2.2 | Регистры сведений | Периодичность, уникальность, срезы |
| 4.2.3 | Регистры бухгалтерии | Счета, субконто, корреспонденции |
| 4.2.4 | Регистры расчёта | Виды расчёта, базовые/вытесняющие |
| 4.2.5 | Запись в регистры | МенеджерЗаписи, НаборЗаписей |

### 4.3 Skill: `1c-catalogs` (~400 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 4.3.1 | Структура справочника | Реквизиты, ТЧ, иерархия, владельцы |
| 4.3.2 | Предопределённые элементы | ПолучитьПредопределённый, ссылки |
| 4.3.3 | Модуль менеджера | ОбработкаПолученияДанных, формы |
| 4.3.4 | Модуль объекта | ПередЗаписью, ПриЗаписи |

### 4.4 Skill: `1c-virtual-tables` (~500 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 4.4.1 | Остатки | Параметры VT: Период, Условие |
| 4.4.2 | Обороты | Параметры: НачалоПериода, КонецПериода |
| 4.4.3 | ОстаткиИОбороты | Комбинированная VT |
| 4.4.4 | СрезПоследних/СрезПервых | Для регистров сведений |
| 4.4.5 | Оптимизация | Передача отборов В параметры VT |

### 4.5 Skill: `1c-temp-tables` (~400 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 4.5.1 | ПОМЕСТИТЬ | Синтаксис, именование |
| 4.5.2 | Пакетные запросы | Менеджер временных таблиц |
| 4.5.3 | Индексирование | ИНДЕКСИРОВАТЬ ПО |
| 4.5.4 | Уничтожение | Автоматическое, явное |
| 4.5.5 | Паттерны использования | Промежуточные данные, порционная обработка |

### Тесты Фазы 4

| # | Тест | Ввод | Ожидание |
|---|------|------|----------|
| 4.T1 | Document posting | "проведение документа реализации" | document-posting + registers |
| 4.T2 | Registers | "регистр накопления остатки" | registers + virtual-tables |
| 4.T3 | Catalogs | "добавить реквизит в справочник" | catalogs |
| 4.T4 | Virtual tables | "виртуальная таблица остатков" | virtual-tables |
| 4.T5 | Temp tables | "пакетный запрос с временными таблицами" | query + temp-tables |

---

## Фаза 5: 1C-Enterprise — Domain Skills, приоритет 3

Специализированные области.

### 5.1 Skill: `1c-roles-rls` (~400 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 5.1.1 | Роли и права | ОбъектМетаданных → Право (Чтение, Изменение, ...) |
| 5.1.2 | RLS шаблоны | Ограничение на уровне записей |
| 5.1.3 | Шаблоны ограничений | #ПоЗначениюПараметраСеанса, #ПоОбъекту |
| 5.1.4 | Проверка прав | ПравоДоступа(), РольДоступна() |

### 5.2 Skill: `1c-exchange` (~500 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 5.2.1 | Планы обмена | Состав, регистрация изменений |
| 5.2.2 | Механизм регистрации | ОбменДанными.Загрузка, Отправители |
| 5.2.3 | XDTO | Пакеты, фабрика, сериализация |
| 5.2.4 | Конвертация данных | Правила конвертации 3.0 |

### 5.3 Skill: `1c-http-services` (~400 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 5.3.1 | HTTP-сервисы | Шаблоны URL, методы (GET/POST/PUT/DELETE) |
| 5.3.2 | Обработчики | Входящий запрос, заголовки, тело |
| 5.3.3 | JSON (де)сериализация | ЗаписьJSON, ЧтениеJSON, СериализаторXDTO |
| 5.3.4 | OData | Стандартный интерфейс, настройка |

### 5.4 Skill: `1c-common-modules` (~400 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 5.4.1 | Типы модулей | Серверный, клиентский, серверный с повторным использованием |
| 5.4.2 | Глобальный/неглобальный | Видимость, привилегированный |
| 5.4.3 | Паттерны API | Именование, параметры, возвращаемые значения |
| 5.4.4 | Серверные вызовы | Минимизация вызовов сервера |

### 5.5 Skill: `1c-report-layouts` (~400 токенов)

| # | Задача | Содержание |
|---|--------|-----------|
| 5.5.1 | Макеты | Типы: ТабличныйДокумент, ActiveDocument |
| 5.5.2 | Области макета | Именованные области, параметры |
| 5.5.3 | Вывод в документ | ВывестиГоризонтальнуюКоллекцию, Вывести |
| 5.5.4 | Печатные формы | Подключаемые, формирование |

---

## Фаза 6: 1C-Enterprise — Конфигурация и интеграция

| # | Задача | Файл | Детали |
|---|--------|------|--------|
| 6.1 | Создать `skill-router-config.json` | `.claude/skills/skill-router-config.json` | 9 bundles, ~50 keywords |
| 6.2 | Скопировать `skill-router.py` из shared | `.claude/hooks/skill-router.py` | Или symlink |
| 6.3 | Регистрация хука в settings.json | `.claude/settings.json` | UserPromptSubmit, timeout 5s |
| 6.4 | Интеграция с `1c-task-detector.py` | Решить: merge или chain | Chain: detector → router |
| 6.5 | Приоритет хуков | detector first (task type), router second (skills) | Порядок в массиве hooks |
| 6.6 | End-to-end тест: простой запрос | "напиши запрос" | 1c-query-language loaded |
| 6.7 | End-to-end тест: сложная задача | "отчёт с пакетным запросом и VT" | skd + query + temp-tables + virtual-tables |
| 6.8 | End-to-end тест: документ с проведением | "проведение ПоступлениеТоваров" | document-posting + registers + forms |
| 6.9 | Замер token overhead | До и после router | Ожидание: с 12K → 2-3K |

---

## Фаза 7: PDF Framework — Конфигурация роутера

**Проект:** `D:\1С-Framework`

| # | Задача | Файл | Детали |
|---|--------|------|--------|
| 7.1 | Создать `skill-router-config.json` | `.claude/skills/skill-router-config.json` | 7 bundles для текущих 12 скиллов |
| 7.2 | Bundle: search | keywords: поиск, search, найди, hybrid, bm25 → pdf-search | — |
| 7.3 | Bundle: research-1c | keywords: 1С, справочник, документ, регистр → 1c-doc-research | — |
| 7.4 | Bundle: research-tech | keywords: rag, embedding, qdrant, langchain → tech-research | — |
| 7.5 | Bundle: architecture | keywords: архитектура, подход, паттерн → architecture-research | — |
| 7.6 | Bundle: infrastructure | keywords: hook, skill, mcp, триада → hooks-skills-mcp-triad, triad-factory | — |
| 7.7 | Bundle: creation | keywords: создай hook, новый скилл → create-hook, doc-to-skill | — |
| 7.8 | Bundle: evaluation | keywords: brainstorm, оценка, подходы → task-evaluation | — |
| 7.9 | Скопировать `skill-router.py` | `.claude/hooks/skill-router.py` | Из shared или создать |
| 7.10 | Регистрация хука в settings.json | `.claude/settings.json` → UserPromptSubmit | +1 hook |
| 7.11 | Проверить конфликт с `research-task-detector` | Оба на UserPromptSubmit | Chain: detector → router |
| 7.12 | Тест: "поиск по справочникам" | → pdf-search + 1c-doc-research | — |
| 7.13 | Тест: "создай hook для кеширования" | → create-hook + hooks-skills-mcp-triad | — |

---

## Фаза 8: PDF Framework — Будущие Domain Skills

Создаются **по мере необходимости**, не упреждающе.

| # | Skill | Триггер создания | Содержание |
|---|-------|-----------------|-----------|
| 8.1 | `search-pipeline-debug` | При частых вопросах "почему поиск не находит" | Pipeline stages, score debug, BM25 vs vector |
| 8.2 | `indexing-pipeline` | При работе с новыми PDF | Loaders, splitters, page_offsets, batch |
| 8.3 | `graph-operations` | При вопросах по графу | LightRAG, GraphRAG, entity extraction |
| 8.4 | `evaluation-benchmark` | При оценке качества | RAGAS, метрики, regression tests |
| 8.5 | `embedding-models` | При смене/сравнении моделей | E5, BGE-M3, Jina-v3, ONNX backend |
| 8.6 | `qdrant-operations` | При миграциях/настройке | Collections, sparse vectors, snapshots |
| 8.7 | `agent-orchestration` | При работе с агентами | RAG agent, multi-agent, LangGraph nodes |
| 8.8 | `prompt-engineering` | При оптимизации промптов | DSPy modules, A/B testing |
| 8.9 | `deployment` | При деплое | Docker compose, health checks, monitoring |

Каждый skill: **30-60 мин на создание**, добавляется в `skill-router-config.json` одной записью.

---

## Фаза 9: MCP Per-Project (параллельно)

| # | Задача | Проект | Детали |
|---|--------|--------|--------|
| 9.1 | Создать `.mcp.json` | PDF Framework | 2 сервера: brave-search, context7 |
| 9.2 | Создать `.mcp.json` | 1C-Enterprise | 7 серверов: 1c-*, serena, jira, etc. |
| 9.3 | User-level MCP | `~/.claude.json` | 2-3 утилиты: github, memory |
| 9.4 | Миграция паролей в env vars | PowerShell | JIRA_PASSWORD, NEO4J_PASSWORD, MCP_ONEC_PASSWORD |
| 9.5 | Удалить избыточные серверы из Desktop | `claude_desktop_config.json` | 10 серверов (ripgrep, grep, clipboard, zip, ...) |
| 9.6 | Добавить permissions в settings.json | Оба проекта | `MCP(server:*)` allow/deny rules |
| 9.7 | Тест: Claude Code видит только нужные MCP | Оба проекта | `claude mcp list` в каждом |

---

## Фаза 10: Мониторинг и оптимизация

| # | Задача | Как | Когда |
|---|--------|-----|-------|
| 10.1 | Логирование skill-router | Hook пишет в `data/skill-router.log` | С Фазы 1 |
| 10.2 | Статистика: какие bundles срабатывают чаще | Парсинг лога | Через 2 недели |
| 10.3 | Анализ: false positives (лишние скиллы) | Ручная проверка | Через 2 недели |
| 10.4 | Анализ: false negatives (нужный скилл не загружен) | User feedback | Итеративно |
| 10.5 | Оптимизация keywords | Добавить/убрать по статистике | Итеративно |
| 10.6 | Оптимизация bundles | Разделить/объединить | Итеративно |
| 10.7 | Token budget report | Подсчёт tokens per session | Ежемесячно |

---

## Сводка по фазам

| Фаза | Что | Проект | Усилия | Приоритет |
|------|-----|--------|--------|-----------|
| Фаза | Что | Проект | Усилия | Приоритет | Статус |
|------|-----|--------|--------|-----------|--------|
| **0** | Проектирование | Оба | 1-2 часа | P0 | **DONE** (PDF) |
| **1** | Universal Router Engine | Shared | 3-4 часа | P0 | **DONE** (skill-router.py) |
| **2** | 1C Meta-Skill | 1C-Enterprise | 30 мин | P0 | Pending |
| **3** | 1C Top-3 Skills (query, skd, forms) | 1C-Enterprise | 4-6 часов | P1 | Pending |
| **4** | 1C Priority-2 Skills (5 шт) | 1C-Enterprise | 5-7 часов | P1 | Pending |
| **5** | 1C Priority-3 Skills (5 шт) | 1C-Enterprise | 4-5 часов | P2 | Pending |
| **6** | 1C Integration & Testing | 1C-Enterprise | 2-3 часа | P1 | Pending |
| **7** | PDF Config & Testing | PDF Framework | 2-3 часа | P1 | **DONE** (7 bundles, 5 tests) |
| **8** | PDF Future Skills | PDF Framework | По запросу | P3 | On-demand |
| **9** | MCP Per-Project | Оба | 2-3 часа | P1 | **DONE** (PDF .mcp.json) |
| **10** | Мониторинг | Оба | Итеративно | P2 | Pending |

## Порядок выполнения

```
Фаза 0 → Фаза 1 → ┬── Фаза 2 → Фаза 3 → Фаза 4 → Фаза 6
                    │                                    ↓
                    ├── Фаза 7 (PDF config)         Фаза 5
                    │                                    ↓
                    └── Фаза 9 (MCP, параллельно)   Фаза 10
```

**Минимальный viable набор:** Фазы 0+1+2+3+6+7

## Пример конфига для 1С (skill-router-config.json)

```json
{
  "bundles": {
    "query": {
      "keywords": ["запрос", "query", "выбрать", "соединение", "where", "группировка"],
      "skills": ["1c-query-language", "1c-temp-tables"],
      "optional": ["1c-virtual-tables"]
    },
    "report": {
      "keywords": ["отчёт", "report", "скд", "компоновка", "макет отчёта"],
      "skills": ["1c-skd", "1c-query-language"],
      "optional": ["1c-report-layouts"]
    },
    "document": {
      "keywords": ["документ", "проведение", "движения", "document"],
      "skills": ["1c-document-posting", "1c-registers"],
      "optional": ["1c-forms"]
    },
    "catalog": {
      "keywords": ["справочник", "catalog", "иерархия", "реквизит справочника"],
      "skills": ["1c-catalogs"],
      "optional": ["1c-forms"]
    },
    "register": {
      "keywords": ["регистр", "накопления", "сведений", "бухгалтерии"],
      "skills": ["1c-registers"],
      "optional": ["1c-virtual-tables"]
    },
    "form": {
      "keywords": ["форма", "команда формы", "реквизит формы", "обработчик"],
      "skills": ["1c-forms"],
      "optional": []
    },
    "exchange": {
      "keywords": ["обмен", "синхронизация", "xdto", "план обмена"],
      "skills": ["1c-exchange"],
      "optional": []
    },
    "http": {
      "keywords": ["http", "rest", "odata", "web-сервис", "api"],
      "skills": ["1c-http-services"],
      "optional": []
    },
    "roles": {
      "keywords": ["роль", "право", "rls", "доступ"],
      "skills": ["1c-roles-rls"],
      "optional": []
    }
  }
}
```

## Пример конфига для PDF Framework

```json
{
  "bundles": {
    "search": {
      "keywords": ["поиск", "search", "найди", "запрос к базе", "hybrid", "bm25"],
      "skills": ["pdf-search"],
      "optional": []
    },
    "research-1c": {
      "keywords": ["1с", "1c", "справочник", "документ 1с", "регистр"],
      "skills": ["1c-doc-research"],
      "optional": []
    },
    "research-tech": {
      "keywords": ["rag", "embedding", "qdrant", "langchain", "reranking", "bm25"],
      "skills": ["tech-research"],
      "optional": []
    },
    "architecture": {
      "keywords": ["архитектура", "подход", "паттерн", "best practice", "как лучше"],
      "skills": ["architecture-research"],
      "optional": []
    },
    "infrastructure": {
      "keywords": ["hook", "skill", "mcp", "триада", "triad", "factory"],
      "skills": ["hooks-skills-mcp-triad"],
      "optional": ["triad-factory", "create-hook"]
    },
    "creation": {
      "keywords": ["создай hook", "новый скилл", "новый хук", "create"],
      "skills": ["create-hook"],
      "optional": ["doc-to-skill"]
    },
    "evaluation": {
      "keywords": ["brainstorm", "оценка подходов", "сравни варианты", "предложи"],
      "skills": ["task-evaluation"],
      "optional": []
    }
  }
}
```
