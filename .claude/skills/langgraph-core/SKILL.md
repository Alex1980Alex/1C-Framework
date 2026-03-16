---
name: langgraph-core
description: "LangGraph v0.2 ядро (import langgraph). ТОЛЬКО при: StateGraph, add_node/add_edge, conditional_edges, @entrypoint/@task, Command/Send, interrupt, subgraph, MessagesState, Pregel, recursion_limit. НЕ для LangChain agents (→ langchain-core), НЕ для стриминга (→ langchain-streaming), НЕ для checkpointers/Store (→ langgraph-memory-persistence), НЕ для LangSmith/deploy (→ langgraph-production), НЕ для 1С."
---

# LangGraph Core

## Установка

```bash
pip install -U langgraph
pip install -U langchain              # Опционально: LLM-интеграция
pip install -U langchain-anthropic    # Провайдер
```
Python 3.10+.

## Два API: Graph vs Functional

| Аспект | Graph API | Functional API |
|--------|-----------|----------------|
| Сложные деревья решений | `conditional_edges` | if/else вручную |
| Параллелизм | Несколько START-edges | Task futures |
| Визуализация | `.get_graph().draw_mermaid_png()` | Нет (динамический граф) |
| Командная разработка | Чёткие ответственности нод | Линейный поток |
| Существующий код | Требует рефакторинга | Минимальные изменения |

Оба API используют один runtime. Можно комбинировать.

---

## Graph API

### Минимальный пример

```python
from langgraph.graph import StateGraph, MessagesState, START, END

graph = StateGraph(MessagesState)
graph.add_node("llm_call", llm_call_fn)
graph.add_node("tool_node", tool_node_fn)
graph.add_edge(START, "llm_call")
graph.add_conditional_edges("llm_call", should_continue, {"tool_node": "tool_node", END: END})
graph.add_edge("tool_node", "llm_call")
agent = graph.compile()
agent.invoke({"messages": [HumanMessage("Hello")]})
```

### State — TypedDict с reducers

```python
from typing import Annotated
import operator

class State(TypedDict):
    foo: int                                          # Перезаписывается
    bar: Annotated[list[str], operator.add]           # Accumulator (append)
    messages: Annotated[list[AnyMessage], add_messages]  # Message reducer (handles IDs)
```

**Варианты state:** TypedDict (без defaults) | dataclass (с defaults) | Pydantic BaseModel

**Разные schema для input/output:**
```python
StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)
```

### Nodes — функции (state) → dict update

```python
def my_node(state: State) -> dict:
    return {"foo": state["foo"] + 1}  # Частичное обновление

def my_node_with_config(state: State, config: RunnableConfig) -> dict:
    thread_id = config["configurable"]["thread_id"]
    return {"foo": 42}
```

### Edges — статические, условные, динамические

```python
# Статический
graph.add_edge("node_a", "node_b")

# Условный (routing function)
def route(state) -> Literal["node_b", "__end__"]:
    return "node_b" if state["needs_more"] else END

graph.add_conditional_edges("node_a", route, {"node_b": "node_b", END: END})

# Параллелизм (несколько edges от START)
graph.add_edge(START, "fetch_news")
graph.add_edge(START, "fetch_weather")
graph.add_edge(START, "fetch_stocks")
# Все запускаются параллельно
```

### Command — обновление + маршрутизация в одном

```python
from langgraph.types import Command

def my_node(state) -> Command[Literal["next_node"]]:
    return Command(update={"key": "value"}, goto="next_node")
```

### Send — динамическая диспетчеризация (map-reduce)

```python
from langgraph.types import Send

def orchestrator(state):
    return {"sections": planner.invoke(...)}

def assign_workers(state):
    return [Send("worker", {"section": s}) for s in state["sections"]]

graph.add_conditional_edges("orchestrator", assign_workers, ["worker"])
```

---

## Functional API

### Минимальный пример

```python
from langgraph.func import entrypoint, task
from langgraph.checkpoint.memory import InMemorySaver

@task
def slow_computation(x: int) -> int:
    return x * 2

@entrypoint(checkpointer=InMemorySaver())
def workflow(x: int) -> dict:
    result = slow_computation(x).result()  # .result() дожидается
    return {"result": result}

config = {"configurable": {"thread_id": "my-thread"}}
workflow.invoke(5, config)
```

### Инъекция параметров

```python
@entrypoint(checkpointer=checkpointer, store=store)
def workflow(input_data: dict, *,
             previous=None,           # Предыдущее состояние из checkpoint
             store: BaseStore,        # Долговременная память
             writer: StreamWriter,    # Custom streaming
             config: RunnableConfig): # thread_id, tags...
```

### Short-term memory через previous

```python
@entrypoint(checkpointer=checkpointer)
def accumulate(n: int, *, previous: int | None = None) -> int:
    total = (previous or 0) + n
    return entrypoint.final(value=previous, save=total)
```

### Политики retry и cache

```python
@task(retry_policy=RetryPolicy(retry_on=ValueError, max_attempts=3))
def risky_call(data): ...

@task(cache_policy=CachePolicy(ttl=120))
def expensive_call(query): ...

# Cache требует compile с InMemoryCache
graph = builder.compile(cache=InMemoryCache())
```

---

## Подграфы (Subgraphs)

### Подход 1: Вызов из ноды (изолированное состояние)

```python
def parent_node(state):
    result = subgraph.invoke({"subgraph_key": state["parent_key"]})
    return {"parent_key": result["subgraph_key"]}  # Маппинг обратно
```

### Подход 2: Добавить как ноду (общее состояние)

```python
parent_builder.add_node("subgraph_node", compiled_subgraph)
```

**Persistence:** Checkpointer только на parent — дети наследуют.
**Независимая память:** `compile(checkpointer=True)` для child.
**Streaming:** `stream(..., subgraphs=True)` видит ноды подграфа.

---

## Прерывания (Interrupts)

```python
from langgraph.types import interrupt, Command

def approval_node(state) -> Command[Literal["proceed", "cancel"]]:
    decision = interrupt({"question": "Approve?", "details": state["action"]})
    return Command(goto="proceed" if decision else "cancel")

# Запуск
config = {"configurable": {"thread_id": "t1"}}
result = graph.invoke({"action": "..."}, config)
print(result["__interrupt__"])  # Пользователь видит payload

# Возобновление
graph.invoke(Command(resume=True), config)
```

### Паттерны interrupt

| Паттерн | Код |
|---------|-----|
| Approve/Reject | `interrupt({"q": "OK?"})` → `Command(goto=...)` |
| Review & Edit | `edited = interrupt({"content": draft})` → `return {"draft": edited}` |
| Tool verification | `interrupt({"tool_call": tc})` → approve/feedback |
| Input validation | `while True: answer = interrupt("Enter age:")` |

### Правила interrupt

- Размещать `interrupt()` ДО side effects (idempotent ops before)
- НЕ оборачивать в try/except
- НЕ вызывать условно (меняет индексы при resume)
- Payload должен быть JSON-serializable

---

## Durable Execution

### Включение

```python
checkpointer = InMemorySaver()  # Dev: in-memory; Prod: PostgresSaver
graph = builder.compile(checkpointer=checkpointer)
config = {"configurable": {"thread_id": "my-thread"}}
graph.invoke(inputs, config)
```

### Режимы durability

| Режим | Checkpoint | Риск | Производительность |
|-------|-----------|------|-------------------|
| `exit` | В конце | Потеря при crash mid-execution | Лучшая |
| `async` | После следующего шага | Маленькое окно потерь | Средняя |
| `sync` | До следующего шага | Минимальный | Overhead |

```python
graph.stream(inputs, durability="sync")
```

### Возобновление

```python
# После interrupt
graph.invoke(Command(resume=value), config)

# После ошибки (перезапуск с последнего superstep)
graph.invoke(None, config)
```

---

## Time Travel

```python
# 1. Запуск
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
state = graph.invoke({}, config)

# 2. История
states = list(graph.get_state_history(config))
selected = states[2]  # Выбрать прошлый checkpoint

# 3. Модификация (опционально)
new_config = graph.update_state(selected.config, values={"topic": "chickens"})

# 4. Воспроизведение
graph.invoke(None, new_config)
```

---

## Pregel Runtime (low-level)

| Channel | Назначение |
|---------|-----------|
| `LastValue` | Хранит последнее значение (default для state keys) |
| `Topic` | PubSub с аккумуляцией |
| `EphemeralValue` | Одноразовый input/output |
| `BinaryOperatorAggregate` | Fold/reduce |

```python
from langgraph.pregel import Pregel, NodeBuilder
from langgraph.channels import LastValue, EphemeralValue

node1 = (NodeBuilder().subscribe_only("input").do(lambda x: x * 2).write_to("output"))
app = Pregel(
    nodes={"node1": node1},
    channels={"input": EphemeralValue(str), "output": LastValue(str)},
    input_channels=["input"], output_channels=["output"]
)
```

---

## Паттерны проектирования

### 5 шагов LangGraph-мышления

1. **Спланировать workflow** — нарисовать на бумаге
2. **Определить типы нод** — LLM / Data / Action / User input
3. **Спроектировать state** — raw data, NOT formatted text
4. **Реализовать ноды** — каждая делает одно
5. **Соединить edges** — static → conditional → dynamic

### Error handling по типам

| Тип ошибки | Обработка |
|-----------|----------|
| Network/Timeout | `RetryPolicy(max_attempts=3, initial_interval=1.0)` |
| Tool/Parsing | Сохранить в state → `Command(update={"error": str(e)}, goto="retry")` |
| User Input | `interrupt("Clarify?")` |
| Unexpected | Пусть поднимается (для debug) |

### Node caching

```python
builder.add_node("expensive", func, cache_policy=CachePolicy(ttl=3))
```

### Recursion limit

```python
graph.invoke(inputs, config={"recursion_limit": 5})
```

---

## Ключевые классы

| Класс/Функция | Import | Назначение |
|---------------|--------|-----------|
| `StateGraph` | `langgraph.graph` | Строитель графа (OOP) |
| `@entrypoint` | `langgraph.func` | Вход workflow (процедурный) |
| `@task` | `langgraph.func` | Единица работы с checkpointing |
| `interrupt()` | `langgraph.types` | Пауза для human input |
| `Command` | `langgraph.types` | State update + routing |
| `Send` | `langgraph.types` | Dynamic dispatch (map-reduce) |
| `add_messages` | `langgraph.graph.message` | Message reducer |
| `MessagesState` | `langgraph.graph` | Built-in state для чатов |
| `InMemorySaver` | `langgraph.checkpoint.memory` | Dev checkpointer |

---

**Источники:** Lang Chain Docs/Lang Graph/ — 17 файлов (Обзор, Установка, Быстрый старт, Мышление, Рабочие процессы, Graph API (3), Functional API (2), Среда выполнения, Подграфы, Прерывания, Надёжное исполнение, Time Travel, Упорство, Локальный сервер)
