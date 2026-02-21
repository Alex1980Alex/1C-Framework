---
name: langgraph-production
description: "LangGraph в production: LangSmith (наблюдаемость, трейсинг), Studio (визуальный дебаг), развёртывание (LangSmith Cloud, langgraph.json), тестирование, структура приложения, Agent Chat UI. Триггеры: 'LangSmith', 'langsmith', 'LangGraph Studio', 'studio', 'langgraph deploy', 'развёртывание langgraph', 'langgraph.json', 'tracing langsmith', 'трейсинг', 'observability langgraph', 'наблюдаемость', 'langgraph test', 'тестирование графа', 'app structure langgraph', 'структура приложения', 'Agent Chat', 'agentchat', 'LangSmith Cloud', 'LangGraph Server', 'langgraph-sdk', 'get_client'. НЕ для StateGraph/edges — используй langgraph-core. НЕ для памяти/checkpointers — используй langgraph-memory-persistence."
---

# LangGraph Production

## LangSmith — наблюдаемость

### Включение трейсинга

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="lsv2_..."
export LANGSMITH_PROJECT="my-project"  # Опционально
```

### Теги и метаданные

```python
config = {
    "tags": ["production", "user_query"],
    "metadata": {"user_id": "123", "version": "1.0"},
    "configurable": {"thread_id": "thread_1"}
}
graph.invoke(inputs, config)
```

### Анонимизация (маскирование данных)

```python
from langsmith import Client
import re

def anonymize(data):
    if isinstance(data, str):
        data = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', data)
        data = re.sub(r'\b[\w.-]+@[\w.-]+\.\w+\b', '[EMAIL]', data)
    return data

client = Client(anonymizer=anonymize)
```

---

## LangSmith Studio — визуальный дебаг

### Запуск

```bash
pip install "langgraph-cli[inmem]"
langgraph dev                        # Автозагрузка langgraph.json
langgraph dev --config ./my.json     # Custom config
```

### Возможности

| Функция | Описание |
|---------|----------|
| Visual graph | Визуализация нод и edges |
| Step-through | Пошаговое выполнение |
| Hot reload | Изменения промптов/tools без перезапуска |
| Time travel | Откат к прошлым checkpoint-ам |
| Test runner | Запуск тестов из UI |
| State inspector | Просмотр state на каждом шаге |

### Interrupt-ы в Studio

Interrupt-точки отображаются визуально. Можно approve/reject/edit прямо в UI.

---

## Структура приложения

### langgraph.json

```json
{
  "dependencies": ["./packages/my-agent"],
  "graphs": {
    "agent": "./packages/my-agent/src/agent.py:graph"
  },
  "env": ".env"
}
```

### Рекомендуемая структура

```
my-agent/
├── langgraph.json           # Конфигурация
├── .env                     # Переменные окружения
├── packages/
│   └── my-agent/
│       ├── pyproject.toml
│       └── src/
│           ├── agent.py     # graph = builder.compile()
│           ├── nodes.py     # Функции нод
│           ├── tools.py     # @tool определения
│           ├── state.py     # TypedDict state
│           └── utils.py     # Вспомогательные
```

### Экспорт графа

```python
# agent.py
from langgraph.graph import StateGraph

builder = StateGraph(State)
# ... add nodes, edges ...
graph = builder.compile(checkpointer=checkpointer)
```

Переменная `graph` указана в `langgraph.json` → доступна через Server/Studio.

---

## Развёртывание

### LangSmith Cloud

```bash
# CLI deploy
langgraph deploy --config langgraph.json

# Или через GitHub интеграцию
# Push → автоматический deploy
```

### LangGraph Server (self-hosted)

```bash
pip install langgraph-cli
langgraph up --config langgraph.json --port 2024
```

### SDK клиент

```python
from langgraph_sdk import get_client, get_sync_client

# Async
client = get_client(url="http://localhost:2024")
thread = await client.threads.create()
run = await client.runs.create(
    thread["thread_id"],
    assistant_id="agent",
    input={"messages": [{"role": "user", "content": "Hello"}]}
)

# Sync
client = get_sync_client(url="http://localhost:2024")
result = client.runs.wait(thread["thread_id"], run["run_id"])
```

### Streaming через SDK

```python
async for event in client.runs.stream(
    thread["thread_id"],
    assistant_id="agent",
    input={"messages": [...]},
    stream_mode=["messages", "updates"]
):
    print(event)
```

---

## Тестирование

### Unit-тесты нод

```python
def test_classify_node():
    state = {"messages": [HumanMessage("I need help with billing")]}
    result = classify_node(state)
    assert result["classification"] == "billing"
```

### Тестирование с checkpointer

```python
from langgraph.checkpoint.memory import InMemorySaver

def test_full_graph():
    checkpointer = InMemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "test_1"}}
    result = graph.invoke(
        {"messages": [HumanMessage("Hello")]},
        config
    )
    assert "messages" in result
```

### Partial execution (тест до определённой ноды)

```python
# Compile с interrupt
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_after=["classify"]  # Останавливается после classify
)

config = {"configurable": {"thread_id": "test_2"}}
result = graph.invoke(inputs, config)

# Проверить промежуточный state
state = graph.get_state(config)
assert state.values["classification"] == "technical"

# Продолжить выполнение
graph.invoke(None, config)
```

### Update state (инъекция данных)

```python
# Принудительно установить state и продолжить
graph.update_state(config, values={"classification": "billing"})
result = graph.invoke(None, config)
```

### Node-level тестирование

```python
# Вызвать конкретную ноду напрямую
compiled = builder.compile()
node_fn = compiled.nodes["my_node"]
result = node_fn.invoke(test_state)
```

---

## Agent Chat UI

Next.js UI для взаимодействия с LangGraph Server.

```
https://agentchat.vercel.app
```

### Возможности

- Real-time tool visualization
- State branching (time travel)
- Multi-thread support
- HITL interrupt handling

### Подключение

```
URL: http://localhost:2024
Assistant ID: agent
```

---

## Паттерны production

### Health check

```python
# LangGraph Server автоматически предоставляет
# GET /health → {"status": "ok"}
# GET /info → {"version": "...", "graphs": [...]}
```

### Rate limiting

```python
from langchain.agents.middleware import ModelCallLimitMiddleware

agent = create_agent(
    model="gpt-4.1",
    tools=[...],
    middleware=[
        ModelCallLimitMiddleware(
            thread_limit=50,    # Max calls per thread
            run_limit=10,       # Max calls per run
            exit_behavior="end" # "end" или "interrupt"
        )
    ]
)
```

### Logging

```python
import logging
logging.getLogger("langgraph").setLevel(logging.DEBUG)
```

---

**Источники:** Lang Graph/Производство/ — 6 файлов (Наблюдаемость ЛангСмита, Студия, Развертывание, Тест, Структура приложения, Интерфейс чата)
