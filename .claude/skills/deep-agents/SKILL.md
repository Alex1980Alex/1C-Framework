---
name: deep-agents
description: "Deep Agents LangChain CLI (import deepagents, deepagents-cli). ТОЛЬКО при: deepagents, FilesystemBackend, StoreBackend, CompositeBackend, TodoListMiddleware, SubAgentMiddleware, deep agent skills/memory. НЕ для LangChain create_agent (→ langchain-core), НЕ для LangGraph (→ langgraph-core), НЕ для Claude Code subagents, НЕ для 1С."
---

# Deep Agents

## Установка

```bash
pip install deepagents-cli
```

## Обзор

Интерактивный CLI для автономных агентов. Встроенные инструменты: файловые операции, shell, web search, HTTP, task delegation. Память между сессиями, поддержка навыков (SKILL.md), автодетекция моделей.

---

## CLI

```bash
deepagents                        # Запуск интерактивно
deepagents --model gpt-4.1        # Указать модель
deepagents --skills ./skills/     # Путь к навыкам
deepagents --thread my-thread     # Продолжить thread
```

### Встроенные команды

| Команда | Назначение |
|---------|-----------|
| `list` | Показать текущие файлы/задачи |
| `skills` | Показать доступные навыки |
| `reset` | Очистить контекст |
| `threads` | Список сохранённых threads |

---

## Встроенные инструменты

| Tool | Назначение |
|------|-----------|
| `write_todos` | Планирование и декомпозиция задач |
| `read_file` | Чтение файлов |
| `write_file` | Создание/перезапись файлов |
| `edit_file` | Редактирование (search/replace) |
| `ls` | Список файлов в директории |
| `glob` | Поиск по паттерну |
| `grep` | Поиск по содержимому |
| `shell` | Выполнение shell-команд |
| `task` | Spawn субагента для изолированной задачи |
| `web_search` | Поиск в интернете |
| `http_request` | HTTP-запросы к API |

---

## Backends (хранилища)

### StateBackend (ephemeral)

```python
from deepagents.backends import StateBackend

backend = StateBackend()
# Только в памяти, один thread, без persistence
```

### FilesystemBackend (локальный диск)

```python
from deepagents.backends import FilesystemBackend

backend = FilesystemBackend(
    root_dir="./workspace",
    virtual_mode=True  # Безопасность: изоляция от реальной FS
)
```

`virtual_mode=True` — агент работает в виртуальной FS, изменения не попадают на диск.

### StoreBackend (persistent)

```python
from deepagents.backends import StoreBackend

backend = StoreBackend(store=langgraph_store)
# Кросс-сессионная persistence через LangGraph Store
```

Путь `/memories/` → persistent store. Другие пути → ephemeral state.

### CompositeBackend (роутинг)

```python
from deepagents.backends import CompositeBackend

backend = CompositeBackend({
    "/project/": FilesystemBackend(root_dir="./project"),
    "/memories/": StoreBackend(store=store),
    "/temp/": StateBackend()
})
# Разные пути → разные backend-ы
```

---

## Middleware

| Middleware | Назначение |
|-----------|-----------|
| `TodoListMiddleware` | Планирование задач (write_todos tool) |
| `FilesystemMiddleware` | Абстракция файловой системы |
| `SubAgentMiddleware` | Делегирование задач подагентам |

### Auto-eviction

Большие tool outputs (> 20K токенов) автоматически выгружаются из контекста.

### Anthropic prompt caching

До 10x ускорение за счёт кеширования промптов (для Claude).

### Auto-summary

При 85% заполненности контекста — автоматическое резюмирование истории.

---

## Субагенты

```python
# Из основного агента
result = task(
    description="Research Python async patterns",
    tools=["web_search", "read_file"],
    model="gpt-4.1-mini"  # Можно использовать другую модель
)
```

### Изоляция

- Субагент получает **свой** контекст (не видит историю parent)
- Результат возвращается как строка
- Предотвращает context bloat
- Universal fallback agent всегда доступен

---

## Навыки (Skills)

Формат SKILL.md — тот же что в Claude Code.

```python
# Автозагрузка из директории
deepagents --skills ./skills/

# Или программно
agent = DeepAgent(skills_dir="./skills/")
```

Агент видит доступные навыки и загружает по необходимости.

---

## Долговременная память

```python
# Автоматическая — через StoreBackend
# Файлы в /memories/ сохраняются между сессиями

# Ручная — через store API
store.put(("memories", user_id), key, {"fact": "..."})
memories = store.search(("memories", user_id), query="...", limit=5)
```

---

## Human-in-the-Loop

```python
from deepagents import DeepAgent

agent = DeepAgent(
    hitl_tools=["shell", "write_file"],  # Требуют одобрения
    auto_approve=["read_file", "ls"]     # Автоматически
)
```

Агент приостанавливается и ждёт одобрения перед выполнением опасных действий.

---

## Sandbox Execution

| Провайдер | Тип | Назначение |
|-----------|-----|-----------|
| Modal | Cloud | Python execution |
| Runloop | Cloud | Isolated sandboxes |
| Daytona | Self-hosted | Development environments |

```python
# Shell commands выполняются в sandbox
agent = DeepAgent(
    sandbox="modal",  # или "runloop", "daytona"
    sandbox_config={"memory": "2Gi"}
)
```

---

## Безопасность

| Мера | Описание |
|------|----------|
| `virtual_mode` | Файловая изоляция |
| Policy wrappers | deny-prefixes для путей |
| HITL | Одобрение опасных действий |
| Sandbox | Изолированное выполнение shell |
| Auto-eviction | Ограничение контекста |

---

## Модели

Автодетекция по API-ключу:

| Переменная | Провайдер |
|-----------|-----------|
| `OPENAI_API_KEY` | OpenAI (gpt-4.1, gpt-5) |
| `ANTHROPIC_API_KEY` | Anthropic (claude-sonnet-4-5-20250929) |
| `GOOGLE_API_KEY` | Google Gemini |
| `AWS_*` | AWS Bedrock |
| `HUGGINGFACE_API_KEY` | HuggingFace |

---

**Источники:** Deep Agents/ — 11 файлов (Обзор, Быстрый старт, CLI, Бэкенды, Навыки, Middleware, Память, HITL, Субагенты, Настройка, Возможности)
