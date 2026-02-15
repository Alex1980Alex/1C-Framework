> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Создайте собственный SQL-агент с LangGraph

## Обзор

В этом руководстве вы узнаете, как создать полностью настраиваемый SQL-агент с помощью LangGraph. В отличие от готового `create_react_agent`, пользовательский агент даёт полный контроль над логикой маршрутизации, обработкой ошибок и стратегией повторных попыток.

### Что будет делать агент

1. Получить доступные таблицы и схемы из базы данных
2. Определить, какие таблицы относятся к вопросу
3. Получить схемы для релевантных таблиц
4. Сгенерировать SQL-запрос на основе вопроса и схем
5. Проверить запрос на ошибки с помощью LLM
6. Выполнить запрос и получить результаты
7. Исправить ошибки от СУБД до успешного выполнения
8. Сформулировать ответ на основе результатов

<Warning>
  Создание систем вопросов и ответов на основе SQL требует выполнения запросов, сгенерированных моделью. Убедитесь, что права доступа к базе данных максимально ограничены.
</Warning>

## Установка

```bash
pip install langchain langgraph langchain-anthropic langchain-community
```

## Настройка базы данных

```python
from langchain_community.utilities import SQLDatabase

db = SQLDatabase.from_uri("sqlite:///example.db")
print(db.dialect)
print(db.get_usable_table_names())
```

## Определение состояния агента

```python
from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    # Дополнительные ключи для отслеживания SQL-специфичного состояния
    query: str
    result: str
    error: str
    relevant_tables: list[str]
```

## Определение узлов графа

### Узел: получение таблиц

```python
from langchain_core.messages import AIMessage


def get_tables(state: AgentState) -> AgentState:
    """Получить список доступных таблиц из БД."""
    tables = db.get_usable_table_names()
    return {
        "messages": [AIMessage(content=f"Available tables: {', '.join(tables)}")],
    }
```

### Узел: определение релевантных таблиц

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")


def identify_tables(state: AgentState) -> AgentState:
    """Определить какие таблицы относятся к вопросу."""
    tables = db.get_usable_table_names()
    user_question = state["messages"][0].content

    response = llm.invoke(
        f"Given tables: {tables}\n"
        f"Question: {user_question}\n"
        f"Which tables are relevant? Return only table names, comma-separated."
    )

    relevant = [t.strip() for t in response.content.split(",")]
    return {
        "relevant_tables": relevant,
        "messages": [AIMessage(content=f"Relevant tables: {', '.join(relevant)}")],
    }
```

### Узел: получение схем

```python
def get_schema(state: AgentState) -> AgentState:
    """Получить DDL-схемы для релевантных таблиц."""
    tables = state["relevant_tables"]
    schema = db.get_table_info(table_names=tables)
    return {
        "messages": [AIMessage(content=f"Schema:\n{schema}")],
    }
```

### Узел: генерация SQL

```python
def generate_query(state: AgentState) -> AgentState:
    """Сгенерировать SQL-запрос на основе схемы и вопроса."""
    messages = state["messages"]

    response = llm.invoke([
        ("system", "Generate a SQL query to answer the user's question. "
                   "Return ONLY the SQL query, no explanation."),
        *messages,
    ])

    return {
        "query": response.content.strip(),
        "messages": [AIMessage(content=f"Generated query: {response.content}")],
    }
```

### Узел: проверка запроса

```python
def validate_query(state: AgentState) -> AgentState:
    """Проверить SQL-запрос на распространённые ошибки."""
    query = state["query"]

    response = llm.invoke(
        f"Check this SQL query for errors:\n{query}\n\n"
        f"If correct, return the query as-is. "
        f"If there are errors, return the corrected query."
    )

    return {
        "query": response.content.strip(),
        "messages": [AIMessage(content=f"Validated query: {response.content}")],
    }
```

### Узел: выполнение запроса

```python
def execute_query(state: AgentState) -> AgentState:
    """Выполнить SQL-запрос и получить результаты."""
    query = state["query"]

    try:
        result = db.run(query)
        return {
            "result": str(result),
            "error": "",
            "messages": [AIMessage(content=f"Query result: {result}")],
        }
    except Exception as e:
        return {
            "result": "",
            "error": str(e),
            "messages": [AIMessage(content=f"Query error: {e}")],
        }
```

### Узел: формулирование ответа

```python
def generate_answer(state: AgentState) -> AgentState:
    """Сформулировать ответ на основе результатов запроса."""
    messages = state["messages"]
    result = state["result"]

    response = llm.invoke([
        ("system", "Answer the user's question based on the SQL query results. "
                   "Be concise and helpful."),
        *messages,
    ])

    return {
        "messages": [AIMessage(content=response.content)],
    }
```

## Построение графа

```python
from langgraph.graph import StateGraph, END


def should_retry(state: AgentState) -> str:
    """Решить, нужно ли повторить запрос или перейти к ответу."""
    if state.get("error"):
        return "retry"
    return "answer"


# Создание графа
workflow = StateGraph(AgentState)

# Добавление узлов
workflow.add_node("get_tables", get_tables)
workflow.add_node("identify_tables", identify_tables)
workflow.add_node("get_schema", get_schema)
workflow.add_node("generate_query", generate_query)
workflow.add_node("validate_query", validate_query)
workflow.add_node("execute_query", execute_query)
workflow.add_node("generate_answer", generate_answer)

# Определение рёбер
workflow.set_entry_point("get_tables")
workflow.add_edge("get_tables", "identify_tables")
workflow.add_edge("identify_tables", "get_schema")
workflow.add_edge("get_schema", "generate_query")
workflow.add_edge("generate_query", "validate_query")
workflow.add_edge("validate_query", "execute_query")

# Условное ребро: retry или answer
workflow.add_conditional_edges(
    "execute_query",
    should_retry,
    {
        "retry": "generate_query",
        "answer": "generate_answer",
    },
)

workflow.add_edge("generate_answer", END)

# Компиляция
agent = workflow.compile()
```

## Запуск агента

```python
result = agent.invoke({
    "messages": [("user", "How many orders were placed last month?")],
    "query": "",
    "result": "",
    "error": "",
    "relevant_tables": [],
})

# Получение финального ответа
final_message = result["messages"][-1]
print(final_message.content)
```

## Визуализация графа

```python
from IPython.display import Image, display

display(Image(agent.get_graph().draw_mermaid_png()))
```

## Добавление checkpointing

```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
agent = workflow.compile(checkpointer=checkpointer)

# Запуск с thread_id для сохранения состояния
config = {"configurable": {"thread_id": "sql-session-1"}}
result = agent.invoke(
    {"messages": [("user", "Show me the top 5 customers")]},
    config=config,
)
```

## Расширения

- **Human-in-the-loop**: добавление точки прерывания перед выполнением запроса
- **Ограничение количества повторов**: максимум 3 попытки перед возвратом ошибки
- **Кэширование схем**: сохранение DDL для повторного использования
- **Стриминг**: потоковая передача промежуточных шагов пользователю
- **Инструменты**: добавление инструментов для описания таблиц, примеров данных
