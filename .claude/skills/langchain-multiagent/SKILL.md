---
name: langchain-multiagent
description: "Многоагентные паттерны LangChain: субагенты (supervisor), передача прав (handoffs), навыки (skills), маршрутизатор (router), настраиваемые рабочие процессы. Триггеры: 'multi-agent', 'многоагентный', 'subagents langchain', 'supervisor pattern', 'handoff', 'передача прав', 'agent handoff', 'router pattern', 'маршрутизатор агентов', 'skills pattern', 'навыки агента', 'multi-agent workflow', 'координация агентов', 'agent coordination', 'dispatch agent', 'agent delegation', 'agent team', 'parallel agents', 'sequential agents', 'agent composition'. НЕ для create_agent/@tool — используй langchain-core. НЕ для StateGraph/edges — используй langgraph-core."
---

# LangChain Multi-Agent Patterns

## Выбор паттерна

| Паттерн | Когда | Параллелизм | State | Calls (1 запрос) |
|---------|-------|------------|-------|-----------------|
| **Subagents** | Распределённые команды, изоляция | + | Stateless | 4 |
| **Handoffs** | Многошаговые диалоги, последовательные этапы | - | Stateful | 3 |
| **Skills** | Один агент + много специализаций | - | Accumulates | 3 |
| **Router** | Классификация → маршрутизация | + | Stateless | 3 |
| **Custom Workflow** | Детерминистик + агентик гибрид | +/- | Full control | Variable |

### Быстрый выбор

- Нужен параллелизм? → **Subagents** или **Router**
- Многошаговый диалог? → **Handoffs**
- Независимая разработка команд? → **Skills** или **Subagents**
- Простая классификация? → **Router**
- Полный контроль потока? → **Custom Workflow**

---

## Паттерн 1: Subagents (Supervisor)

Мастер-агент координирует подагентов через tool calls.

```python
from langchain.tools import tool
from langchain.agents import create_agent

# 1. Специализированные агенты
research_agent = create_agent(
    model="gpt-4.1",
    tools=[search_docs, fetch_data],
    system_prompt="You are a research specialist"
)

writer_agent = create_agent(
    model="gpt-4.1",
    tools=[write_content],
    system_prompt="You are a writing specialist"
)

# 2. Обёртки как tools
@tool("research", description="Research a topic")
def call_research(query: str):
    result = research_agent.invoke(
        {"messages": [{"role": "user", "content": query}]}
    )
    return result["messages"][-1].content

@tool("write", description="Write content")
def call_writer(content: str):
    result = writer_agent.invoke(
        {"messages": [{"role": "user", "content": content}]}
    )
    return result["messages"][-1].content

# 3. Supervisor
supervisor = create_agent(
    model="gpt-4.1",
    tools=[call_research, call_writer],
    system_prompt="Coordinate research and writing teams"
)
```

### Single Dispatch Tool (для масштабируемых команд)

```python
SUBAGENTS = {
    "research": research_agent,
    "writer": writer_agent,
    "reviewer": reviewer_agent
}

@tool
def task(agent_name: str, description: str) -> str:
    """Execute task by registered subagent."""
    agent = SUBAGENTS[agent_name]
    result = agent.invoke(
        {"messages": [{"role": "user", "content": description}]}
    )
    return result["messages"][-1].content
```

### Параллельный dispatch через Send

```python
from langgraph.types import Send

def route_to_agents(state):
    return [
        Send("research_node", {"query": f"Research: {state['query']}"}),
        Send("data_node", {"query": f"Data for: {state['query']}"}),
    ]
# Все выполняются параллельно
```

### State update из подагента

```python
from langgraph.types import Command

@tool
def research_with_state(query: str, runtime: ToolRuntime) -> Command:
    result = research_agent.invoke(...)
    return Command(update={
        "last_research": result["messages"][-1].content,
        "research_complete": True
    })
```

---

## Паттерн 2: Handoffs (Передача прав)

Агент передаёт управление через state-переменную `current_step`.

```python
from langchain.agents import AgentState, create_agent
from langchain.tools import tool, ToolRuntime
from langchain.messages import ToolMessage
from langgraph.types import Command

class SupportState(AgentState):
    current_step: str = "triage"
    warranty_status: str | None = None

# Инструмент обновляет state → триггерит переход
@tool
def record_warranty(status: str, runtime: ToolRuntime) -> Command:
    return Command(update={
        "messages": [ToolMessage(
            content=f"Warranty: {status}",
            tool_call_id=runtime.tool_call_id
        )],
        "warranty_status": status,
        "current_step": "classify_issue"  # Transition!
    })

# Middleware меняет поведение по current_step
@wrap_model_call
def apply_step_config(request: ModelRequest, handler):
    step = request.state.get("current_step", "triage")
    configs = {
        "triage": {
            "prompt": "Gather warranty info. Use record_warranty.",
            "tools": [record_warranty]
        },
        "classify_issue": {
            "prompt": "Classify the issue type.",
            "tools": [record_issue_type]
        },
        "solution": {
            "prompt": "Provide solution based on warranty and issue.",
            "tools": [provide_solution, escalate]
        }
    }
    config = configs[step]
    return handler(request.override(
        system_prompt=config["prompt"], tools=config["tools"]
    ))
```

### Multi-Agent Handoff (отдельные агенты как ноды)

```python
@tool
def transfer_to_support(runtime: ToolRuntime) -> Command:
    last_ai = next(m for m in reversed(runtime.state["messages"])
                   if isinstance(m, AIMessage))
    return Command(
        goto="support_agent",
        update={
            "active_agent": "support",
            "messages": [last_ai, ToolMessage(
                content="Transferred", tool_call_id=runtime.tool_call_id
            )]
        },
        graph=Command.PARENT
    )
```

**Контекст при передаче:** передавай только пару (last AI message + ToolMessage), НЕ всю историю подагента.

---

## Паттерн 3: Skills (Навыки)

Один агент динамически загружает специализированные промпты.

```python
SKILLS = {
    "sql_expert": {
        "description": "SQL queries and optimization",
        "prompt": "You are a SQL expert. Use standard SQL, optimize...",
        "tools": [execute_sql, test_query]
    },
    "data_analyst": {
        "description": "Data analysis and visualization",
        "prompt": "You are a data analyst. Find patterns...",
        "tools": [load_data, plot_data]
    }
}

@tool
def load_skill(skill_name: str) -> str:
    """Load specialized skill context."""
    if skill_name not in SKILLS:
        return f"Available: {list(SKILLS.keys())}"
    skill = SKILLS[skill_name]
    return f"Loaded: {skill['description']}\n\n{skill['prompt']}"

agent = create_agent(
    model="gpt-4.1",
    tools=[load_skill, execute_sql, load_data],
    system_prompt="Load appropriate skill first, then proceed."
)
```

**Внимание:** Skills накапливают контекст (все загруженные промпты остаются в истории). При длинных диалогах — высокий расход токенов.

---

## Паттерн 4: Router (Маршрутизатор)

Классификация → маршрутизация к агентам → синтез результатов.

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from pydantic import BaseModel, Field

# 1. Классификация
class QueryClass(BaseModel):
    domain: str = Field(description="One of: technical, billing, account")

def classify(state):
    classifier = model.with_structured_output(QueryClass)
    result = classifier.invoke(state["query"])
    return {"classification": result.domain}

# 2. Маршрутизация
def route(state):
    domain = state["classification"]
    return Send(f"{domain}_agent", {"query": state["query"]})

# 3. Синтез
def synthesize(state):
    results = "\n".join(f"{k}: {v}" for k, v in state["results"].items())
    final = model.invoke(f"Combine:\n{results}\n\nOriginal: {state['query']}")
    return {"final_answer": final.content}

# 4. Граф
builder = StateGraph(State)
builder.add_node("classify", classify)
builder.add_node("tech_agent", call_tech)
builder.add_node("billing_agent", call_billing)
builder.add_node("synthesize", synthesize)
builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route,
    ["tech_agent", "billing_agent"])
builder.add_edge("tech_agent", "synthesize")
builder.add_edge("billing_agent", "synthesize")
builder.add_edge("synthesize", END)
```

**Stateless vs Stateful:** Router по умолчанию stateless. Для multi-turn оберни в агент как tool.

---

## Паттерн 5: Custom Workflow

Детерминистическая логика + агентное мышление через LangGraph.

```python
# RAG с Query Rewriting
def rewrite_query(state):
    rewritten = model.with_structured_output(RewrittenQuery).invoke(state["query"])
    return {"rewritten_query": rewritten.query}

def retrieve(state):
    docs = vector_store.similarity_search(state["rewritten_query"], k=5)
    return {"documents": [d.page_content for d in docs]}

def answer(state):
    context = "\n\n".join(state["documents"])
    response = agent.invoke({"messages": [{
        "role": "user",
        "content": f"Context:\n{context}\n\nQuestion: {state['query']}"
    }]})
    return {"answer": response["messages"][-1].content}

workflow = StateGraph(State)
workflow.add_node("rewrite", rewrite_query)    # LLM
workflow.add_node("retrieve", retrieve)        # Deterministic
workflow.add_node("answer", answer)            # Agent
workflow.add_edge(START, "rewrite")
workflow.add_edge("rewrite", "retrieve")
workflow.add_edge("retrieve", "answer")
workflow.add_edge("answer", END)
```

---

## Context Engineering

### Три типа контекста

| Тип | Область | Обновление | Пример |
|-----|---------|-----------|--------|
| **Model Context** | Один LLM-вызов | `middleware` | Dynamic prompt, tool selection |
| **Tool Context** | Tools read/write | `Command.update` | State, Store |
| **Lifecycle Context** | Между шагами | Hooks | Summarization, logging |

### Dynamic prompt по состоянию

```python
@dynamic_prompt
def state_aware_prompt(request: ModelRequest) -> str:
    base = "You are a helpful assistant."
    if len(request.messages) > 10:
        base += "\nBe brief — long conversation."
    if request.state.get("authenticated"):
        base += "\nUser has premium access."
    return base
```

### Dynamic tool selection

```python
@wrap_model_call
def filter_tools_by_role(request: ModelRequest, handler):
    role = request.runtime.context.user_role
    if role != "admin":
        tools = [t for t in request.tools if "read" in t.name]
        request = request.override(tools=tools)
    return handler(request)
```

---

## Антипаттерны

| Ошибка | Последствие | Решение |
|--------|------------|---------|
| Передавать полную историю подагента | Путает принимающего агента | Только пару: last AI + ToolMessage |
| Слишком много tools на одном агенте | Model paralysis | Разделить по Skills или Subagents |
| Skills без контроля токенов | Раздутый контекст | Мониторить usage, summarize |
| Stateless router для диалогов | Потеря контекста | Обернуть в agent с checkpointer |
| Синхронные subagents для тяжёлых задач | Таймаут supervisor | Async + job tracking |

---

## Сравнение производительности

### One-shot запрос

| Паттерн | LLM Calls | Токены |
|---------|-----------|--------|
| Handoffs | 3 | ~6K |
| Skills | 3 | ~6K |
| Router | 3 | ~6K |
| Subagents | 4 | ~8K |

### Повторный запрос (2 подряд)

| Паттерн | LLM Calls | Токены | Причина |
|---------|-----------|--------|---------|
| Handoffs | 3+2=5 | ~10K | State сохраняется |
| Skills | 3+2=5 | ~10K | Skill загружен |
| Subagents | 4+4=8 | ~16K | Stateless, заново |
| Router | 3+3=6 | ~12K | Нет state |

### Multi-domain (3 домена по ~2K токенов)

| Паттерн | LLM Calls | Токены | Причина |
|---------|-----------|--------|---------|
| Subagents | 5 | ~9K | Параллельно + изоляция |
| Router | 5 | ~9K | Параллельно |
| Handoffs | 7+ | ~14K+ | Последовательно |
| Skills | 3 | ~15K | Все skills загружены |

---

**Источники:** Lang Chain/Расширенное использование/Многоагентный/ — 6 файлов (Многоагентный, Субагенты, Передача прав, Навыки, Маршрутизатор, Настраиваемый рабочий процесс) + Контекстная инженерия, Человек в процессе
