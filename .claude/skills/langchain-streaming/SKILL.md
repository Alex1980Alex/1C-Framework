---
name: langchain-streaming
description: "Стриминг LangChain/LangGraph (stream_mode, astream_events). ТОЛЬКО при: stream_mode values/messages/updates/custom/debug, SSE langchain, StreamWriter, get_stream_writer, useStream React, token streaming langgraph, disable_streaming. НЕ для create_agent (→ langchain-core), НЕ для StateGraph (→ langgraph-core), НЕ для 1С, НЕ для Claude Code."
---

# Streaming (LangChain + LangGraph)

## 5 режимов stream_mode

| Режим | Что возвращает | Когда использовать |
|-------|---------------|-------------------|
| `values` | Полный state после каждого шага | Простые pipelines |
| `updates` | Дельта state (изменения) | Отслеживание прогресса |
| `messages` | Токены + метаданные от LLM | Печать по токенам |
| `custom` | Произвольные данные от `StreamWriter` | Progress bars, промежуточные результаты |
| `debug` | Полная debug-информация | Отладка |

---

## Базовое использование

### State updates (прогресс)

```python
for chunk in graph.stream(inputs, stream_mode="updates"):
    node_name = list(chunk.keys())[0]
    state_update = chunk[node_name]
    print(f"[{node_name}] → {state_update}")
```

### Token streaming (посимвольный вывод)

```python
for msg, metadata in graph.stream(inputs, stream_mode="messages"):
    if isinstance(msg, AIMessageChunk) and msg.content:
        print(msg.content, end="", flush=True)
```

### Custom data (произвольные события)

```python
from langgraph.config import get_stream_writer

def my_node(state):
    writer = get_stream_writer()
    writer({"type": "progress", "step": 1, "total": 5})
    # ... work ...
    writer({"type": "progress", "step": 5, "total": 5})
    return {"result": "done"}

for chunk in graph.stream(inputs, stream_mode="custom"):
    print(f"Event: {chunk}")
```

### Мультирежим

```python
for mode, chunk in graph.stream(inputs, stream_mode=["updates", "custom"]):
    if mode == "updates":
        print(f"State: {chunk}")
    elif mode == "custom":
        print(f"Custom: {chunk}")
```

---

## Custom streaming из tools

```python
from langchain.tools import tool, ToolRuntime

@tool
def search_docs(query: str, runtime: ToolRuntime) -> str:
    """Search with progress updates."""
    writer = runtime.stream_writer
    writer(f"Searching for: {query}")
    results = db.search(query)
    writer(f"Found {len(results)} results")
    return "\n".join(results)
```

---

## Streaming подграфов

```python
# Видеть ноды внутри подграфов
for namespace, chunk in graph.stream(inputs, subgraphs=True):
    if namespace:
        print(f"Subgraph [{namespace}]: {chunk}")
    else:
        print(f"Parent: {chunk}")
```

---

## Фильтрация

### По тегам

```python
# Только конкретные ноды
for chunk in graph.stream(inputs, stream_mode="messages"):
    msg, metadata = chunk
    if "important" in metadata.get("tags", []):
        print(msg.content)
```

### По имени ноды

```python
for chunk in graph.stream(inputs, stream_mode="updates"):
    if "llm_node" in chunk:
        print(chunk["llm_node"])
```

---

## Отключение стриминга

```python
# На уровне модели
model = ChatOpenAI(model="gpt-4", streaming=False)

# На уровне ноды
graph.add_node("no_stream_node", func, metadata={"disable_streaming": True})
```

---

## Frontend: React useStream

```bash
npm install @langchain/langgraph-sdk
```

### Базовое использование

```typescript
import { useStream } from "@langchain/langgraph-sdk/react";

function Chat() {
  const stream = useStream({
    assistantId: "my-agent",
    apiUrl: "http://localhost:2024",
    messagesKey: "messages",
    throttle: 50,  // ms между обновлениями UI
  });

  return (
    <div>
      {stream.messages.map(m => <Message key={m.id} msg={m} />)}
      {stream.isLoading && <Spinner />}
      {stream.error && <Error msg={stream.error} />}

      <Input onSubmit={(text) =>
        stream.submit({
          messages: [{ role: "user", content: text }]
        })
      } />
    </div>
  );
}
```

### Ключевые свойства useStream

| Свойство | Тип | Назначение |
|----------|-----|-----------|
| `messages` | `Message[]` | Текущие сообщения |
| `values` | `State` | Текущий state графа |
| `isLoading` | `boolean` | В процессе выполнения |
| `error` | `Error?` | Ошибка |
| `interrupt` | `Interrupt?` | Прерывание (HITL) |
| `toolCalls` | `ToolCall[]` | Активные tool calls |
| `submit(input)` | function | Отправить сообщение |
| `stop()` | function | Остановить выполнение |
| `setBranch(config)` | function | Переключить ветку (time travel) |

### Thread persistence (сессии)

```typescript
const [threadId, setThreadId] = useState<string | undefined>();

const stream = useStream({
  assistantId: "my-agent",
  threadId,
  onThreadId: setThreadId,  // Сохраняет при создании
  reconnectOnMount: true,   // Восстанавливает при обновлении страницы
});
```

### Optimistic updates

```typescript
stream.submit(
  { messages: [{ role: "user", content: text }] },
  {
    optimisticValues: (prev) => ({
      ...prev,
      messages: [...prev.messages, { role: "user", content: text }]
    })
  }
);
```

### Human-in-the-Loop (прерывания)

```typescript
if (stream.interrupt) {
  const { value } = stream.interrupt;

  // Одобрить
  stream.submit(Command.resume({ decision: "approve" }));

  // Отклонить
  stream.submit(Command.resume({ decision: "reject", reason: "..." }));

  // Редактировать
  stream.submit(Command.resume({ decision: "edit", args: {...} }));
}
```

### Branching (time travel)

```typescript
// Переключиться на другую ветку
stream.setBranch({
  messageId: "msg_123",
  branchIndex: 1  // Альтернативная ветка
});
```

### Tool call rendering

```typescript
const toolCalls = stream.getToolCalls();
for (const tc of toolCalls) {
  // tc.name, tc.args, tc.result
  render(<ToolCard call={tc} />);
}
```

### Custom events

```typescript
const stream = useStream({
  assistantId: "my-agent",
  onCustomEvent: (data) => {
    // data = то что отправлено через StreamWriter
    updateProgressBar(data.step, data.total);
  },
  onUpdateEvent: (data) => {
    console.log("State updated:", data);
  },
});
```

### Multi-agent streaming

```typescript
// Определить какой агент сгенерировал сообщение
const metadata = stream.getMessagesMetadata();
for (const [msgId, meta] of Object.entries(metadata)) {
  console.log(`${msgId}: from ${meta.lc_agent_name}`);
}
```

---

## SSE (Server-Sent Events) — для LangGraph Server

```python
# Серверная сторона — LangGraph Server обслуживает автоматически
# Клиентская сторона:
import httpx

async with httpx.AsyncClient() as client:
    async with client.stream("POST", "http://localhost:2024/runs/stream", json={
        "assistant_id": "agent",
        "input": {"messages": [{"role": "user", "content": "Hello"}]},
        "stream_mode": ["messages", "updates"]
    }) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                print(data)
```

---

## Async streaming (Python)

```python
async for chunk in graph.astream(inputs, stream_mode="messages"):
    msg, metadata = chunk
    if isinstance(msg, AIMessageChunk):
        print(msg.content, end="")
```

**Python < 3.11:** передавай config явно через `get_stream_writer(config)`.

---

## Антипаттерны

| Ошибка | Решение |
|--------|---------|
| Стримить `values` для больших states | Используй `updates` (только дельты) |
| Не проверять тип message в `messages` | Фильтруй `isinstance(msg, AIMessageChunk)` |
| Забыть `flush=True` при print | `print(token, end="", flush=True)` |
| Стримить всё без фильтрации | Фильтруй по tags или node name |
| Не указать `throttle` в useStream | UI дёргается, задать 50-100ms |

---

**Источники:** Lang Chain/Стриминг/ — 2 файла (Обзор, Внешний интерфейс) + Lang Graph/Возможности/Стриминг.md
