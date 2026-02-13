---
name: tech-research
description: "Используй этот скилл когда пользователь спрашивает о технологиях RAG, embeddings, vector search, LLM, Python-библиотеках (LangChain, Qdrant, sentence-transformers), паттернах ML/AI, инструментах фреймворка. Триггеры: 'как работает RAG', 'что такое embeddings', 'документация по LangChain', 'reranking', 'chunking strategies', 'vector search', 'BM25', 'graph RAG', 'MCP', 'LangGraph', 'Qdrant API', 'sentence-transformers', 'ColBERT', 'FAISS', 'sparse vectors', 'hybrid search'. НЕ для 1С — для 1С используй 1c-doc-research."
---

# Tech Research — исследование технологий RAG/ML/Python

## Обзор

Исследовательский скилл для ответов по технологиям фреймворка: RAG, embeddings, vector search, LLM, Python-библиотеки. **Официальная документация библиотек — эталон.** Скилл ищет в official docs, GitHub, papers, верифицирует и кеширует результат.

**НЕ для 1С** — для вопросов по 1С:Предприятие используй `1c-doc-research`.

---

## Быстрый справочник

| Задача | Действие |
|--------|----------|
| Ответ по технологии | Фаза 0 (кеш) → Фаза 1 (official docs) → Фаза 2 (GitHub/papers) → Фаза 5 (кеш) |
| Проверить кеш | Прочитать `cache/_index.json`, найти по keywords |
| Поиск в official docs | `WebSearch: "[библиотека] official documentation 2025 OR 2026"` |
| Поиск на GitHub | `WebSearch: "site:github.com [тема] stars:>100"` |
| Сохранить в кеш | Создать topic-файл по `cache/_topic_template.md` + обновить `_index.json` |
| Проверить актуальность | `last_verified` < 7 дней = свежий, иначе quick verify |

---

## Домены

| Домен | Примеры тем | Ключевые источники |
|-------|-------------|-------------------|
| **RAG/Search** | embeddings, chunking, reranking, hybrid search, BM25 | LangChain docs, Qdrant docs, papers |
| **Python/ML** | LangChain, LangGraph, sentence-transformers, ONNX | PyPI, GitHub, official docs |
| **Vector DBs** | Qdrant, ChromaDB, FAISS, pgvector | Official docs, GitHub |
| **LLM/Agents** | Claude API, tool use, agent patterns, MCP | Anthropic docs, LangGraph docs |
| **Оптимизация** | ColBERT, FlashRank, sparse vectors, RAPTOR | Papers (arxiv), HuggingFace |

---

## Иерархия источников (СТРОГИЙ ПРИОРИТЕТ)

```
ПРИОРИТЕТ 1 — OFFICIAL DOCUMENTATION (обязательный)
│
├─ Официальная документация библиотеки/инструмента
│  (docs.langchain.com, qdrant.tech/documentation, etc.)
├─ API reference (readthedocs, GitHub pages)
│
ПРИОРИТЕТ 2 — VENDOR / AUTHOR
│
├─ Блог авторов библиотеки (langchain blog, qdrant blog)
├─ Release notes, changelogs, migration guides
├─ HuggingFace model cards (для моделей)
│
ПРИОРИТЕТ 3 — RESEARCH & CODE
│
├─ GitHub репозитории (stars > 100, active)
├─ Arxiv papers (для алгоритмов: ColBERT, RAPTOR, HyDE)
├─ Реальные бенчмарки (MTEB, BEIR)
│
ПРИОРИТЕТ 4 — COMMUNITY
│
├─ Stack Overflow (проверенные ответы, votes > 10)
├─ Habr / Medium (технические статьи с рабочим кодом)
├─ Discord/Forum обсуждения (с осторожностью)
│
ПРИОРИТЕТ 5 — НАШИ ДАННЫЕ
│
├─ MEMORY.md (наши решения, баги, trade-offs)
├─ CLAUDE.md (конфигурация фреймворка)
└─ docs/ (внутренняя документация проекта)
```

---

## Процесс исследования

### Фаза 0: Проверка кеша знаний (ПЕРЕД ПОИСКОМ)

1. Прочитай `.claude/skills/tech-research/cache/_index.json`
2. Найди topic по ключевым словам вопроса (fuzzy match по `keywords`)
3. **Если topic найден:**
   a. Прочитай topic-файл из `cache/`
   b. Проверь свежесть:
      - `last_verified` < 7 дней → **использовать как есть**
      - `last_verified` >= 7 дней → **quick verify**: WebSearch по теме, сравнить. Если API/версия не изменились — обновить `last_verified`. Иначе — Фаза 1
   c. Пометить: `[Из кеша знаний, верифицировано ДАТА]`
4. **Если topic НЕ найден** → перейти к Фазе 1

### Фаза 1: Official Documentation (ОБЯЗАТЕЛЬНО)

**Всегда начинай с официальных источников.**

```
WebSearch: "[библиотека] official documentation [версия]"
WebFetch: [URL документации] — если URL известен
WebSearch: "[библиотека] API reference [класс/метод]"
```

**Известные URL документации:**

| Библиотека | Документация |
|-----------|-------------|
| LangChain | python.langchain.com/docs |
| LangGraph | langchain-ai.github.io/langgraph |
| Qdrant | qdrant.tech/documentation |
| sentence-transformers | sbert.net |
| Anthropic/Claude | docs.anthropic.com |
| FastAPI | fastapi.tiangolo.com |
| Pydantic | docs.pydantic.dev |
| ChromaDB | docs.trychroma.com |
| HuggingFace | huggingface.co/docs |

Из ответа извлеки:
- **API** — классы, методы, параметры, return types
- **Версия** — для какой версии информация (breaking changes!)
- **Примеры кода** — рабочие, проверенные

### Фаза 2: Расширенные источники (ДОПОЛНЕНИЕ)

Запускай **параллельно** с Фазой 1.

**GitHub:**
```
WebSearch: "site:github.com [тема] stars:>100"
WebSearch: "site:github.com [библиотека] examples [паттерн]"
```

**Papers (для алгоритмов):**
```
WebSearch: "site:arxiv.org [алгоритм] [год]"
WebSearch: "[алгоритм] paper implementation python"
```

**Бенчмарки:**
```
WebSearch: "[модель/алгоритм] benchmark MTEB OR BEIR"
WebSearch: "[библиотека] performance comparison 2025 OR 2026"
```

**GitHub-репозитории — проверяй качество:**

| Критерий | Минимум | Идеально |
|----------|---------|----------|
| Stars | > 100 | > 1000 |
| Последний коммит | < 6 мес | < 1 мес |
| Issues ratio | < 50% open | < 20% open |
| Документация | README есть | docs/ есть |

### Фаза 3: Верификация

1. **Версия** — информация для текущей версии? Breaking changes между версиями?
   - LangChain 0.1 → 0.2 → 0.3: много breaking changes
   - Qdrant 1.x → текущая: API стабильный, но новые features
   - Пометить: `[Версия X.Y, проверить для текущей]`
2. **Deprecated** — метод/класс не устарел? Есть замена?
3. **Перекрёстная проверка** — факт подтверждён >= 2 источниками? Если нет: `[непроверено]`
4. **Наш опыт** — проверить MEMORY.md на bug patterns, workarounds, наши решения по этой теме

### Фаза 4: Оформление результата

Каждый факт ДОЛЖЕН иметь атрибуцию: `[Docs, URL]`, `[GitHub, URL]`, `[Paper, URL]`, `[MEMORY.md]`.

### Фаза 5: Кеширование знаний (ПОСЛЕ ОТВЕТА)

1. Определи нормализованное имя темы (lowercase, дефисы): `embeddings`, `langchain-tools`, `qdrant-sparse-vectors`
2. Создай topic-файл по шаблону `cache/_topic_template.md`:
   - Заполни **все 7 категорий знаний**: Идентификация, Установка и настройка, Core API, Паттерны, Архитектура, Диагностика, Источники
   - Frontmatter: `topic`, `domain`, `created`, `last_verified`, `version`, `sources`, `keywords`
3. Сохрани в `.claude/skills/tech-research/cache/<имя-темы>.md`
4. Обнови `cache/_index.json`: добавь запись с `file`, `created`, `last_verified`, `keywords`, `domain`

**7 категорий знаний:**

```
1. ИДЕНТИФИКАЦИЯ         → Что это, для чего, когда использовать, альтернативы
2. УСТАНОВКА И НАСТРОЙКА → pip install, config, зависимости, env vars
3. CORE API              → Классы, методы, параметры, типы, return values
4. ПАТТЕРНЫ              → Код-примеры, сценарии, интеграции, best practices
5. АРХИТЕКТУРА           → Как работает внутри, абстракции, ограничения, trade-offs
6. ДИАГНОСТИКА           → Частые ошибки, антипаттерны, debugging, performance
7. ИСТОЧНИКИ             → Полный список с атрибуцией [Docs, URL]
```

Полный шаблон: `cache/_topic_template.md`

---

## Формат ответа (ОБЯЗАТЕЛЬНЫЙ)

```markdown
## [Тема]: краткое резюме

### По официальной документации
<Основная информация из official docs>
<Каждый факт помечен: [Docs, URL]>
<Версия: [для X.Y.Z]>

### Код-примеры
<Рабочий код — копируй и запускай>
<Пометка: [из docs] или [из GitHub, URL] или [наш опыт]>

### Наш опыт (из фреймворка)
<Баги, workarounds, решения из MEMORY.md / CLAUDE.md>
<Пометка: [MEMORY.md] или [наш опыт, Phase N]>

### Альтернативы и trade-offs [если есть]
<Сравнение подходов, бенчмарки>

### Источники
- **[Official Docs]** URL — [что взято]
- **[GitHub]** URL — [что взято]
- **[Paper]** URL — [что взято]
- **[MEMORY.md]** — [что взято]
```

---

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| Пропустить official docs | Блоги устаревают, docs актуальны | ВСЕГДА начинай с WebSearch по official docs |
| Код без проверки версии | Breaking changes между версиями | Указывать версию: `[для LangChain 0.3.x]` |
| Deprecated API | Код сломается при обновлении | Проверять changelogs, migration guides |
| Факт без источника | Нельзя проверить | Каждый факт = [источник, URL] |
| Игнорировать MEMORY.md | Мы уже нашли баги и workarounds | Всегда сверять с нашим опытом |
| Не сохранить в кеш | Повторный поиск тратит время | Фаза 5: всегда кешировать |
| Копировать код из Medium | Может быть устаревшим / неполным | Предпочитать official docs + GitHub examples |
| Не указать trade-offs | Пользователь не видит альтернатив | Сравнивать подходы, давать бенчмарки |
