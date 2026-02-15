> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Создайте семантическую поисковую систему с помощью LangChain

## Обзор

В этом руководстве вы узнаете, как создать систему вопросов и ответов на основе Retrieval Augmented Generation (RAG) с помощью LangChain. RAG объединяет извлечение документов с генерацией ответов LLM.

### Ключевые концепции

- **Индексация**: загрузка, разбиение и сохранение данных в векторное хранилище
- **Извлечение (Retrieval)**: поиск релевантных документов во время запроса
- **Генерация**: использование извлечённого контекста в ответах LLM

## Подходы к реализации

### 1. Агентный RAG

Использует агента с инструментами извлечения. Модель решает, когда искать, и может выполнять несколько запросов итеративно.

**Преимущества**: контекстные поисковые запросы, гибкость.
**Недостатки**: два inference-вызова на каждую операцию поиска.

### 2. Двухшаговая RAG-цепочка

Более простой подход: всегда выполняет извлечение и делает один вызов LLM.

**Преимущества**: меньшая задержка.
**Недостатки**: меньше гибкости.

## Архитектура

### Конвейер индексации

1. **Загрузка**: использование document loaders для получения исходных данных
2. **Разбиение**: разделение документов на управляемые фрагменты
3. **Хранение**: эмбеддинг и индексация фрагментов в векторной БД

### Конвейер retrieval-generation

Поиск в сохранённых документах и включение извлечённого контекста в промпт модели.

## Установка

```bash
pip install langchain langgraph langchain-anthropic langchain-community
```

## Реализация

### Шаг 1: Загрузка документов

```python
from langchain_community.document_loaders import PyMuPDFLoader

loader = PyMuPDFLoader("path/to/document.pdf")
docs = loader.load()
```

### Шаг 2: Разбиение на фрагменты

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)
splits = text_splitter.split_documents(docs)
```

### Шаг 3: Создание векторного хранилища

```python
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-large"
)

vectorstore = Chroma.from_documents(
    documents=splits,
    embedding=embeddings,
)
```

### Шаг 4: Создание retriever

```python
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5},
)
```

### Шаг 5: Создание RAG-цепочки

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")

prompt = ChatPromptTemplate.from_template("""
Answer the question based only on the following context:

{context}

Question: {question}
""")

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

### Шаг 6: Выполнение запроса

```python
response = rag_chain.invoke("What is a retrieval augmented generation?")
print(response)
```

## Агентный подход

### Создание инструмента поиска

```python
from langchain.tools.retriever import create_retriever_tool

retriever_tool = create_retriever_tool(
    retriever,
    name="document_search",
    description="Search indexed documents for relevant information",
)
```

### Создание агента

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    llm,
    tools=[retriever_tool],
    prompt="You are a helpful assistant that answers questions using document search.",
)
```

### Запуск агента

```python
result = agent.invoke({"messages": [("user", "What are the key features?")]})
print(result["messages"][-1].content)
```

## Расширения

- **Потоковая передача токенов**: streaming для ответов в реальном времени
- **Многоходовые разговоры**: поддержка истории сообщений
- **Долгосрочная память**: интеграция с хранилищем состояния
- **Гибридный поиск**: комбинация vector + BM25 для лучшего качества
- **Реранкинг**: LLM или cross-encoder для повышения точности
