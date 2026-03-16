---
name: langchain-core
description: "LangChain v0.3 ядро (import langchain). ТОЛЬКО при: create_agent, @tool decorator, init_chat_model, SystemMessage/HumanMessage/AIMessage, middleware before_model/after_model, structured output langchain, guardrails, HumanInTheLoopMiddleware. НЕ для LangGraph StateGraph (→ langgraph-core), НЕ для vector stores/loaders (→ langchain-integrations), НЕ для стриминга (→ langchain-streaming), НЕ для 1С, НЕ для Claude Code."
---

# LangChain Core

## Установка

```bash
pip install -U langchain
pip install -U langchain-anthropic   # или langchain-openai, langchain-google-genai
```
Python 3.10+ обязателен. Провайдеры ставятся отдельными пакетами.

## create_agent — точка входа

```python
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

model = init_chat_model("claude-sonnet-4-5-20250929", temperature=0.7, max_tokens=1000, timeout=30)

agent = create_agent(
    model=model,
    tools=[get_weather, search_db],
    system_prompt="You are a helpful assistant",
    context_schema=Context,                    # Опционально: типизация контекста
    response_format=ToolStrategy(ResponseFormat), # Опционально: структурированный вывод
    checkpointer=InMemorySaver(),              # Опционально: память
    middleware=[LoggingMiddleware()],           # Опционально: middleware
    state_schema=CustomAgentState              # Опционально: расширение состояния
)

config = {"configurable": {"thread_id": "1"}}
result = agent.invoke({"messages": [{"role": "user", "content": "Hello"}]}, config)
```

## Инструменты (@tool)

### Базовый инструмент

```python
from langchain.tools import tool

@tool
def search_database(query: str, limit: int = 10) -> str:
    """Search customer database for records matching query.
    Args:
        query: Search query
        limit: Max results
    """
    return f"Found {limit} results for '{query}'"
```

### ToolRuntime — доступ к контексту, store, stream

```python
from langchain.tools import tool, ToolRuntime

@tool
def fetch_user_info(runtime: ToolRuntime[Context]) -> str:
    """Get user info from context and store."""
    user_id = runtime.context.user_id        # Static context
    if runtime.store:                         # Cross-session memory
        if mem := runtime.store.get(("users",), user_id):
            return mem.value["preferences"]
    return "Default preferences"
```

### Обновление состояния агента из tool

```python
from langgraph.types import Command
from langchain.messages import RemoveMessage, REMOVE_ALL_MESSAGES

@tool
def update_user_name(new_name: str, runtime: ToolRuntime) -> Command:
    """Update user name in state."""
    return Command(update={"user_name": new_name})

@tool
def clear_conversation() -> Command:
    """Clear conversation history."""
    return Command(update={"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]})
```

### stream_writer в инструментах

```python
@tool
def get_weather(city: str, runtime: ToolRuntime) -> str:
    writer = runtime.stream_writer
    writer(f"Fetching data for: {city}")
    return f"In {city} it's sunny!"
```

## Модели

### Инициализация

```python
from langchain.chat_models import init_chat_model

model = init_chat_model(
    "claude-sonnet-4-5-20250929",
    temperature=0.7,    # 0 = deterministic, 1+ = creative
    max_tokens=1000,
    timeout=30,
    max_retries=3
)
```

### invoke / stream / batch

```python
response = model.invoke("Question?")                     # Single
for chunk in model.stream("Question?"):                   # Streaming
    print(chunk.text, end="", flush=True)
responses = model.batch(["Q1", "Q2", "Q3"])               # Batch
for r in model.batch_as_completed(inputs, config={"max_concurrency": 5}):  # Parallel batch
    print(r)
```

### Tool calling

```python
model_with_tools = model.bind_tools([get_weather])
response = model_with_tools.invoke("Weather in Boston?")
for tc in response.tool_calls:
    print(f"Tool: {tc['name']}, Args: {tc['args']}")
```

### Structured output на уровне модели

```python
class Movie(BaseModel):
    title: str = Field(..., description="Movie title")
    year: int
    director: str

model_structured = model.with_structured_output(Movie)
movie = model_structured.invoke("Tell me about Inception")
# Movie(title="Inception", year=2010, director="Nolan")
```

## Сообщения

```python
from langchain.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

messages = [
    SystemMessage("You are a poetry expert"),
    HumanMessage("Write haiku about spring"),
    AIMessage("Blossoms fall softly..."),
    ToolMessage(content="Result", tool_call_id="call_123", name="search")
]
```

### Мультимодальный контент

```python
# Изображение
HumanMessage(content=[
    {"type": "text", "text": "Describe this image"},
    {"type": "image", "url": "https://example.com/image.jpg"}
])

# PDF
HumanMessage(content=[
    {"type": "text", "text": "Analyze document"},
    {"type": "file", "base64": "...", "mime_type": "application/pdf"}
])
```

### Токены

```python
response.usage_metadata  # {'input_tokens': 8, 'output_tokens': 304, 'total_tokens': 312}
```

## Structured Output (на уровне агента)

### ProviderStrategy (нативная поддержка модели)

```python
from langchain.agents.structured_output import ProviderStrategy

agent = create_agent(model="gpt-4.1", response_format=ProviderStrategy(ContactInfo))
result = agent.invoke({"messages": [...]})
print(result["structured_response"])  # ContactInfo(...)
```

### ToolStrategy (через tool calling — более универсальная)

```python
from langchain.agents.structured_output import ToolStrategy

agent = create_agent(model="gpt-4.1", response_format=ToolStrategy(ProductReview))
# Поддержка Union типов:
response_format=ToolStrategy(Union[ContactInfo, EventDetails])
# Обработка ошибок:
response_format=ToolStrategy(schema=ProductReview, handle_errors=True)
```

## Middleware

### Встроенные middleware

| Middleware | Назначение | Ключевые параметры |
|-----------|-----------|-------------------|
| `SummarizationMiddleware` | Сжатие истории | `trigger=("tokens", 4000)`, `keep=("messages", 20)` |
| `HumanInTheLoopMiddleware` | Одобрение действий | `interrupt_on={"tool_name": {"allowed_decisions": [...]}}` |
| `ModelCallLimitMiddleware` | Лимит вызовов модели | `thread_limit=10`, `run_limit=5`, `exit_behavior="end"` |
| `ToolCallLimitMiddleware` | Лимит вызовов tool | `tool_name="search"`, `thread_limit=5` |
| `PIIMiddleware` | Защита PII | `strategy="redact"/"mask"/"hash"/"block"` |
| `ToolRetryMiddleware` | Retry при ошибках | `max_retries=3`, `backoff_factor=2.0` |
| `ModelFallbackMiddleware` | Fallback модель | `"gpt-4.1-mini", "claude-3-5-sonnet"` |

### Custom middleware (декоратор)

```python
from langchain.agents.middleware import before_model, after_model, wrap_model_call

@before_model
def log_before(state: AgentState, runtime: Runtime) -> dict | None:
    print(f"Messages: {len(state['messages'])}")
    return None  # None = no state change

@wrap_model_call
def retry_model(request: ModelRequest, handler: Callable) -> ModelResponse:
    for attempt in range(3):
        try:
            return handler(request)
        except Exception as e:
            if attempt == 2: raise

@wrap_tool_call
def handle_tool_errors(request, handler):
    try:
        return handler(request)
    except Exception as e:
        return ToolMessage(content=f"Error: {e}", tool_call_id=request.tool_call["id"])
```

### Dynamic model/tool selection через middleware

```python
@wrap_model_call
def dynamic_model(request: ModelRequest, handler) -> ModelResponse:
    model = advanced_model if len(request.state["messages"]) > 10 else basic_model
    return handler(request.override(model=model))

@wrap_model_call
def filter_tools(request: ModelRequest, handler) -> ModelResponse:
    role = request.runtime.context.user_role
    tools = request.tools if role == "admin" else [t for t in request.tools if "read" in t.name]
    return handler(request.override(tools=tools))
```

## Runtime — контекст, состояние, store

| Компонент | Тип | Доступ | Назначение |
|-----------|-----|--------|-----------|
| **context** | Static | `runtime.context.user_id` | Конфигурация на время запроса |
| **state** | Mutable | `request.state["key"]` | Состояние агента (messages, custom) |
| **store** | Persistent | `runtime.store.get(ns, key)` | Кросс-сессионная память |

### Dynamic prompts

```python
from langchain.agents.middleware import dynamic_prompt

@dynamic_prompt
def prompt_from_context(request: ModelRequest) -> str:
    return f"You are helpful. User: {request.runtime.context.user_name}"
```

## Guardrails (PII)

```python
PIIMiddleware("email", strategy="redact", apply_to_input=True)
PIIMiddleware("credit_card", strategy="mask", detector=r"\d{4}-\d{4}-\d{4}-\d{4}")

# Custom detector
def detect_ssn(content: str) -> list[dict]:
    return [{"text": m.group(0), "start": m.start(), "end": m.end()}
            for m in re.finditer(r"\d{3}-\d{2}-\d{4}", content)]

PIIMiddleware("ssn", detector=detect_ssn, strategy="hash")
```

Стратегии: `block` | `redact` | `mask` | `hash`

## Human-in-the-Loop

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

agent = create_agent(
    model="gpt-4.1",
    tools=[read_email, send_email],
    checkpointer=InMemorySaver(),
    middleware=[HumanInTheLoopMiddleware(
        interrupt_on={"send_email_tool": {"allowed_decisions": ["approve", "edit", "reject"]},
                      "read_email_tool": False}
    )]
)

# 1. Запуск (прерывается на send_email_tool)
result1 = agent.invoke({"messages": [...]}, config)

# 2. Возобновление с решением
result2 = agent.invoke({
    "messages": result1["messages"],
    "decisions": [{"tool_call_id": "call_123", "decision": "approve"}]
}, config)
```

Решения: `approve` | `edit` (с новыми args) | `reject` (с причиной)

## RAG паттерны

### 2-Step RAG
```python
docs = retriever.invoke(query)
response = model.invoke(f"Answer based on: {docs}\n\nQ: {query}")
```

### Agentic RAG (агент решает когда искать)
```python
@tool
def fetch_documentation(query: str) -> str:
    """Fetch docs for query."""
    return "\n".join([d.page_content for d in retriever.invoke(query)])

agent = create_agent(model="gpt-4.1", tools=[fetch_documentation])
```

---

**Источники:** Lang Chain Docs/Lang Chain/ — 18 файлов (Обзор, Установка, Быстрый старт, Агенты, Инструменты, Модели, Сообщения, Кратковременная память, Структурированный вывод, Middleware (3), Ограждения, Среда выполнения, Контекстная инженерия, Извлечение, Человек в процессе, Философия)
