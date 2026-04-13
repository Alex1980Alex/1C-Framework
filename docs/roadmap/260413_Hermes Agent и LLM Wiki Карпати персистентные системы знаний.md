# Дорожная карта: Hermes Agent / LLM Wiki Карпаты → PDF Framework

**Версия:** 1.1
**Дата:** 2026-04-13
**Статус:** draft
**Автор:** Claude Opus 4.6
**Исследование:** [hermes-llm-wiki-github-landscape.md](../../.claude/skills/architecture-research/cache/hermes-llm-wiki-github-landscape.md)

---

## Контекст и мотивация

Фреймворк PDF Vector & Graph достиг зрелости инфраструктуры: 75 скиллов, 17 MCP-серверов, 13 хуков, 4 системы памяти, LangGraph-агенты с многослойным роутингом. Однако знания распределены по множеству форматов и локаций — cache-директории в скиллах, плоский MEMORY.md, Qdrant-коллекции, YAML-файлы конфигурации. Это создаёт фрагментацию: агент не может эффективно компаундировать знания между сессиями.

Архитектурное видение "Hermes Agent / LLM Wiki Карпаты" предлагает решение — три слоя организации знаний (raw sources, markdown wiki, schema) с агентом-библиотекарем, который активно поддерживает целостность базы знаний. Это сдвиг парадигмы от пассивного RAG (запрос → чанки) к активному управлению знаниями (документ → структурированные сущности → связи → компаундинг).

Данная дорожная карта формализует переход от текущего состояния к целевому. Ключевой принцип — brownfield-совместимость: все новые компоненты надстраиваются поверх существующих без breaking changes. Каждая фаза независима и доставляет ценность сама по себе, но вместе они образуют систему, где знания экспоненциально нарастаются с каждой обработанной сессией.

Мотивация приоритизации: низкостоимостные компоненты с высокой ценностью (Obsidian vault, MPF helper, schema/log) идут первыми, создавая фундамент для более сложных pipeline (PDF → wiki pages). Sandbox и OAuth отложены как необязательные для текущего single-user режима.

---

## Архитектурные столпы

### Столп 1: Markdown Prompting Framework (MPF)

Структурированные промпты с секциями ask/context/constraints/example. Демонстрирует +7.2% точности JSON-извлечения (81.2% vs 74%) на GPT-4.

| Аспект | Текущее состояние | Целевое состояние |
|--------|-------------------|-------------------|
| Формат промптов | f-string в src/pdf_framework/agents/ | MPF helper с валидацией структуры |
| Шаблоны | Разбросаны по коду | Централизованные templates/ |
| Тестирование | Нет | Eval suite для промптов |

### Столп 2: skill.md — процедурная память

Progressive disclosure (3 уровня детализации), negative boundaries (anti_triggers) в description.

| Аспект | Текущее состояние | Целевое состояние |
|--------|-------------------|-------------------|
| Формат скиллов | 75 YAML+MD файлов | То же + anti_triggers в frontmatter |
| Роутинг | 4 слоя (phrase → fuzzy → TF-IDF → semantic) | + anti_trigger фильтрация |
| Progressive disclosure | Частично (контент скиллов) | Формализовано в schema |

### Столп 3: MCP + Sandbox + Human-in-the-loop

Изолированное исполнение кода, авторизация с TTL, явное подтверждение действий.

| Аспект | Текущее состояние | Целевое состояние |
|--------|-------------------|-------------------|
| MCP серверы | 17 серверов в .mcp.json | + Obsidian MCP |
| Sandbox | Нет | E2B SDK интеграция |
| Авторизация | Local-only | OAuth 2.1 с TTL (deferred) |

### Столп 4: LLM Wiki (Карпаты)

Агент-библиотекарь, 3 слоя знаний, index.md + log.md, Obsidian как IDE, компаундинг.

| Аспект | Текущее состояние | Целевое состояние |
|--------|-------------------|-------------------|
| Wiki-слой | Нет (только cache/ мини-wiki) | docs/ + memory/ как Obsidian vault |
| Библиотекарь | Нет | Auto-librarian hook |
| PDF pipeline | Chunk-based RAG | + Structured wiki pages pipeline |
| Хронология | Нет | memory/log.md |
| Schema | Нет | memory/SCHEMA.md |

---

## Принципы реализации

1. **Brownfield-совместимость.** Все новые компоненты работают поверх существующих. Никаких переписываний — только надстройки и расширения.

2. **Triad-pattern соответствие.** Каждый новый компонент маппится на Hooks (WHEN) + Skills (HOW) + MCP (WITH WHAT). Auto-librarian = hook + skill + MCP-вызовы. Wiki pipeline = skill + MCP + agents.

3. **Инкрементальность.** Каждая фаза доставляет измеримую ценность независимо. Можно остановиться после любой фазы и иметь работающую систему.

4. **No breaking changes.** Существующие скиллы, хуки, MCP-серверы продолжают работать без модификаций. Новые поля в frontmatter опциональны.

5. **Wiki-as-code.** Wiki-страницы версионируются в git, проходят code review, имеют schema валидацию. Знания — это код.

6. **Compound knowledge.** Каждая обработанная сессия увеличивает плотность связей в wiki. Метрика: knowledge compound rate.

7. **Fail-safe defaults.** При ошибке в новых компонентах (librarian, wiki pipeline) система деградирует к текущему поведению, не ломается.

---

## Фазы реализации

### Сводная таблица фаз

| Фаза | Название | Приоритет | Трудозатраты | Зависимости |
|------|----------|-----------|--------------|-------------|
| 1 | Obsidian Vault Integration | P0 | S | Нет |
| 2 | Foundation — MPF + anti_triggers + log/schema | P1 | M | Нет |
| 3 | Auto-Librarian Hook | P1 | M | Фаза 1 |
| 4 | PDF → Structured Wiki Pages | P2 | XL | Фазы 1, 2 |
| 5 | Sandbox для агентов | P3 | M | Фаза 2 |
| 6 | Defer — OAuth 2.1 MCP TTL | P3 | L | Фаза 5 |

---

### Фаза 1: Obsidian Vault Integration

**Цель:** Создать единый Obsidian vault поверх существующих markdown-файлов (docs/, memory/, cache/), обеспечив навигацию по знаниям через wiki-links и graph view.

**Приоритет:** P0
**Трудозатраты:** S
**Зависимости:** Нет

#### Задачи

- [ ] Добавить `obsidian-mcp` сервер в `.mcp.json` с конфигурацией vault path
- [ ] Создать `.obsidian/` директорию в корне vault с `app.json`, `workspace.json`, `community-plugins.json`
- [ ] Настроить `workspace.json` для монтирования `docs/`, `memory/`, `.claude/skills/*/cache/` как единое пространство
- [ ] Создать `docs/wiki/_index.md` с картой wiki-страниц и cross-reference таблицей
- [ ] Добавить wiki-links в существующие `memory/MEMORY.md` на связанные документы
- [ ] Настроить `.obsidian/templates/` для шаблонов новых wiki-страниц (entity, concept, how-to)
- [ ] Создать `.claude/skills/obsidian-vault/SKILL.md` с инструкциями по работе с vault
- [ ] Протестировать graph view: убедиться что ≥30 узлов видны и связаны
- [ ] Добавить `.gitignore` правила для `.obsidian/workspace.json` (пользовательский state)

#### Критерии готовности

- [ ] Obsidian открывает корень проекта как vault без ошибок
- [ ] Graph view отображает ≥30 связанных узлов из docs/, memory/, cache/
- [ ] Wiki-links между MEMORY.md и docs/ работают (click → navigate)
- [ ] obsidian-mcp сервер отвечает на list_pages, search, get_backlinks
- [ ] Существующие скиллы и хуки работают без изменений

#### Риски и митигация

| Риск | Митигация |
|------|-----------|
| Obsidian конфликтует с .claude/ файлами | Исключить .claude/ из vault через .obsidian/appearance.json |
| Производительность graph view при >500 файлов | Настроить graph filter на tagged pages только |
| Wiki-links ломают markdown-парсеры | Использовать стандартный `[[link]]` синтаксис, обратно совместимый |

---

### Фаза 2: Foundation — MPF + anti_triggers + log/schema

**Цель:** Формализовать паттерны столпов 1-2: MPF helper для структурированных промптов, anti_triggers для негативных границ скиллов, log.md и SCHEMA.md для хронологии и правил ведения знаний.

**Приоритет:** P1
**Трудозатраты:** M
**Зависимости:** Нет

#### Задачи

- [ ] Создать `src/shared/mpf_prompt.py` с классом `MPFPrompt` (поля: ask, context, constraints, example, output_format)
- [ ] Реализовать валидацию MPF-структуры: обязательные поля, длина секций, формат example
- [ ] Мигрировать промпты `src/pdf_framework/agents/grader.py` на MPF helper
- [ ] Мигрировать промпты `src/pdf_framework/agents/rewriter.py` на MPF helper
- [ ] Мигрировать промпты `src/pdf_framework/agents/hallucination_check.py` на MPF helper
- [ ] Добавить `anti_triggers` в JSON schema `.claude/skills/skill-router-config.json`
- [ ] Обновить `src/skill_router.py` слой A (phrase matching) для проверки anti_triggers
- [ ] Добавить anti_triggers в 5-10 наиболее конфликтующих скиллов (по данным роутинга)
- [ ] Создать `memory/log.md` с начальной записью и шаблоном хронологии
- [ ] Создать `memory/SCHEMA.md` с правилами именования, тегирования, cross-references
- [ ] Обновить `.claude/hooks/session-memory-save.py` для записи в `memory/log.md`

#### Критерии готовности

- [ ] MPFPrompt генерирует промпты с 4 обязательными секциями (ask, context, constraints, example)
- [ ] Все 3 LangGraph-агента используют MPF helper (0 f-string промптов в продакшн коде)
- [ ] anti_triggers блокируют ≥90% ложных активаций на тестовом наборе (20 запросов)
- [ ] memory/log.md содержит ≥5 записей после тестовой сессии
- [ ] memory/SCHEMA.md описывает ≥3 правила именования и ≥2 правила связывания
- [ ] Существующий skill-router проходит все текущие тесты без регрессии

#### Риски и митигация

| Риск | Митигация |
|------|-----------|
| MPF миграция ломает существующие промпты | Параллельное выполнение: старый и новый промпт, сравнение выходов |
| anti_triggers слишком агрессивны | Порог: anti_trigger срабатывает только при точном совпадении, не fuzzy |
| log.md растёт неограниченно | Лимит 500 строк, архивация в log-archive/ по месяцам |

---

### Фаза 3: Auto-Librarian Hook

**Цель:** Реализовать агента-библиотекаря (столп 4) как hook на запись в docs/ и memory/, который проверяет целостность wiki-links, детектирует конфликты и обновляет индексы.

**Приоритет:** P1
**Трудозатраты:** M
**Зависимости:** Фаза 1 (Obsidian vault)

#### Задачи

- [ ] Создать `.claude/hooks/auto-librarian.py` с триггером на PostToolUse (Write, Edit) в docs/, memory/
- [ ] Реализовать проверку wiki-links: парсинг `[[link]]`, валидация target существует
- [ ] Реализовать детект конфликтов: семантический поиск через Qdrant skill_library для новых страниц
- [ ] Создать `.claude/skills/auto-librarian/SKILL.md` с описанием процедур библиотекаря
- [ ] Интегрировать с memory-orchestrator MCP для уведомлений о конфликтах
- [ ] Реализовать авто-обновление `docs/wiki/_index.json` при добавлении/изменении страниц
- [ ] Добавить логирование действий в `memory/log.md` через librarian
- [ ] Настроить конфигурацию: `.claude/hooks/auto-librarian-config.json` (исключения, пороги)
- [ ] Протестировать на существующих wiki-страницах: 0 false positives на начальном наборе

#### Критерии готовности

- [ ] Hook срабатывает на каждый Write/Edit в docs/, memory/ без задержки >500ms
- [ ] Битые wiki-links детектируются и логируются с указанием source → target
- [ ] Семантические конфликты (дублирование содержания) детектируются при cosine similarity >0.85
- [ ] _index.json обновляется автоматически при изменении wiki-страниц
- [ ] Либрариан логирует ≥1 запись в log.md за каждую сессию с изменениями wiki
- [ ] Hook не блокирует запись при ошибке (fail-safe: логировать и продолжить)

#### Риски и митигация

| Риск | Митигация |
|------|-----------|
| Hook замедляет запись файлов | Асинхронное выполнение: fire-and-forget для некритичных проверок |
| Слишком много false positive конфликтов | Начальный порог similarity 0.90, итеративная настройка |
| Конфликт с session-memory-save hook | Явное упорядочивание: session-memory-save → auto-librarian |

---

### Фаза 4: PDF → Structured Wiki Pages

**Цель:** Создать альтернативу raw-chunks RAG — LLM pipeline, который читает PDF и генерирует структурированные markdown wiki-страницы с извлечёнными сущностями, связями и фактами.

**Приоритет:** P2
**Трудозатраты:** XL
**Зависимости:** Фазы 1, 2

#### Задачи

- [ ] Создать `src/pdf_framework/indexing/wiki_pipeline.py` с LangGraph StateGraph
- [ ] Определить схему wiki-страницы: `docs/wiki/templates/entity.md`, `concept.md`, `procedure.md`
- [ ] Реализовать узел extraction: LLM извлекает сущности и связи из PDF chunks
- [ ] Реализовать узел structuring: LLM генерирует markdown по шаблону из извлеченных данных
- [ ] Реализовать узел validation: проверка schema, wiki-links, полноты фактов
- [ ] Создать prompt templates в `src/pdf_framework/prompts/wiki_extraction.py` (MPF format)
- [ ] Реализовать параллельную индексацию: wiki_chunks в Qdrant collection `wiki_pages_v1`
- [ ] Создать eval suite: `tests/eval/wiki_pipeline_eval.py` с метриками precision, recall, F1
- [ ] Провести сравнение: structured wiki pages vs baseline chunk RAG на 10 тестовых PDF
- [ ] Интегрировать pipeline в `src/pdf_framework/agents/` как дополнительный маршрут обработки
- [ ] Добавить `.claude/skills/wiki-pipeline/SKILL.md` с инструкциями запуска и настройки

#### Критерии готовности

- [ ] Pipeline обрабатывает PDF → ≥3 wiki-страницы с извлеченными сущностями
- [ ] Schema валидация проходит на ≥95% сгенерированных страниц
- [ ] Wiki-links в сгенерированных страницах ссылаются на реальные документы
- [ ] Precision извлечения фактов ≥80% на тестовом наборе (manual eval)
- [ ] Qdrant collection wiki_pages_v1 содержит структурированные эмбеддинги
- [ ] Сравнительный eval показывает улучшение retrieval precision vs baseline ≥10%

#### Риски и митигация

| Риск | Митигация |
|------|-----------|
| LLM галлюцинирует факты при извлечении | Hallucination-check агент из существующего src/pdf_framework/agents/ |
| Pipeline слишком медленный для больших PDF | Chunk-level parallelism, progressive processing |
| Сгенерированные wiki-страницы низкого качества | Human-in-the-loop: ревью первых 20 страниц перед авто-режимом |

---

### Фаза 5: Sandbox для агентов

**Цель:** Интегрировать E2B SDK для безопасного исполнения Python-кода агентов (research скрипты, eval, тестовые запросы) без риска для основной среды.

**Приоритет:** P3
**Трудозатраты:** M
**Зависимости:** Фаза 2 (MPF для промптов sandbox-агентов)

#### Задачи

- [ ] Создать `src/pdf_framework/sandbox/e2b_backend.py` с интерфейсом SandboxBackend
- [ ] Реализовать методы: execute(code), install(package), upload(files), download(files)
- [ ] Создать `src/pdf_framework/sandbox/dry_run_backend.py` как fallback без E2B
- [ ] Интегрировать sandbox в research-скиллы: `architecture-research`, `tech-research`
- [ ] Добавить `.claude/skills/sandbox-execution/SKILL.md` с правилами использования
- [ ] Настроить timeout и resource limits для sandbox-сессий
- [ ] Реализовать dry-run режим для 1C execute_code как мягкая альтернатива full sandbox

#### Критерии готовности

- [ ] E2B sandbox исполняет Python-код изолированно (нет доступа к файловой системе хоста)
- [ ] Dry-run backend работает без E2B API key (для локальной разработки)
- [ ] Research-скиллы используют sandbox для eval скриптов
- [ ] Timeout 30с срабатывает корректно, ресурсы освобождаются
- [ ] Логирование sandbox-сессий в memory/log.md

#### Риски и митигация

| Риск | Митигация |
|------|-----------|
| E2B API недоступен | Dry-run backend как fallback, graceful degradation |
| Стоимость E2B при частом использовании | Лимит: 50 sandbox-сессий/день, кэширование результатов |
| Dry-run недостаточно изолирован | Явное предупреждение в SKILL.md: dry-run = preview only |

---

### Фаза 6: Defer — OAuth 2.1 MCP TTL

**Цель:** Добавить OAuth 2.1 авторизацию с TTL для MCP-серверов при переходе к multi-tenant production. В текущем single-user режиме не требуется.

**Приоритет:** P3
**Трудозатраты:** L
**Зависимости:** Фаза 5

#### Задачи

- [ ] Спроектировать OAuth 2.1 flow для MCP: `docs/design/oauth-mcp-flow.md`
- [ ] Реализовать `src/shared/mcp_oauth.py` с token management, TTL, refresh
- [ ] Добавить auth middleware в MCP серверы (поэтапно, начиная с pdf-vector-graph)
- [ ] Создать `.claude/skills/oauth-setup/SKILL.md` для deployment
- [ ] Настроить token storage: encrypted local или vault secret backend
- [ ] Провести security review: audit log, token revocation, scope validation

#### Критерии готовности

- [ ] MCP-серверы отклоняют запросы без валидного токена
- [ ] Токены имеют TTL ≤1 час, refresh token ≤24 часа
- [ ] Audit log содержит все запросы с токенами
- [ ] Token revocation работает мгновенно

#### Риски и митигация

| Риск | Митигация |
|------|-----------|
| Overhead для single-user | Feature flag: OAuth включается только при MULTI_TENANT=true |
| Сложность refresh flow | Использовать проверенные библиотеки (authlib, pyjwt) |

---

## Метрики успеха

| Метрика | Базовое значение | Целевое значение | Метод измерения |
|---------|-----------------|------------------|-----------------|
| Retrieval precision (wiki pages vs chunks) | Baseline chunk RAG | +10% precision | Eval suite на 10 тестовых PDF |
| Корректная активация скиллов | ~85% (оценка) | ≥95% | Тестовый набор 50 запросов, anti_triggers включены |
| Broken wiki-links | N/A (нет wiki) | 0 | Auto-librarian hook проверка |
| Knowledge compound rate | 0 (нет log) | ≥5 новых связей/сессия | Подсчёт в memory/log.md |
| Token usage per query | Baseline | -15% за счёт MPF | Логирование token_count в eval |
| Wiki pages from PDF | 0 | ≥3 pages/PDF | Wiki pipeline stats |
| MPF prompt compliance | 0% (f-string) | 100% агентов | Код-ревью: 0 f-string промптов |

---

## Открытые вопросы

1. **Obsidian free vs Obsidian Sync.** Использовать бесплатный локальный Obsidian с git-sync, или приобрести Obsidian Sync для multi-device? Git-sync добавляет friction, Sync стоит $96/год. Решение влияет на workflow обновления wiki.

2. **Inline wiki-links vs frontmatter refs.** Синтаксис `[[page-name]]` в теле документа или структурированные ссылки в YAML frontmatter (`related: [page1, page2]`)? Inline — гибче, frontmatter — парсабельнее. Гибридный вариант?

3. **Vault в git или отдельно.** Включать wiki-страницы в основной репозиторий (прозрачность, code review) или вынести в отдельный vault-репозиторий (чистота основного repo)? Размер и частота изменений — ключевые факторы.

4. **Wiki pages как chunks или entities.** При индексации в Qdrant — рассматривать wiki-страницу как единый chunk (проще, но теряет гранулярность) или разбивать на entity-level chunks (точнее, но сложнее поддерживать)?

5. **Auto-librarian автономность.** Должен ли библиотекарь автоматически разрешать конфликты (merge дубликатов) или только уведомлять? Полная автономия рискованна, но ручное разрешение — bottleneck.

---

## Ссылки

- `CLAUDE.md` — основной конфигурационный файл агента
- `AGENTS.md` — спецификация LangGraph-агентов
- `memory/MEMORY.md` — текущий flat index памяти (~240 строк)
- `.claude/skills/architecture-research/SKILL.md` — скилл архитектурного исследования
- `.claude/skills/tech-research/SKILL.md` — скилл технического исследования
- `.claude/skills/hooks-skills-mcp-triad/SKILL.md` — паттерн Triad (hooks + skills + MCP)
- `.claude/skills/memory-unified/SKILL.md` — оркестрация 4 систем памяти
- `docs/roadmap/` — другие роадмапы фреймворка (LLM Rotation, AutoResearch, BSL Intelligence)

---

## История изменений

| Дата | Версия | Описание |
|------|--------|----------|
| 2026-04-13 | v1.0 | Initial draft — на основе анализа первоисточника Hermes Agent / LLM Wiki Карпати |
