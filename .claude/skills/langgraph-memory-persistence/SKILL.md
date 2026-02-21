---
name: langgraph-memory-persistence
description: "LangGraph память и persistence: checkpointers (InMemory, Postgres, SQLite, Redis, MongoDB, CosmosDB), long-term memory (Store), semantic search, threads, state snapshots, message trimming, summarization, encryption. Триггеры: 'checkpointer', 'InMemorySaver', 'PostgresSaver', 'SqliteSaver', 'langgraph memory', 'long-term memory', 'BaseStore', 'InMemoryStore', 'PostgresStore', 'RedisStore', 'MongoDBStore', 'store.put', 'store.search', 'store.get', 'thread_id', 'get_state', 'get_state_history', 'update_state', 'StateSnapshot', 'trim_messages', 'RemoveMessage', 'REMOVE_ALL_MESSAGES', 'message summarization', 'EncryptedSerializer', 'semantic search memory', 'cross-thread memory', 'кратковременная память', 'долговременная память'. НЕ для StateGraph/edges — используй langgraph-core. НЕ для стриминга — используй langchain-streaming."
---

# LangGraph Memory & Persistence

## Два типа памяти

| Тип | Область | Хранилище | Пример |
|-----|---------|-----------|--------|
| **Short-term** | Per-thread | Checkpointer | История диалога |
| **Long-term** | Cross-thread | Store | Профиль пользователя, предпочтения |

---

## Short-term Memory (Checkpointers)

### Включение

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "user_123"}}
graph.invoke(inputs, config)
```

**Thread** — уникальный идентификатор диалога. Каждый thread хранит свою историю.

### Провайдеры checkpointers

| Checkpointer | Пакет | Когда |
|--------------|-------|-------|
| `InMemorySaver` | `langgraph-checkpoint` | Dev/тесты |
| `SqliteSaver` | `langgraph-checkpoint-sqlite` | Локальная разработка |
| `PostgresSaver` | `langgraph-checkpoint-postgres` | Production |
| `MongoDBSaver` | `langgraph-checkpoint-mongodb` | MongoDB-стек |
| `RedisSaver` | `langgraph-checkpoint-redis` | Redis-стек |
| `CosmosDBSaver` | `langgraph-checkpoint-cosmosdb` | Azure |

### Production: PostgreSQL

```bash
pip install langgraph-checkpoint-postgres
```

```python
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string("postgresql://user:pass@host/db") as checkpointer:
    checkpointer.setup()  # Создаёт таблицы (один раз)
    graph = builder.compile(checkpointer=checkpointer)
```

### Async-варианты

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
    await checkpointer.setup()
    graph = builder.compile(checkpointer=checkpointer)
```

### State Snapshots

```python
# Текущее состояние
state = graph.get_state(config)
# state.values — текущие значения
# state.next — следующие ноды к выполнению
# state.config — конфигурация checkpoint
# state.metadata — метаданные

# История состояний
states = list(graph.get_state_history(config))
selected = states[2]  # Прошлый checkpoint

# Модификация состояния
new_config = graph.update_state(config, values={"key": "new_value"})
graph.invoke(None, new_config)  # Продолжить с нового состояния
```

### Serialization

```python
# По умолчанию: JsonPlusSerializer (JSON + pickle fallback)

# Шифрование (production)
from langgraph.checkpoint.serde.encryption import EncryptedSerializer

serializer = EncryptedSerializer(
    key=b"32-byte-AES-key-here............"
)
checkpointer = PostgresSaver(conn, serde=serializer)
```

---

## Long-term Memory (Store)

### Включение

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
graph = builder.compile(checkpointer=checkpointer, store=store)
```

### Операции

```python
# Записать
store.put(
    namespace=("memories", "user_123"),
    key="preference_theme",
    value={"theme": "dark", "language": "ru"}
)

# Получить
item = store.get(("memories", "user_123"), "preference_theme")
# item.value → {"theme": "dark", "language": "ru"}

# Поиск (по namespace)
items = store.search(("memories", "user_123"), limit=10)

# Удалить
store.delete(("memories", "user_123"), "preference_theme")
```

### Доступ из нод

```python
def my_node(state, config, *, store):
    user_id = config["configurable"]["user_id"]

    # Читать
    memories = store.search(("memories", user_id), limit=5)

    # Писать
    store.put(
        ("memories", user_id),
        str(uuid.uuid4()),
        {"fact": "User prefers dark mode"}
    )

    return {"result": "done"}
```

### Semantic Search в Store

```python
from langchain_openai import OpenAIEmbeddings

store = InMemoryStore(
    index={
        "embed": OpenAIEmbeddings(model="text-embedding-3-small"),
        "dims": 1536,
        "fields": ["fact", "content"]  # Какие поля индексировать
    }
)

# Поиск по смыслу
results = store.search(
    ("memories", "user_123"),
    query="What does the user prefer?",
    limit=5
)
for item in results:
    print(f"Score: {item.score}, Value: {item.value}")
```

### Production Stores

| Store | Пакет | Когда |
|-------|-------|-------|
| `InMemoryStore` | `langgraph` | Dev/тесты |
| `PostgresStore` | `langgraph-checkpoint-postgres` | Production |
| `RedisStore` | `langgraph-checkpoint-redis` | High-throughput |
| `MongoDBStore` | `langgraph-checkpoint-mongodb` | MongoDB-стек |

```python
from langgraph.store.postgres import PostgresStore

async with PostgresStore.from_conn_string(conn_string) as store:
    await store.setup()
    graph = builder.compile(checkpointer=checkpointer, store=store)
```

---

## Message Management

### Trimming (ограничение длины)

```python
from langchain_core.messages import trim_messages

def trim_node(state):
    trimmed = trim_messages(
        state["messages"],
        max_tokens=4000,
        token_counter=model,        # Модель считает токены
        strategy="last",            # Оставить последние
        start_on="human",           # Начать с human message
        include_system=True,        # Сохранить system prompt
        allow_partial=False         # Не резать сообщения
    )
    return {"messages": trimmed}
```

### Удаление сообщений

```python
from langchain.messages import RemoveMessage, REMOVE_ALL_MESSAGES

# Удалить конкретное
return {"messages": [RemoveMessage(id="msg_abc123")]}

# Удалить все
return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}
```

### Summarization (сжатие истории)

```python
from langchain.agents.middleware import SummarizationMiddleware

agent = create_agent(
    model="gpt-4.1",
    tools=[...],
    middleware=[
        SummarizationMiddleware(
            trigger=("tokens", 4000),    # Триггер: > 4000 токенов
            keep=("messages", 20),       # Оставить последние 20
        )
    ]
)
```

### Ручная summarization

```python
def summarize_node(state):
    if len(state["messages"]) > 20:
        summary = model.invoke(
            f"Summarize this conversation:\n{state['messages'][:10]}"
        )
        # Заменить старые сообщения summary
        return {
            "messages": [
                RemoveMessage(id=m.id) for m in state["messages"][:10]
            ] + [SystemMessage(content=f"Summary: {summary.content}")]
        }
    return {}
```

---

## Subgraph Memory

### Наследование от parent

```python
# Child наследует checkpointer от parent автоматически
parent_builder.add_node("child", compiled_child_graph)
parent = parent_builder.compile(checkpointer=checkpointer)
```

### Независимая память subgraph

```python
# Child получает свой собственный checkpointer
child = child_builder.compile(checkpointer=True)
parent_builder.add_node("child", child)
```

### State access при interrupt

```python
# Только когда subgraph прерван
state = graph.get_state(config, subgraphs=True)
subgraph_state = state.tasks[0].state  # State подграфа
```

---

## Checkpoint Interface (для custom implementations)

```python
class BaseCheckpointSaver:
    def put(self, config, checkpoint, metadata, new_versions): ...
    def put_writes(self, config, writes, task_id): ...
    def get_tuple(self, config): ...
    def list(self, config, *, filter, before, limit): ...
```

**Pending Writes:** незавершённые записи сохраняются для возобновления без повторного выполнения.

---

## Паттерны

### User profile accumulation

```python
@entrypoint(checkpointer=checkpointer, store=store)
def chat(message: str, *, config, store):
    user_id = config["configurable"]["user_id"]

    # Загрузить профиль
    profile = store.get(("profiles",), user_id)
    preferences = profile.value if profile else {}

    # Обработать
    response = model.invoke([
        SystemMessage(f"User prefs: {preferences}"),
        HumanMessage(message)
    ])

    # Обновить профиль при необходимости
    if "preference" in message.lower():
        store.put(("profiles",), user_id, {
            **preferences, "last_updated": datetime.now().isoformat()
        })

    return response
```

### Thread cleanup

```python
# Удалить thread (все checkpoints)
checkpointer.delete_thread(config)
```

---

## Антипаттерны

| Ошибка | Решение |
|--------|---------|
| InMemorySaver в production | PostgresSaver / RedisSaver |
| Не вызвать `.setup()` для DB | `checkpointer.setup()` при старте |
| Store без semantic search | Добавить `index={...}` с embeddings |
| Неограниченная история | `trim_messages` или `SummarizationMiddleware` |
| Checkpointer на child subgraph | Только на parent (child наследует) |
| Хранить секреты без шифрования | `EncryptedSerializer` |

---

**Источники:** Lang Graph/Возможности/ — 4 файла (Упорство, Память, Надежное исполнение, Используйте путешествия во времени)
