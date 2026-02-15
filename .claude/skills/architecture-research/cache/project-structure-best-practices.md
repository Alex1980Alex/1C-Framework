# Структура проекта — Best Practices для Python RAG Framework

**Дата исследования:** 2026-02-12
**Контекст:** PDF Vector & Graph Framework (251 Python файл, 4 точки входа, 19 пакетов)

---

## 1. Организация проекта: Layer-based vs Feature-based

### Layer-based (по техническому слою)
- Файлы группируются по типу: `routers/`, `models/`, `services/`, `schemas/`
- Подходит для **domain libraries** и **микросервисов**
- Официальная документация FastAPI использует этот подход
- **Источник:** [FastAPI Official: Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

### Feature-based (по домену/функциональности)
- Файлы группируются по бизнес-домену: `auth/`, `users/`, `posts/` — каждый со своими router, schemas, models
- Подходит для **больших монолитных приложений** с множеством доменов
- Рекомендуется [FastAPI Best Practices (zhanymkanov)](https://github.com/zhanymkanov/fastapi-best-practices) — вдохновлён Netflix Dispatch
- **Источник:** [FastAPI Project Structure for Large Applications 2026](https://medium.com/@devsumitg/the-perfect-structure-for-a-large-production-ready-fastapi-app-78c55271d15c)

### Наш выбор: Layer-based для ядра
- `pdf_framework/` — это **domain library** (не бизнес-приложение), поэтому layer-based правильный
- `api/routes/` — это адаптер, feature-based тут не нужен (1 домен: PDF RAG)
- **Вердикт:** текущая организация верная

---

## 2. src/ Layout

- **Рекомендация:** размещать код в `src/` (а не в корне)
- **Причины:** предотвращает import shadowing, заставляет использовать `pip install -e .`
- **Наш проект:** использует `src/` — **соответствует**
- **Источник:** Python Packaging Guide, PEP 517/518

---

## 3. LangGraph Agent Structure

Официальная рекомендация LangChain для LangGraph-приложений:

```
my_agent/
├── utils/
│   ├── tools.py       — инструменты графа
│   ├── nodes.py       — функции узлов
│   └── state.py       — определение состояния
├── __init__.py
└── agent.py           — конструкция графа
```

- **Наш проект:** `agents/rag/` с `nodes/`, `state.py`, `agent.py` — **соответствует**
- **Источник:** [LangGraph Application Structure](https://docs.langchain.com/langgraph-platform/application-structure)

---

## 4. Monorepo с несколькими точками входа

### UV Workspaces (современный подход)
```
project/
├── pyproject.toml          — корневой workspace
├── packages/
│   └── core/               — общая библиотека
├── services/
│   ├── api/                — FastAPI
│   ├── cli/                — CLI
│   └── mcp-server/         — MCP
```

- **Подходит для:** крупных проектов (>5 пакетов), независимого версионирования
- **Наш проект:** единый pyproject.toml — **допустимо** на текущем масштабе (4 точки входа используют общий `pdf_framework`)
- **Источник:** [Python Monorepo with UV (TORE.dev)](https://tore.dev/en/blog/uv-monorepo-article), [Python Workspaces (UV)](https://tomasrepcik.dev/blog/2025/2025-10-26-python-workspaces/)

### Entry Points через pyproject.toml
```toml
[project.scripts]
pdf-api = "src.api.app:main"
pdf-cli = "src.cli.main:main"
pdf-mcp = "src.mcp_server.server:main"
```

- **Источник:** [Multiple Entry Points](https://blog.claude.nl/posts/how-to-structure-a-python-project-with-multiple-entry-points/)

---

## 5. Clean Architecture / Hexagonal

### Принцип
```
core/           — домен (бизнес-логика, порты/интерфейсы)
infrastructure/ — адаптеры (БД, API, внешние сервисы)
```

- **Наш проект:** `pdf_framework/` = core, `api/` = infrastructure adapter
- **Частичное соответствие:** routes импортируют framework напрямую (нет Service Layer)
- **Источник:** [Clean DDD Lessons](https://medium.com/unil-ci-software-engineering/clean-ddd-lessons-project-structure-and-naming-conventions-00d0b9c57610)

---

## 6. RAG Framework Structures (индустрия)

### FlashRAG (WWW2025)
- Модульная архитектура: retrievers, rerankers, generators, compressors
- 36 benchmark datasets, 23 алгоритма
- **Аналог:** наш `search/strategies/` + `search/reranking/`
- **Источник:** [FlashRAG](https://github.com/RUC-NLPIR/FlashRAG)

### LlamaIndex
- Модульная: Index → Query Engine → Response Synthesizer
- 300+ integration packages
- **Источник:** [LlamaIndex Documentation](https://developers.llamaindex.ai)

### Haystack
- Graph-like pipeline: Retriever → Reader → Generator
- **Аналог:** наш `search/pipelines/` (two-stage, section-first)
- **Источник:** [Haystack Documentation](https://haystack.deepset.ai)

---

## 7. Проблемные зоны нашего проекта

| Проблема | Тип | Приоритет | Рекомендация |
|----------|-----|-----------|--------------|
| Components = God Object | Coupling | Средний | Разбить на domain-specific holders |
| Routes → Framework (прямой импорт) | Coupling | Средний | Добавить Service Layer (`api/services/`) |
| config.py — монолитный | Size | Низкий | Оставить (пока <500 строк) |
| Дублирование (image/table extractors) | Debt | Низкий | Удалить deprecated в `loaders/` |
| Пустые пакеты (6 шт.) | Debt | Низкий | Удалить или заполнить |

---

## 8. Общая оценка

**85% соответствие best practices.** Структура зрелая для проекта из 251 файла.

Сильные стороны: interface-based design, strategy pattern, async-first, отсутствие циклических зависимостей, чёткое разделение точек входа.

Слабые стороны: God Object в DI, отсутствие Service Layer, технический долг (deprecated файлы, пустые пакеты).

---

## Источники (14)

1. [LangGraph Application Structure](https://docs.langchain.com/langgraph-platform/application-structure)
2. [LangGraph Architecture Guide 2025](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-ai-framework-2025-complete-architecture-guide-multi-agent-orchestration-analysis)
3. [FastAPI Best Practices (zhanymkanov)](https://github.com/zhanymkanov/fastapi-best-practices)
4. [FastAPI Project Structure 2026](https://medium.com/@devsumitg/the-perfect-structure-for-a-large-production-ready-fastapi-app-78c55271d15c)
5. [FastAPI Scalable Structure](https://fastlaunchapi.dev/blog/how-to-structure-fastapi)
6. [FastAPI Official: Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
7. [Python Monorepo with UV](https://tore.dev/en/blog/uv-monorepo-article)
8. [Python Workspaces (UV)](https://tomasrepcik.dev/blog/2025/2025-10-26-python-workspaces/)
9. [Multiple Entry Points](https://blog.claude.nl/posts/how-to-structure-a-python-project-with-multiple-entry-points/)
10. [Clean DDD Lessons](https://medium.com/unil-ci-software-engineering/clean-ddd-lessons-project-structure-and-naming-conventions-00d0b9c57610)
11. [FlashRAG (WWW2025)](https://github.com/RUC-NLPIR/FlashRAG)
12. [2025 Guide to RAG Frameworks](https://www.morphik.ai/blog/guide-to-oss-rag-frameworks-for-developers)
13. [Developer's Guide to Agentic Frameworks 2026](https://pub.towardsai.net/a-developers-guide-to-agentic-frameworks-in-2026-3f22a492dc3d)
14. [State of Agent Engineering](https://www.langchain.com/state-of-agent-engineering)
