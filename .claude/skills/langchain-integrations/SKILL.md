---
name: langchain-integrations
description: "LangChain v0.3 интеграции (import langchain-openai/langchain-anthropic). ТОЛЬКО при: Chroma/FAISS/Pinecone/Qdrant langchain, OpenAIEmbeddings, ChatOpenAI, ChatAnthropic, WebBaseLoader, RecursiveCharacterTextSplitter, BM25Retriever langchain. НЕ для create_agent/middleware (→ langchain-core), НЕ для LangGraph (→ langgraph-core), НЕ для 1С, НЕ для Claude Code."
---

# LangChain Integrations

## Установка

```bash
pip install -U langchain                    # Ядро
pip install -U langchain-<provider>         # Провайдеры ставятся отдельно
```

Основные пакеты: `langchain-openai`, `langchain-anthropic`, `langchain-google-genai`, `langchain-aws`, `langchain-ollama`, `langchain-groq`, `langchain-huggingface`, `langchain-chroma`, `langchain-qdrant`, `langchain-postgres`, `langchain-pinecone`, `langchain-cohere`, `langchain-mistralai`, `langchain-mongodb`.

---

## Vector Stores

### Интерфейс

```python
store.add_documents(documents, ids=ids)              # Добавить
store.delete(ids=["id1", "id2"])                      # Удалить
docs = store.similarity_search(query, k=3, filter={}) # Поиск
```

### Выбор по окружению

| Окружение | Store | Пакет | Особенность |
|-----------|-------|-------|-------------|
| Dev/тесты | InMemoryVectorStore | `langchain-core` | Без зависимостей |
| Локальная разработка | Chroma | `langchain-chroma` | Персистентный |
| Локальная разработка | FAISS | `langchain-community` | Facebook AI, быстрый |
| Production (managed) | Pinecone | `langchain-pinecone` | Облачный managed |
| Production (self-hosted) | Qdrant | `langchain-qdrant` | Открытый, гибкий |
| Production (SQL) | PGVector | `langchain-postgres` | PostgreSQL расширение |
| Production (enterprise) | Milvus | `langchain-milvus` | Масштабируемый |
| Production (document DB) | MongoDB Atlas | `langchain-mongodb` | Встроенный vector search |

### Пример

```python
from langchain_chroma import Chroma

vector_store = Chroma(
    collection_name="my_collection",
    embedding_function=embeddings,
    persist_directory="./chroma_db"
)

# Similarity search с фильтром
docs = vector_store.similarity_search(
    "запрос", k=5, filter={"source": "manual"}
)
```

**Метрики:** Cosine Similarity, Euclidean Distance, Dot Product.

---

## Embeddings

### Интерфейс

```python
vectors = embeddings.embed_documents(["text1", "text2"])  # Batch
vector = embeddings.embed_query("query text")              # Single
```

### Провайдеры

| Модель | Пакет | Рекомендуемая модель |
|--------|-------|---------------------|
| OpenAI | `langchain-openai` | `text-embedding-3-large` |
| Google Gemini | `langchain-google-genai` | `models/gemini-embedding-001` |
| AWS Bedrock | `langchain-aws` | `amazon.titan-embed-text-v2:0` |
| HuggingFace | `langchain-huggingface` | `sentence-transformers/all-mpnet-base-v2` |
| Ollama | `langchain-ollama` | `llama3` (локально) |
| Cohere | `langchain-cohere` | `embed-english-v3.0` |
| MistralAI | `langchain-mistralai` | `mistral-embed` |

### Кеширование embeddings

```python
from langchain_core.embeddings import CacheBackedEmbeddings
from langchain_core.storage import LocalFileStore

store = LocalFileStore("./cache/")
cached_embedder = CacheBackedEmbeddings.from_bytes_store(
    underlying_embeddings,
    store,
    namespace=underlying_embeddings.model
)
```

---

## Document Loaders

### Интерфейс

```python
docs = loader.load()        # Загрузить все
docs = loader.lazy_load()   # Ленивая загрузка (для больших объёмов)
```

### По типу контента

| Тип | Loader | Пакет/Библиотека |
|-----|--------|-----------------|
| PDF | PyPDFLoader | `pypdf` |
| PDF (таблицы) | PDFPlumberLoader | `pdfplumber` |
| PDF (быстрый) | PyMuPDFLoader | `pymupdf` |
| PDF (Markdown) | PyMuPDF4LLMLoader | `pymupdf4llm` |
| PDF (modern) | DoclingLoader | `docling` |
| Web | WebBaseLoader | `langchain-community` |
| Web (рекурсивный) | RecursiveURLLoader | `langchain-community` |
| CSV | CSVLoader | `langchain-community` |
| JSON | JSONLoader | `langchain-community` |
| HTML | BSHTMLLoader | `beautifulsoup4` |
| Cloud (GCS) | GCSDirectoryLoader | `langchain-google-community` |
| Cloud (S3) | S3DirectoryLoader | `langchain-aws` |

---

## Text Splitters

```bash
pip install -U langchain-text-splitters
```

### Стратегии

| Стратегия | Класс | Когда использовать |
|-----------|-------|--------------------|
| **Рекурсивный** (рекомендуемый) | `RecursiveCharacterTextSplitter` | Общий текст |
| По токенам | `CharacterTextSplitter.from_tiktoken_encoder` | Контроль размера для LLM |
| По Markdown | `MarkdownHeaderTextSplitter` | Markdown-документы |
| По коду | `RecursiveCharacterTextSplitter.get_separators_for_language` | Исходный код |
| По HTML | `HTMLHeaderTextSplitter` | HTML-страницы |

### Пример

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " ", ""]
)
chunks = splitter.split_documents(documents)
```

**Токен-based splitting:**
```python
splitter = CharacterTextSplitter.from_tiktoken_encoder(
    encoding_name="cl100k_base",
    chunk_size=500,
    chunk_overlap=50
)
```

---

## Retrievers

### Интерфейс

```python
docs = retriever.invoke("query")  # -> List[Document]
```

### Типы

| Retriever | Назначение | Пакет |
|-----------|-----------|-------|
| VectorStoreRetriever | Из любого vector store | `langchain-core` |
| BM25Retriever | Lexical ranking | `langchain-community` |
| EnsembleRetriever | Гибридный (vector + BM25) | `langchain-community` |
| MultiQueryRetriever | Генерирует вариации запроса | `langchain-core` |
| TavilySearchAPIRetriever | Интернет-поиск | `langchain-community` |
| WikipediaRetriever | Статьи Wikipedia | `langchain-community` |
| ArxivRetriever | Научные статьи | `langchain-community` |

### Rerankers

```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain_cohere import CohereRerank

reranker = CohereRerank(model="rerank-v3.5", top_n=3)
retriever = ContextualCompressionRetriever(
    base_compressor=reranker,
    base_retriever=vector_store.as_retriever(search_kwargs={"k": 10})
)
```

Провайдеры reranking: **Cohere**, **FlashRank**, **Contextual AI**.

---

## Chat Models

### Универсальная инициализация

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("claude-sonnet-4-5-20250929", temperature=0.7)
```

### Матрица возможностей

| Модель | Пакет | Tool Calling | Structured Output | Multimodal |
|--------|-------|-------------|-------------------|-----------|
| ChatOpenAI | `langchain-openai` | + | + | + |
| ChatAnthropic | `langchain-anthropic` | + | + | + |
| ChatGoogleGenerativeAI | `langchain-google-genai` | + | + | + |
| ChatGroq | `langchain-groq` | + | + | - |
| ChatBedrock | `langchain-aws` | + | + | - |
| ChatOllama | `langchain-ollama` | + | + | - |

### OpenAI-совместимые endpoints

```python
model = ChatOpenAI(
    model="model-name",
    api_key="YOUR_API_KEY",
    base_url="https://api.provider.com/v1"
)
```

---

## Key-Value Stores

### Интерфейс

```python
store.mget(["key1", "key2"])                    # Получить
store.mset([("key1", b"val1"), ("key2", b"val2")])  # Записать
store.mdelete(["key1"])                          # Удалить
list(store.yield_keys(prefix="user_"))           # Итерация по ключам
```

| Store | Назначение |
|-------|-----------|
| InMemoryByteStore | Dev/тесты |
| LocalFileStore | Кеш на диске |
| RedisStore | Production (быстрый) |
| ElasticsearchEmbeddingsCache | Кеш embeddings |

---

## Tools & Toolkits

### Search Tools

| Инструмент | Бесплатно | Данные |
|-----------|-----------|--------|
| DuckDuckGo | Полностью | URL, snippet, title |
| Brave Search | Бесплатно | URL, snippet, title |
| Tavily | 1000/мес | URL, content, images |
| Google Serper | Free tier | URL, snippet, rank |

### Code Interpreters

Amazon Bedrock AgentCore, Azure Dynamic Sessions, Riza (Python, JS, PHP, Ruby).

### Productivity Toolkits

GitHub, Gmail, Slack, Jira, Office365 — готовые наборы инструментов.

---

## Паттерн: RAG Pipeline

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 1. Подготовка
embeddings = OpenAIEmbeddings()
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
vectorstore = Chroma(embedding_function=embeddings, persist_directory="./db")

# 2. Индексация
docs = loader.load()
chunks = splitter.split_documents(docs)
vectorstore.add_documents(chunks)

# 3. Поиск + генерация
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
docs = retriever.invoke("запрос пользователя")
model = ChatOpenAI(model="gpt-4")
response = model.invoke(f"Контекст: {docs}\n\nВопрос: запрос пользователя")
```

---

## Переменные окружения

| Переменная | Провайдер |
|-----------|-----------|
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `GOOGLE_API_KEY` | Google Gemini |
| `COHERE_API_KEY` | Cohere |
| `MISTRAL_API_KEY` | MistralAI |
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | AWS Bedrock |

---

**Источники:** Интеграции LangChain/ — 14 файлов (Anthropic, Google, Ollama, Пакеты, Поставщики, Векторные хранилища, Embeddings, Загрузчики, Сплиттеры, Ретриверы, Chat Models, K/V Stores, Tools, Middleware провайдеров)
