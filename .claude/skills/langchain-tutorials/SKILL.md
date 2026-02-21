---
name: langchain-tutorials
description: "Туториалы LangChain/LangGraph: RAG Agent, SQL Agent, Voice Agent, Semantic Search, Multi-Agent (субагенты, handoffs, router, skills), Custom RAG/SQL с LangGraph. Триггеры: 'tutorial langchain', 'туториал', 'RAG agent tutorial', 'SQL agent tutorial', 'voice agent', 'semantic search tutorial', 'multi-agent tutorial', 'пример агента', 'agent example', 'LangChain quickstart', 'быстрый старт langchain', 'как построить RAG', 'как построить SQL агента', 'custom RAG agent', 'custom SQL agent', 'пошаговый пример', 'step by step agent'. НЕ для API reference — используй langchain-core/langgraph-core."
---

# LangChain / LangGraph Tutorials

## RAG Agent (LangChain)

Агент с доступом к документации, самостоятельно решает когда искать.

```python
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

# 1. Vector store + retriever
vectorstore = Chroma(
    embedding_function=OpenAIEmbeddings(),
    persist_directory="./docs_db"
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# 2. Tool
@tool
def search_docs(query: str) -> str:
    """Search documentation for relevant information."""
    docs = retriever.invoke(query)
    return "\n\n".join([d.page_content for d in docs])

# 3. Agent
agent = create_agent(
    model="gpt-4.1",
    tools=[search_docs],
    system_prompt=(
        "You answer questions using documentation. "
        "Always search docs before answering."
    )
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "How to configure logging?"}]
})
```

---

## SQL Agent (LangChain)

Агент выполняет SQL-запросы с проверкой и обработкой ошибок.

```python
from langchain.agents import create_agent
from langchain_community.utilities import SQLDatabase
from langchain_community.tools.sql_database.tool import (
    QuerySQLDataBaseTool,
    InfoSQLDatabaseTool,
    ListSQLDatabaseTool,
    QuerySQLCheckerTool
)

# 1. Database
db = SQLDatabase.from_uri("sqlite:///chinook.db")

# 2. Tools
tools = [
    ListSQLDatabaseTool(db=db),          # Список таблиц
    InfoSQLDatabaseTool(db=db),           # Схема таблиц
    QuerySQLCheckerTool(db=db, llm=model),# Проверка SQL
    QuerySQLDataBaseTool(db=db)           # Выполнение SQL
]

# 3. Agent
agent = create_agent(
    model="gpt-4.1",
    tools=tools,
    system_prompt=(
        "You are a SQL expert. Workflow:\n"
        "1. List tables\n"
        "2. Get schema of relevant tables\n"
        "3. Write SQL query\n"
        "4. Check query with checker tool\n"
        "5. Execute query\n"
        "6. Present results"
    )
)
```

### SQL Agent + HITL

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

agent = create_agent(
    model="gpt-4.1",
    tools=tools,
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={"sql_db_query": True}  # Одобрение перед execute
        )
    ],
    checkpointer=InMemorySaver()
)
```

### Безопасность SQL

- **READ-only permissions** на базу данных
- **Checker tool** перед выполнением
- **HITL** для опасных запросов (DELETE, UPDATE)

---

## Semantic Search (LangChain)

Полный pipeline: загрузка → split → embed → search.

```python
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# 1. Load
loader = WebBaseLoader("https://docs.example.com/guide")
docs = loader.load()

# 2. Split
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000, chunk_overlap=200
)
chunks = splitter.split_documents(docs)

# 3. Embed + Store
vectorstore = Chroma.from_documents(
    chunks,
    OpenAIEmbeddings(),
    persist_directory="./search_db"
)

# 4. Search
results = vectorstore.similarity_search("authentication setup", k=3)
for doc in results:
    print(doc.page_content[:200])
```

---

## Custom RAG Agent (LangGraph)

RAG с query rewriting и adaptive retrieval через StateGraph.

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal

class RAGState(TypedDict):
    query: str
    rewritten_query: str
    documents: list[str]
    answer: str
    needs_more: bool

def rewrite_query(state: RAGState) -> dict:
    rewritten = model.invoke(
        f"Rewrite for better search: {state['query']}"
    )
    return {"rewritten_query": rewritten.content}

def retrieve(state: RAGState) -> dict:
    docs = retriever.invoke(state["rewritten_query"])
    return {"documents": [d.page_content for d in docs]}

def generate(state: RAGState) -> dict:
    context = "\n\n".join(state["documents"])
    response = model.invoke(
        f"Context:\n{context}\n\nQuestion: {state['query']}"
    )
    return {"answer": response.content}

def check_quality(state: RAGState) -> Literal["retrieve_more", "done"]:
    if "I don't know" in state["answer"]:
        return "retrieve_more"
    return "done"

builder = StateGraph(RAGState)
builder.add_node("rewrite", rewrite_query)
builder.add_node("retrieve", retrieve)
builder.add_node("generate", generate)

builder.add_edge(START, "rewrite")
builder.add_edge("rewrite", "retrieve")
builder.add_edge("retrieve", "generate")
builder.add_conditional_edges("generate", check_quality, {
    "retrieve_more": "retrieve",
    "done": END
})

rag_agent = builder.compile()
result = rag_agent.invoke({"query": "How to set up auth?"})
```

---

## Custom SQL Agent (LangGraph)

SQL агент с retry loop через граф.

```python
class SQLState(TypedDict):
    query: str
    sql: str
    result: str
    error: str | None
    attempts: int

def generate_sql(state: SQLState) -> dict:
    prompt = f"Write SQL for: {state['query']}"
    if state.get("error"):
        prompt += f"\nPrevious error: {state['error']}"
    sql = model.invoke(prompt)
    return {"sql": sql.content, "attempts": state.get("attempts", 0) + 1}

def execute_sql(state: SQLState) -> dict:
    try:
        result = db.run(state["sql"])
        return {"result": str(result), "error": None}
    except Exception as e:
        return {"result": "", "error": str(e)}

def should_retry(state: SQLState) -> Literal["retry", "respond"]:
    if state.get("error") and state.get("attempts", 0) < 3:
        return "retry"
    return "respond"

builder = StateGraph(SQLState)
builder.add_node("generate", generate_sql)
builder.add_node("execute", execute_sql)
builder.add_node("respond", format_response)

builder.add_edge(START, "generate")
builder.add_edge("generate", "execute")
builder.add_conditional_edges("execute", should_retry, {
    "retry": "generate",
    "respond": "respond"
})
builder.add_edge("respond", END)

sql_agent = builder.compile()
```

---

## Multi-Agent Tutorials

### Subagents (supervisor)

```python
# Координатор делегирует задачи
@tool
def research(query: str) -> str:
    return research_agent.invoke(...)["messages"][-1].content

@tool
def write(content: str) -> str:
    return writer_agent.invoke(...)["messages"][-1].content

supervisor = create_agent(model="gpt-4.1", tools=[research, write])
```

### Handoffs

```python
# Агент передаёт управление через state
@tool
def transfer_to_billing(runtime: ToolRuntime) -> Command:
    return Command(goto="billing_agent", update={"active": "billing"},
                   graph=Command.PARENT)
```

### Router

```python
# Классификация → параллельная обработка → синтез
builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route, ["tech", "billing"])
builder.add_edge("tech", "synthesize")
builder.add_edge("billing", "synthesize")
```

### Skills

```python
# Динамическая загрузка специализированных промптов
@tool
def load_skill(name: str) -> str:
    return SKILLS[name]["prompt"]
```

---

## Voice Agent (LangChain)

Голосовой агент через speech-to-text → LLM → text-to-speech.

```python
# Whisper (speech-to-text) → Agent → TTS
from langchain_community.tools import WhisperTool, TTSTool

agent = create_agent(
    model="gpt-4.1",
    tools=[whisper_tool, tts_tool, search_docs],
    system_prompt="Voice assistant. Listen → Process → Respond with speech."
)
```

---

## Поддерживаемые модели (все tutorials)

| Провайдер | Модель | Пакет |
|-----------|--------|-------|
| OpenAI | gpt-4.1, gpt-5 | `langchain-openai` |
| Anthropic | claude-sonnet-4-5-20250929 | `langchain-anthropic` |
| Google | Gemini | `langchain-google-genai` |
| AWS | Bedrock models | `langchain-aws` |
| HuggingFace | Open models | `langchain-huggingface` |
| Azure | Azure OpenAI | `langchain-openai` |

---

**Источники:** Учиться/ — 10+ файлов (RAG Agent, SQL Agent, Voice Agent, Semantic Search, Multi-Agent tutorials, Custom RAG/SQL, Концептуальные обзоры)
