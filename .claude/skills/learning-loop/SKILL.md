---
name: learning-loop
description: "Цикл обучения: SEARCH → FETCH → EXECUTE → VERIFY → CREATE. Триггеры: 'нет скилла', 'найди информацию и сделай', 'learning loop', 'научись делать', 'создай скилл из опыта', 'fetch and learn'. НЕ для существующих скиллов — используй skill-router."
---

# Learning Loop — самообучающийся цикл Claude Code

## Обзор

Когда задача требует знаний, которых нет в существующих скиллах — запускается Learning Loop. Ищем скилл → не нашли → собираем знания из интернета → выполняем задачу → создаём новый скилл для будущего использования. Каждая новая задача делает систему умнее.

---

## Быстрый справочник

| Фаза | Действие | Инструменты |
|------|----------|-------------|
| SEARCH | Найти существующий скилл | Grep по skills/, skill-router-config.json |
| FETCH | Собрать знания (ротация источников) | Context7, WebSearch, WebFetch |
| EXECUTE | Выполнить задачу с атрибуцией | Skill-Delegated Subagent (Task tool) |
| VERIFY | Проверить соответствие knowledge | Grep + ревьюер-субагент (обязательный) |
| CREATE | Создать скилл | doc-to-skill, skill-router-config.json |

---

## Алгоритм

```
ВХОД: Задача программирования (или любая задача)
  │
  ▼
ФАЗА 1: SEARCH — поиск существующего скилла
  │ Grep по .claude/skills/*/SKILL.md
  │ Проверить skill-router-config.json keywords
  │
  ├─ НАЙДЕН → Использовать скилл напрямую → КОНЕЦ
  │
  └─ НЕ НАЙДЕН → продолжить
      │
      ▼
ФАЗА 2: FETCH — сбор знаний (ротация источников по домену)
  │ Определить домен: tech-python | tech-other | 1c
  │ Ротация источников в порядке trust score
  │ Минимум 3 разных источника
  │
  │ Результат: knowledge_block (KB) + маркерные паттерны
  │
  ▼
ФАЗА 3: EXECUTE — выполнение с атрибуцией
  │ Промпт = KB + SKILL.md + Задача + требование атрибуции
  │ Task(subagent_type="general-purpose", prompt=...)
  │ Субагент указывает Source: для каждого решения
  │
  │ Результат: код с атрибуциями
  │
  ▼
ФАЗА 4: VERIFY — трёхуровневая верификация
  │ Уровень 1: grep маркерных паттернов (оркестратор)
  │ Уровень 2: ревьюер-субагент (ОБЯЗАТЕЛЬНЫЙ)
  │ Уровень 3: решение оркестратора (PASS/PARTIAL/FAIL)
  │
  ├─ PASS/PARTIAL → продолжить
  └─ FAIL → повторный EXECUTE с фидбеком (макс 1 retry)
      │
      ▼
ФАЗА 5: CREATE — создание скилла из опыта
  │ Применить doc-to-skill шаблон
  │ Извлечь: команды, паттерны, антипаттерны, диагностику
  │ Создать .claude/skills/<name>/SKILL.md
  │ Зарегистрировать в skill-router-config.json
  │
  │ Результат: новый скилл для будущего использования
  │
  ▼
ВЫХОД: Задача выполнена + скилл создан + верифицирован
```

---

## Фаза 1: SEARCH — поиск скилла

### Шаг 1.1: Поиск по ключевым словам

```bash
# Поиск в SKILL.md файлах
grep -ri "keyword1\|keyword2" .claude/skills/*/SKILL.md

# Поиск в роутере
grep -i "keyword" .claude/skills/skill-router-config.json
```

### Шаг 1.2: Семантический поиск (если keyword miss)

Если точного совпадения нет — проверь смежные домены:

| Задача | Смежный скилл |
|--------|---------------|
| Retry/resilience | framework-troubleshooting, langchain-core |
| HTTP client | framework-api, langchain-integrations |
| Data validation | framework-config, langchain-core |
| Testing | evaluation-benchmark |
| Logging | framework-troubleshooting, claude-code-admin |

### Шаг 1.3: Решение

| Результат | Действие |
|-----------|----------|
| Точное совпадение | Использовать скилл → КОНЕЦ |
| Частичное совпадение | Расширить существующий скилл (добавить секцию) |
| Нет совпадения | Перейти к FETCH |

---

## Фаза 2: FETCH — сбор знаний (ротация источников)

**Ключевой принцип:** Источники ротируются в порядке убывания доверия (trust score).
Модуль оценки: `.claude/hooks/shared/trust_scorer.py` (TrustScorer).

### Определение домена

| Домен | Когда | Примеры |
|-------|-------|---------|
| **tech-python** | Python-библиотеки, RAG/ML фреймворки | tenacity, LangChain, FastAPI, Qdrant |
| **tech-other** | Другие языки и технологии | React, Go, Rust, Docker, K8s, TypeScript |
| **1c** | Платформа 1С:Предприятие | BSL, регистры, справочники, отчёты |

### Ротация источников по доменам

#### Домен: tech-python (Python-библиотеки)

| Приоритет | Источник | Trust | Инструмент | Что искать |
|-----------|----------|-------|------------|------------|
| 1 | **MCP Context7** | 1.0 | resolve-library-id + get-library-docs | Structured official docs |
| 2 | **StackOverflow** | rubric | WebSearch site:stackoverflow.com | Edge cases, pitfalls, accepted answers |
| 3 | **GitHub Repos** | rubric | WebSearch site:github.com stars:>100 | Production patterns, real examples |
| 4 | **Official Docs** | high | WebFetch readthedocs/pypi | API reference, installation |
| 5 | **Comparison** | medium | WebSearch "{lib} vs {alt}" | Benchmarks, trade-offs |

#### Домен: tech-other (другие языки и технологии)

| Приоритет | Источник | Trust | Инструмент | Что искать |
|-----------|----------|-------|------------|------------|
| 1 | **MCP Context7** | 1.0 | resolve-library-id (если есть в Context7) | Structured docs для React, Vue, Express и т.д. |
| 2 | **Official Docs** | high | WebFetch (docs.docker.com, go.dev, и т.д.) | API reference, getting started |
| 3 | **StackOverflow** | rubric | WebSearch site:stackoverflow.com [{tag}] | Common issues, best practices |
| 4 | **GitHub Repos** | rubric | WebSearch site:github.com stars:>100 | Templates, boilerplates, examples |
| 5 | **Awesome Lists** | medium | WebSearch "awesome-{tech} github" | Curated resource lists |

#### Домен: 1С Предприятие

| Приоритет | Источник | Trust | Инструмент | Что искать |
|-----------|----------|-------|------------|------------|
| 1 | **Infostart.ru** | rubric | WebSearch site:infostart.ru | Публикации с рейтингом >= 4.0 |
| 2 | **its.1c.ru** | high | WebSearch site:its.1c.ru | Официальная документация |
| 3 | **GitHub** | rubric | WebSearch site:github.com 1C BSL | Открытые проекты, конфигурации |
| 4 | **StackOverflow** | rubric | WebSearch site:stackoverflow.com [1c] | Ответы сообщества |

### MCP Context7 — первоисточник для tech-доменов

Context7 предоставляет structured documentation для 1000+ библиотек.

**Алгоритм использования:**
```
1. Вызвать resolve-library-id с именем библиотеки/технологии
   → Если resolves → получить context7_id
   → Если НЕ resolves → пропустить, перейти к приоритету 2

2. Вызвать get-library-docs с context7_id и topic
   → Получить актуальную документацию
   → Trust = 1.0 (всегда доверяем)

Примеры библиотек в Context7:
  Python: FastAPI, LangChain, Pydantic, SQLAlchemy, tenacity, httpx
  JS/TS: React, Next.js, Express, Prisma, Drizzle
  Go: Gin, Echo, GORM
  Rust: Actix, Tokio, Serde
```

### StackOverflow — edge cases и антипаттерны

```
WebSearch: "site:stackoverflow.com {library} {problem} [{language}]"
WebSearch: "site:stackoverflow.com {library} common mistakes pitfalls"

Критерии качества ответа (trust_scorer.py):
  - is_accepted: True (вес 40%)
  - score >= 3 upvotes (вес 30%)
  - recency_days <= 365 (вес 30%)
```

### GitHub Repos — production patterns

```
WebSearch: "site:github.com {library} production stars:>100"
WebSearch: "{library} {language} real-world example github"

Критерии качества repo (trust_scorer.py):
  - stars >= 100 (вес 30%)
  - last_commit_days <= 90 (вес 25%)
  - has_docs: yes (вес 25%)
  - license: MIT/Apache/BSD/ISC (вес 20%)
```

### Trust Score рубрика

| Источник | Trust | Критерии |
|----------|-------|----------|
| **Context7** | 1.0 (всегда) | Structured official docs, всегда актуальны |
| **GitHub** | 0.0-1.0 | stars 30%, recency 25%, docs 25%, license 20% |
| **StackOverflow** | 0.0-1.0 | accepted 40%, score 30%, recency 30% |
| **Infostart** | 0.0-1.0 | rating 35%, downloads 35%, recency 30% |

### Критерии достаточности

Знания считаются достаточными когда собраны **ИЗ МИНИМУМ 3 РАЗНЫХ ИСТОЧНИКОВ**:

- [ ] Context7 docs ИЛИ official docs (если Context7 недоступен)
- [ ] Минимум 1 StackOverflow ответ (accepted или score >= 3)
- [ ] Минимум 1 GitHub repo (stars >= 50, last commit < 90 days)
- [ ] Core API (3+ основных функций/классов)
- [ ] Минимум 2 рабочих примера (из разных источников)
- [ ] Минимум 3 антипаттерна / частых ошибки (преимущественно из SO)
- [ ] Интеграция с целевым стеком проекта

---

## Фаза 3: EXECUTE — выполнение через субагента

### Паттерн: Skill-Delegated Subagent (ADR-007)

```
Оркестратор (Claude главный):
  1. Читает смежные SKILL.md (фреймворк-контекст)
  2. Формирует knowledge_block из FETCH результатов
  3. Извлекает маркерные паттерны из knowledge_block (для верификации)
  4. Делегирует субагенту с требованием атрибуции:

Task(
  subagent_type="general-purpose",
  prompt="""
    # Контекст проекта
    {содержимое смежного SKILL.md}

    # Знания о библиотеке
    {knowledge_block из FETCH}

    # Задача
    {конкретная задача программирования}

    # Требования
    - Python 3.11+, async-first
    - Pydantic v2 для моделей
    - Тесты с pytest

    # Атрибуция (ОБЯЗАТЕЛЬНО)
    Для каждой функции/класса укажи в docstring:
      Source: [название секции из knowledge_block]
    Если используешь паттерн НЕ из knowledge_block — укажи:
      Source: [own] и объясни почему
  """
)
```

---

## Фаза 4: VERIFY — трёхуровневая верификация

**ОБЯЗАТЕЛЬНАЯ ФАЗА.** Проверяет что субагент использовал знания из FETCH, а не свои training данные.

### Уровень 1: Структурная проверка (оркестратор, автоматическая)

```
Оркестратор выполняет grep/read по результату EXECUTE:

  1. Маркерные паттерны из knowledge_block присутствуют?
     Пример: knowledge говорит "используй wait_exponential_jitter"
     → grep "wait_exponential_jitter" в результате
     → Если найден wait_exponential БЕЗ _jitter → ПРОБЛЕМА

  2. Антипаттерны из knowledge_block ОТСУТСТВУЮТ?
     Пример: knowledge говорит "@retry без параметров — антипаттерн"
     → grep "^@retry$" в результате → не должно быть

  3. Атрибуции (Source:) присутствуют?
     → grep "Source:" в результате → должны быть

  Результат: список проблем (может быть пустой)
```

### Уровень 2: Ревьюер-субагент (ОБЯЗАТЕЛЬНЫЙ)

```
Task(
  subagent_type="general-purpose",
  prompt="""
    # Роль
    Ты — code reviewer. Проверь что код написан на основе
    предоставленных знаний, а не training данных агента.

    # Эталонные знания (из FETCH)
    {knowledge_block}

    # Код для проверки (из EXECUTE)
    {результат EXECUTE}

    # Проблемы структурной проверки
    {список проблем из Уровня 1, если есть}

    # Инструкция проверки
    Для КАЖДОЙ функции/класса в коде:
    1. Найди соответствующую секцию в эталонных знаниях
    2. Сравни: API, параметры, паттерны совпадают?
    3. Проверь атрибуцию (Source:) — корректна ли ссылка?
    4. Если функция НЕ из knowledge — это ошибка или обоснованное дополнение?

    # Формат ответа
    ## Соответствие knowledge_block
    | Функция | Source указан | Соответствует knowledge | Комментарий |
    |---------|--------------|------------------------|-------------|

    ## Вердикт
    PASS — код соответствует knowledge_block
    FAIL — код содержит расхождения (перечислить)
    PARTIAL — частичное соответствие (перечислить проблемы)

    ## Рекомендации (если FAIL/PARTIAL)
    Конкретные исправления со ссылками на секции knowledge_block.
  """
)
```

### Уровень 3: Решение оркестратора

```
Вердикт ревьюера:
  PASS    → перейти к CREATE
  PARTIAL → оркестратор исправляет конкретные проблемы → CREATE
  FAIL    → Ralph Wiggum цикл (итеративный EXECUTE → VERIFY)
```

### Полный pipeline EXECUTE + VERIFY

```
EXECUTE (субагент + атрибуция)
  │
  ▼
VERIFY Уровень 1: grep маркерных паттернов (оркестратор, 0 cost)
  │
  ▼
VERIFY Уровень 2: ревьюер-субагент (обязательный, 1 subagent call)
  │
  ├─ PASS    → CREATE
  ├─ PARTIAL → исправить → CREATE
  └─ FAIL    → Ralph Wiggum Loop (см. ниже)
```

### Ralph Wiggum Loop — итеративный retry при FAIL

При FAIL ревьюера запускается Ralph Wiggum цикл — итеративный
EXECUTE → VERIFY с фидбеком до достижения PASS.

```
FAIL (ревьюер вернул список проблем)
  │
  ▼
Ralph Wiggum итерация N (макс 3):
  │
  │ Промпт = knowledge_block
  │        + код предыдущей попытки
  │        + фидбек ревьюера (конкретные проблемы)
  │        + "Исправь ТОЛЬКО указанные проблемы"
  │
  ├─ EXECUTE: субагент исправляет код
  │
  ├─ VERIFY: ревьюер проверяет исправления
  │    ├─ PASS    → RALPH_DONE → CREATE
  │    ├─ PARTIAL → оркестратор фиксит → RALPH_DONE → CREATE
  │    └─ FAIL    → следующая итерация (N+1)
  │
  └─ После 3 неудачных итераций:
       → Объяснить почему не удаётся (не зацикливаться)
       → CREATE с пометкой "requires manual review"
       → В skill антипаттерны: добавить проблемные места
```

**Принципы Ralph Wiggum в VERIFY:**
- Каждая итерация получает фидбек предыдущей (не начинает с нуля)
- После 3 неудач — объяснить причину, не зацикливаться
- Коммит по одному логическому изменению на итерацию
- Фидбек ревьюера = конкретные строки + секции knowledge_block

---

## Фаза 5: CREATE — создание скилла

### Алгоритм создания (doc-to-skill)

```
1. Объединить знания:
   - FETCH результаты (документация, примеры)
   - EXECUTE опыт (что сработало, что нет)
   - Антипаттерны (ошибки при реализации)

2. Применить шаблон SKILL.md:
   - Обзор (2-4 предложения)
   - Быстрый справочник (таблица)
   - Установка (pip install)
   - Основные команды/API
   - Паттерны использования (копируемые шаблоны)
   - Диагностика (проблема → причина → решение)
   - Антипаттерны

3. Регистрация:
   - Создать .claude/skills/<name>/SKILL.md
   - Добавить bundle в skill-router-config.json
   - Проверить уникальность триггеров
```

### Чеклист нового скилла

- [ ] SKILL.md создан (≤ 500 строк)
- [ ] Description ≤ 300 символов с триггерами
- [ ] Минимум 5 триггерных фраз
- [ ] Минимум 1 НЕ-redirect на смежный скилл
- [ ] Bundle в skill-router-config.json
- [ ] Триггеры уникальны (grep проверка)
- [ ] Минимум 3 копируемых шаблона
- [ ] Минимум 3 антипаттерна

---

## Интеграция с триадой

Learning Loop использует существующие компоненты:

| Компонент | Роль в Learning Loop |
|-----------|---------------------|
| skill-router | SEARCH: поиск существующих скиллов |
| Context7/WebSearch/WebFetch | FETCH: сбор знаний (ротация источников) |
| trust_scorer.py | FETCH: оценка качества источников |
| Skill-Delegated Subagent | EXECUTE: делегирование с контекстом + атрибуция |
| Ревьюер-субагент | VERIFY: обязательная проверка соответствия knowledge |
| doc-to-skill | CREATE: конвертация знаний в скилл |
| triad-factory | CREATE: Q1-Q6 если нужны hook/enforcer |

---

## Пример: полный цикл (5 фаз)

```
Задача: "Добавь retry с exponential backoff для API вызовов"

SEARCH:
  grep -ri "retry\|tenacity\|backoff" .claude/skills/*/SKILL.md
  → НЕ НАЙДЕНО

FETCH (домен: tech-python):
  1. Context7: resolve-library-id("tenacity") → structured docs
  2. WebSearch("site:stackoverflow.com tenacity common mistakes")
     → accepted answer: "всегда используй reraise=True"
  3. WebSearch("site:github.com tenacity production stars:>100")
     → github.com/jd/tenacity (13K stars, MIT)
  4. WebFetch(tenacity.readthedocs.io)
  → KB: API + маркеры: wait_exponential_jitter, reraise=True, stop_after_attempt|stop_after_delay

EXECUTE (с атрибуцией):
  Task(general-purpose):
    Промпт: framework-config SKILL + tenacity KB + задача
    Требование: "Source: [секция] для каждой функции"
  → retry.py с 4 декораторами + Source: атрибуции

VERIFY:
  Уровень 1 (структурная):
    grep "wait_exponential_jitter" → найдено ✓
    grep "reraise=True" → найдено ✓
    grep "^@retry$" → не найдено ✓ (антипаттерн отсутствует)
  Уровень 2 (ревьюер-субагент):
    Task(general-purpose, prompt=KB + код + инструкция проверки)
    → PASS: все 4 функции соответствуют knowledge_block
  Уровень 3: PASS → переходим к CREATE

CREATE:
  .claude/skills/tenacity-retry/SKILL.md
  skill-router-config.json → "tenacity-retry" bundle
  → Скилл готов к использованию + верифицирован
```

---

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| Сразу писать код без SEARCH | Может быть скилл с готовыми паттернами | Всегда начинай с поиска скилла |
| FETCH без критериев достаточности | Неполные знания → плохой код | Минимум 3 источника, trust scoring |
| Пропустить VERIFY | Субагент мог использовать training данные | VERIFY обязательна (ревьюер-субагент) |
| EXECUTE без атрибуции | Нельзя проверить соответствие knowledge | Всегда требуй Source: в промпте |
| Не создавать скилл после задачи | Следующая сессия повторит FETCH | ВСЕГДА создавай скилл (CREATE обязательна) |
| Скилл без антипаттернов | Claude повторит ошибки | Минимум 3 антипаттерна из опыта |
| Копировать всю документацию | Скилл > 500 строк, бесполезен | Извлечь только actionable знания |
