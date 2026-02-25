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
| VERIFY | Проверить соответствие knowledge | code-verify (knowledge-compliance) |
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
  └─ FAIL → Ralph Wiggum Loop (итеративный retry, макс 3)
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

## Фаза 4: VERIFY — верификация через code-verify

Запусти `code-verify` в режиме **knowledge-compliance**:

| Вход | Значение |
|------|----------|
| reference | knowledge_block из FETCH |
| code | результат EXECUTE |
| markers | маркерные паттерны из knowledge_block |

Результат: PASS → CREATE / PARTIAL → исправить → CREATE / FAIL → Ralph Wiggum Loop (макс 3).

Полная документация: `.claude/skills/code-verify/SKILL.md`

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
