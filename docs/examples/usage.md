# Примеры использования

## Программное использование (Python API)

### Базовый пайплайн: загрузка → индексация → поиск

```python
import asyncio
from src.pdf_framework.config import get_settings
from src.pdf_framework.loaders import get_loader
from src.pdf_framework.processing.pipeline import ProcessingPipeline
from src.pdf_framework.embeddings import get_embedding_engine
from src.pdf_framework.vector_store import get_vector_store
from src.pdf_framework.vector_store.indexing.indexer import DocumentIndexer
from src.pdf_framework.search.strategies.vector_search import VectorSearchStrategy

async def main():
    settings = get_settings()

    # 1. Инициализация компонентов
    loader = get_loader(settings.pdf)
    pipeline = ProcessingPipeline(settings.pdf)
    engine = get_embedding_engine(settings.embedding)
    store = get_vector_store(settings.vector_store)
    await store.initialize()

    # 2. Загрузка и обработка PDF
    document = await loader.load("path/to/document.pdf")
    chunks = pipeline.process(document)
    print(f"Документ: {document.metadata.title}")
    print(f"Страниц: {document.metadata.page_count}")
    print(f"Чанков: {len(chunks)}")

    # 3. Индексация
    indexer = DocumentIndexer(engine, store)
    result = await indexer.index_chunks(
        chunks,
        document_id=document.id,
        source_path=document.source_path,
    )
    print(f"Проиндексировано: {result.chunks_stored} чанков")

    # 4. Поиск
    search = VectorSearchStrategy(engine, store)
    response = await search.search("ключевые выводы", k=3)
    for r in response.results:
        print(f"[{r.score:.3f}] {r.chunk.content[:100]}...")

asyncio.run(main())
```

### Построение графа знаний

```python
import asyncio
from src.pdf_framework.config import get_settings
from src.pdf_framework.graph_store import get_graph_store
from src.pdf_framework.processing.extractors.entity_extractor import LLMEntityExtractor
from src.pdf_framework.graph_store.construction.builder import GraphBuilder

async def build_knowledge_graph(chunks):
    settings = get_settings()

    # Инициализация
    graph_store = get_graph_store(settings.graph_store)
    await graph_store.initialize()

    extractor = LLMEntityExtractor(
        settings=settings.agent,
        api_key=settings.anthropic_api_key,
    )
    builder = GraphBuilder(extractor, graph_store)

    # Извлечение и построение
    stats = await builder.build_from_chunks(chunks)
    print(f"Сущностей: {stats['entities_added']}")
    print(f"Связей: {stats['relations_added']}")

    # Запрос к графу
    entities = await graph_store.find_entities(name="OpenAI", limit=5)
    for e in entities:
        print(f"  {e.name} ({e.entity_type})")
        subgraph = await graph_store.get_neighbors(e.id, depth=1)
        for r in subgraph.relations:
            print(f"    → {r.relation_type} → {r.target_entity_id}")

asyncio.run(build_knowledge_graph(chunks))
```

### Гибридный поиск

```python
import asyncio
from src.api.dependencies.components import get_components

async def hybrid_search_example():
    components = await get_components()

    # Гибридный поиск (vector + graph через RRF)
    response = await components.search_manager.search(
        query="нейронные сети",
        strategy="hybrid",
        k=5,
    )

    print(f"Найдено: {response.total_found} результатов за {response.elapsed_ms:.0f}ms")
    for i, r in enumerate(response.results, 1):
        print(f"  [{i}] score={r.score:.4f} source={r.source}")
        print(f"      {r.chunk.content[:150]}...")

asyncio.run(hybrid_search_example())
```

### RAG-ответ

```python
import asyncio
from src.api.dependencies.components import get_components
from src.pdf_framework.chains.qa.retrieval_qa import RetrievalQAChain

async def rag_example():
    components = await get_components()

    # Поиск контекста
    search_response = await components.search_manager.search(
        query="основные методы",
        strategy="hybrid",
        k=5,
    )

    # Генерация ответа
    chain = RetrievalQAChain(
        settings=components.settings.agent,
        api_key=components.settings.anthropic_api_key,
    )
    answer = await chain.answer("Какие основные методы описаны?", search_response)
    print(answer)

asyncio.run(rag_example())
```

### LangGraph RAG-агент

```python
import asyncio
from src.api.dependencies.components import get_components
from src.pdf_framework.agents.rag.agent import create_rag_agent

async def agent_example():
    components = await get_components()

    agent = create_rag_agent(
        search_manager=components.search_manager,
        settings=components.settings.agent,
        api_key=components.settings.anthropic_api_key,
    )

    result = await agent.ainvoke({
        "question": "Сравните подходы A и B из документа"
    })

    print(f"Стратегия: {result['search_strategy']}")
    print(f"Ответ: {result['answer']}")
    print(f"Источники: {result['sources']}")

asyncio.run(agent_example())
```

### Использование кэша эмбеддингов

```python
from src.pdf_framework.embeddings.cache.file_cache import FileEmbeddingCache

cache = FileEmbeddingCache()

# Проверить кэш
cached = cache.get("some text")
if cached is None:
    # Вычислить эмбеддинг
    embedding = await engine.embed_text("some text")
    cache.put("some text", embedding)
else:
    embedding = cached

# Статистика
print(cache.stats)  # {"hits": 10, "misses": 2}
```

### Очистка текста

```python
from src.pdf_framework.processing.cleaners.text_cleaner import TextCleaner

cleaner = TextCleaner()

# Очистка текста из PDF
raw_text = "  Некоторый    текст  с  \n\n\n\n  лишними пробелами  "
clean_text = cleaner.clean(raw_text)
# "Некоторый текст с\n\nlишними пробелами"
```

### Метрики

```python
from src.pdf_framework.callbacks.metrics.collector import MetricsCollector

metrics = MetricsCollector()

# Замер времени
metrics.start_timer("indexing")
# ... операция индексации ...
elapsed = metrics.stop_timer("indexing")
print(f"Индексация: {elapsed:.0f}ms")

# Счётчики
metrics.increment("documents_processed")
metrics.increment("chunks_created", amount=42)

# Сводка
print(metrics.summary())
```

## CLI

```bash
# Индексация с построением графа
pdf-framework index report.pdf --graph

# Семантический поиск, 10 результатов
pdf-framework search "ключевые слова" -k 10

# Гибридный поиск
pdf-framework search "запрос" --strategy hybrid

# RAG-ответ
pdf-framework ask "Какие выводы можно сделать?"

# Статистика
pdf-framework stats

# Запуск API-сервера
pdf-framework server --port 9000
```

## REST API (curl)

```bash
# Индексация
curl -X POST http://localhost:8000/documents/index \
  -H "Content-Type: application/json" \
  -d '{"file_path": "report.pdf"}'

# Поиск
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "запрос", "strategy": "hybrid", "k": 5}'

# RAG
curl -X POST http://localhost:8000/search/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Ваш вопрос?"}'

# Статистика
curl http://localhost:8000/documents/stats

# Удаление документа
curl -X DELETE http://localhost:8000/documents/abc123
```
