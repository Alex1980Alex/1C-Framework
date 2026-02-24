---
name: learning-loop
description: "Цикл обучения: SEARCH skill → FETCH knowledge → EXECUTE task → CREATE skill. Триггеры: 'нет скилла', 'найди информацию и сделай', 'learning loop', 'научись делать', 'создай скилл из опыта', 'fetch and learn'. НЕ для существующих скиллов — используй skill-router."
---

# Learning Loop — самообучающийся цикл Claude Code

## Обзор

Когда задача требует знаний, которых нет в существующих скиллах — запускается Learning Loop. Ищем скилл → не нашли → собираем знания из интернета → выполняем задачу → создаём новый скилл для будущего использования. Каждая новая задача делает систему умнее.

---

## Быстрый справочник

| Фаза | Действие | Инструменты |
|------|----------|-------------|
| SEARCH | Найти существующий скилл | Grep по skills/, skill-router-config.json |
| FETCH | Собрать знания | WebSearch, WebFetch, MCP Context7 |
| EXECUTE | Выполнить задачу | Skill-Delegated Subagent (Task tool) |
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
ФАЗА 2: FETCH — сбор знаний
  │ WebSearch: "{library} python best practices 2026"
  │ WebSearch: "site:github.com {library} examples"
  │ WebFetch: официальная документация (readthedocs, pypi)
  │ MCP Context7: resolve → read (если доступен)
  │
  │ Результат: собранные знания (KB)
  │
  ▼
ФАЗА 3: EXECUTE — выполнение задачи через субагента
  │ Читаем релевантные SKILL.md (смежные домены)
  │ Формируем промпт = KB + SKILL.md + Задача
  │ Task(subagent_type="general-purpose", prompt=...)
  │ Субагент реализует задачу, возвращает результат
  │
  │ Результат: реализованный код
  │
  ▼
ФАЗА 4: CREATE — создание скилла из опыта
  │ Применить doc-to-skill шаблон
  │ Извлечь: команды, паттерны, антипаттерны, диагностику
  │ Создать .claude/skills/<name>/SKILL.md
  │ Зарегистрировать в skill-router-config.json
  │
  │ Результат: новый скилл для будущего использования
  │
  ▼
ВЫХОД: Задача выполнена + скилл создан
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

## Фаза 2: FETCH — сбор знаний

### Стратегия поиска (приоритет источников)

```
1. Official docs (readthedocs, pypi, github README)    ← PRIMARY
2. GitHub examples (stars > 50, recent activity)         ← PATTERNS
3. Stack Overflow / Discussions (top-voted answers)      ← EDGE CASES
4. Blog posts от maintainers                             ← BEST PRACTICES
5. MCP Context7 (если доступен — structured docs)       ← STRUCTURED
```

### Шаблон поисковых запросов

```
WebSearch: "{library} python documentation official"
WebSearch: "{library} python best practices examples 2025 2026"
WebSearch: "{library} vs {alternative} comparison"
WebSearch: "site:github.com {library} production usage"
WebFetch: <URL из результатов WebSearch>
```

### MCP Context7 (если доступен)

```
1. context7_resolve_library("{library}") → получить context7_id
2. context7_get_library_docs(context7_id, topic="{specific topic}") → документация
```

### Критерии достаточности

Знания считаются достаточными когда собраны:
- [ ] Установка и зависимости
- [ ] Core API (3+ основных функций/классов)
- [ ] Минимум 2 рабочих примера
- [ ] Минимум 3 антипаттерна / частых ошибки
- [ ] Интеграция с нашим стеком (async, Pydantic, FastAPI)

---

## Фаза 3: EXECUTE — выполнение через субагента

### Паттерн: Skill-Delegated Subagent (ADR-007)

```
Оркестратор (Claude главный):
  1. Читает смежные SKILL.md (фреймворк-контекст)
  2. Формирует knowledge_block из FETCH результатов
  3. Делегирует субагенту:

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
  """
)
```

### Верификация результата

После выполнения субагентом:
1. Проверить что файлы созданы
2. Запустить тесты (если написаны)
3. Проверить на lint ошибки

---

## Фаза 4: CREATE — создание скилла

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
| WebSearch/WebFetch | FETCH: сбор знаний из интернета |
| Skill-Delegated Subagent | EXECUTE: делегирование с контекстом |
| doc-to-skill | CREATE: конвертация знаний в скилл |
| triad-factory | CREATE: Q1-Q6 если нужны hook/enforcer |

---

## Пример: полный цикл

```
Задача: "Добавь retry с exponential backoff для API вызовов"

SEARCH:
  grep -ri "retry\|tenacity\|backoff" .claude/skills/*/SKILL.md
  → НЕ НАЙДЕНО

FETCH:
  WebSearch("tenacity python retry best practices 2026")
  WebSearch("tenacity async retry decorator examples")
  WebFetch(tenacity readthedocs)
  → Собрано: API, декораторы, async поддержка, jitter

EXECUTE:
  Task(general-purpose):
    Контекст: framework-config SKILL + tenacity KB
    Задача: создать src/pdf_framework/utils/retry.py
  → Реализован модуль с retry декоратором

CREATE:
  .claude/skills/tenacity-retry/SKILL.md
  skill-router-config.json → "tenacity-retry" bundle
  → Скилл готов к использованию в будущих сессиях
```

---

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| Сразу писать код без SEARCH | Может быть скилл с готовыми паттернами | Всегда начинай с поиска скилла |
| FETCH без критериев достаточности | Неполные знания → плохой код | Проверяй 5 критериев достаточности |
| Не создавать скилл после задачи | Следующая сессия повторит FETCH | ВСЕГДА создавай скилл (CREATE обязательна) |
| Скилл без антипаттернов | Claude повторит ошибки | Минимум 3 антипаттерна из опыта |
| Копировать всю документацию | Скилл > 500 строк, бесполезен | Извлечь только actionable знания |
