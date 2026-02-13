# Руководство по использованию

## Что нового

### Phase 1: Reranking, Metadata Filtering, Configurable Weights

1. **Reranking** - Автоматическое улучшение точности (+40%)
2. **Фильтрация по metadata** - Поиск по типу документа, языку, версии
3. **Настраиваемые веса** - Гибкая настройка hybrid search

### Phase 2: MMR Diversity, Semantic Chunking, Query Expansion

4. **MMR (Maximal Marginal Relevance)** - Разнообразие результатов, устранение дубликатов
5. **Semantic Chunking** - Интеллектуальное разбиение текста по смысловым блокам
6. **Query Expansion** - Автоматическое расширение запроса синонимами и перефразировками

### Phase 3: Contextual Retrieval, FlashRank, Two-Stage Pipeline

7. **Contextual Retrieval** - Добавление контекста документа к каждому чанку при индексации
8. **FlashRank** - Быстрый и лёгкий reranker для продакшена
9. **Two-Stage Pipeline** - Двухэтапный поиск: быстрый recall + точный reranking

### Phase 4: Evaluation Framework, RAG Triad, Benchmark Runner

10. **Evaluation Framework** - Автоматическая оценка качества поиска и RAG
11. **RAG Triad** - Метрики: Faithfulness, Answer Relevance, Context Relevance
12. **Benchmark Runner** - Запуск бенчмарков на наборах данных с отчётами

### Phase 5: Self-RAG Agent

13. **Document Grading** - Оценка релевантности найденных документов
14. **Query Rewriting** - Автоматическая перепись запроса при низкой релевантности
15. **Hallucination Check** - Проверка ответа на соответствие контексту

### Phase 6: GraphRAG (Global & Local Search)

16. **Community Detection** - Кластеризация сущностей графа (Leiden algorithm)
17. **Local Search** - Поиск по ближайшим сущностям и community summaries
18. **Global Search** - Map-reduce по всем community для высокоуровневых ответов

### Phase 7: Parent-Child Retrieval

19. **Auto-Merge Strategy** - Поиск по child chunks, возврат parent chunks
20. **Hierarchical Indexing** - Двухуровневая структура для точного и полного контекста

### Phase 8: Adaptive RAG

21. **Query Classification** - Автоматический выбор стратегии по типу запроса
22. **Sub-Question Decomposition** - Разложение сложных вопросов на подвопросы
23. **Strategy Routing** - Умная маршрутизация: vector, hybrid, graphrag

### Phase 9: Conversational RAG

24. **Interactive Chat** - Многошаговый диалог с контекстом
25. **Query Reformulation** - Автоматическая переписка с учётом истории
26. **Streaming Responses** - Поточный вывод ответов (SSE)

### Phase 10: Layout-Aware Parsing

27. **Document Structure** - Распознавание заголовков, параграфов, списков
28. **Table Extraction** - Извлечение таблиц в Markdown формате
29. **Image Extraction** - Извлечение изображений с описанием через Vision

### Phase 11: Observability & Caching

30. **Tracing** - JSON tracing всех операций
31. **Embedding Cache** - Кэширование эмбеддингов
32. **LLM Cache** - Кэширование LLM ответов
33. **Metrics Dashboard** - HTML дашборд с метриками

### Phase 12: Multi-Tenancy & Auth

34. **Tenant Isolation** - Изолированные коллекции для каждого тенанта
35. **JWT Authorization** - Токен-based авторизация
36. **RBAC** - Ролевой доступ (viewer, editor, admin)

### Phase 13: RAPTOR & HyDE

37. **RAPTOR Tree** - Иерархическая кластеризация чанков с суммаризацией
38. **HyDE** - Hypothetical Document Embeddings для улучшения recall
39. **Summary Index** - Отдельная коллекция с суммаризациями документов

### Phase 14: UI & Developer Experience

40. **Web UI** - Gradio интерфейс с 5 вкладками (Chat, Search, Documents, Graph, Settings)
41. **QuickRAG API** - 3-строчный API для быстрого старта
42. **OpenAI-Compatible API** - Совместимость с OpenAI Python SDK
43. **Query Suggestions** - Entity-based, frequency-based, LLM-based предложения

### Phase 15: Image Understanding & Multimodal RAG

44. **Image Extraction** - PyMuPDF извлечение изображений (min 50×50)
45. **Claude Vision Descriptions** - Claude Sonnet 4.5 для описания изображений
46. **Image-Aware Chunking** - Привязка к странице через `page_number`
47. **Markdown Tables** - 81.5% изображений содержат markdown таблицы

### Phase 16: BM25 Lexical Search + Hybrid Fusion

48. **BM25 индекс** - SQLite FTS5 полнотекстовый поиск
49. **pymorphy3 Lemmatization** - Русская морфология (NDCG@10 = 52.16 по RusBEIR)
50. **Reciprocal Rank Fusion** - `score(d) = SUM 1/(k + rank_i(d))`, k=60
51. **Header Propagation** - Заголовки разделов в метаданных чанков

### Phase 17: Semantic Caching & Query Optimization

52. **Embedding Cache** - LRU кэш эмбеддингов запросов (TTL 1 час)
53. **Semantic Cache** - Cosine similarity >= 0.95 → возврат кэша
54. **Response Cache** - LLM ответы с привязкой к query + strategy
55. **Cache Invalidation** - Очистка при переиндексации документа

### Phase 18: Incremental Indexing

56. **Document Versioning** - Content hash для отслеживания изменений
57. **Delta Indexing** - Индексация только изменённых чанков
58. **File Watcher** - Автоматическая переиндексация при изменении файлов

### Phase 19: Deep Research Agent

59. **Research Planner** - Декомпозиция исследовательских вопросов на подзадачи
60. **Multi-Step Retrieval** - Итеративный поиск с углублением
61. **Quality Checker** - Проверка полноты и качества ответа
62. **Research Synthesizer** - Синтез финального ответа из нескольких источников

### Phase 20: AutoRAG Optimization

63. **Parameter Grid** - Перебор параметров поиска (strategy, k, weights)
64. **Smart Grid** - Интеллектуальный выбор комбинаций для тестирования
65. **Optimization Runner** - Автоматический запуск бенчмарков
66. **Analyzer** - Анализ результатов, выбор оптимальных настроек

### Phase 21: RAGAS Evaluation

67. **RAGAS Adapter** - Интеграция с RAGAS framework
68. **Regression Testing** - Отслеживание деградации качества
69. **Error Analysis** - Анализ ошибок и слабых мест
70. **History Tracking** - История оценок по версиям

### Phase 22: Self-Learning Feedback

71. **Feedback Store** - Хранение пользовательской обратной связи
72. **Few-Shot Learning** - Использование лучших примеров для улучшения
73. **Score Boosting** - Повышение score документов с позитивным фидбеком

### Phase 23: Production Hardening

74. **Qdrant Vector Store** - Миграция с ChromaDB на Qdrant (Docker)
75. **PgVector Provider** - Альтернативный провайдер PostgreSQL + pgvector
76. **Rate Limiting** - Ограничение частоты запросов
77. **RBAC** - Ролевой доступ (viewer, editor, admin)

### Phase 24: Qdrant Native BM25 + FTS5 Fallback

78. **Sparse Vectors** - BM25 через Qdrant sparse vectors + IDF modifier
79. **Hybrid Search** - Server-side RRF (dense + BM25 prefetch)
80. **FTS5 Fallback** - pymorphy3 lemmatization как fallback
81. **Rebuild API** - Кнопка «Пересобрать BM25» в UI + API endpoint

### Cross-Cutting: Ralph Wiggum (Self-Correcting Feedback)

82. **LLM Self-Correction** - При сбое LLM-вызова, передаём *причину* отказа в следующую попытку
83. **11 точек интеграции** - grader, rewriter, hallucination_checker, agent, context_generator, entity_extractor, query_expansion, hyde, summarizer
84. **Валидаторы** - Проверка длины, языка, формата, JSON, identity check

### Cross-Cutting: Page-Aware Chunk Mapping

85. **Page Offsets** - `pymupdf_loader.py` сохраняет `page_offsets = [(char_offset, page_num)]`
86. **Bisect Mapping** - `pipeline.py` использует `bisect.bisect_right()` для привязки чанков к страницам
87. **Результат** - 834/834 текстовых чанков → корректные страницы, 218/218 страниц покрыты

---

## Быстрый старт

### 1. Поиск с автоматическим reranking (рекомендуется)

```bash
# Простой поиск - reranking включен автоматически
python -m src.cli.main search "документация 1С Предприятие"

# Результат: Top score улучшается с 0.59 до 0.99
```

### 2. Фильтрация по языку

```bash
# Найти только русскоязычные документы
python -m src.cli.main search "руководство" --language ru

# Только английские
python -m src.cli.main search "manual" --language en
```

### 3. Фильтрация по типу документа

```bash
# Только руководства пользователя
python -m src.cli.main search "установка" --doc-type user_manual

# Только документация
python -m src.cli.main search "API" --doc-type documentation

# Доступные типы:
# - documentation
# - user_manual
# - developer_guide
# - admin_guide
# - api_reference
# - tutorial
# - introduction
```

### 4. Фильтрация по версии

```bash
# Документы версии 8.3
python -m src.cli.main search "конфигуратор" --version 8.3

# Конкретная версия
python -m src.cli.main search "PostgreSQL" --version 8.3.26
```

### 5. Комбинированные фильтры

```bash
# Русскоязычные руководства пользователя версии 8.3
python -m src.cli.main search "работа с базой данных" \
    --language ru \
    --doc-type user_manual \
    --version 8.3

# Hybrid search с фильтрацией
python -m src.cli.main search "PostgreSQL" \
    --strategy hybrid \
    --language ru \
    --doc-type documentation
```

---

## CLI команды

### Базовые параметры

```bash
python -m src.cli.main search "QUERY" [OPTIONS]
```

**Опции:**

| Опция | Описание | Default | Пример |
|-------|----------|---------|--------|
| `--strategy`, `-s` | Стратегия поиска | `vector` | `--strategy hybrid` |
| `--top-k`, `-k` | Количество результатов | `5` | `-k 10` |
| `--no-rerank` | Отключить reranking | `false` | `--no-rerank` |
| `--no-self-rag` | Отключить Self-RAG | `false` | `--no-self-rag` |
| `--language` | Фильтр по языку | - | `--language ru` |
| `--doc-type` | Фильтр по типу | - | `--doc-type documentation` |
| `--version` | Фильтр по версии | - | `--version 8.3` |
| `--diversity` | Коэффициент разнообразия (для MMR) | `0.3` | `--diversity 0.5` |
| `--expand-query` | Расширение запроса синонимами (HyDE) | `false` | `--expand-query` |
| `--verbose`, `-v` | Подробный вывод с trace | `false` | `--verbose` |
| `--stream` | Потоковый вывод ответа | `false` | `--stream` |
| `--tenant` | Tenant ID для multi-tenancy | `default` | `--tenant company-a` |
| `--force-route` | Принудительный выбор стратегии (adaptive) | - | `--force-route graphrag_global` |

**Стратегии поиска:**

- `vector` - Семантический поиск через dense embeddings (E5-large 1024d)
- `bm25` - Лексический поиск BM25 (FTS5 + pymorphy3 lemmatization, 5-14ms)
- `hybrid` - Комбинация vector + BM25 + graph с RRF fusion (лучшее качество)
- `graph` - Поиск по знаниям графа (entities, relations)
- `mmr` - Maximal Marginal Relevance (разнообразие результатов)
- `two_stage` - Двухэтапный pipeline: быстрый recall + точный reranking
- `self_rag` - Self-RAG с grading, rewriting, hallucination check
- `adaptive` - Адаптивный выбор стратегии по типу запроса
- `graphrag_local` - Local GraphRAG: поиск по ближайшим сущностям
- `graphrag_global` - Global GraphRAG: map-reduce по communities
- `auto_merge` - Parent-Child: поиск по child, возврат parent
- `raptor` - RAPTOR: иерархический поиск по summaries

### Примеры команд

```bash
# 1. Быстрый поиск (vector, reranking enabled)
python -m src.cli.main search "конфигуратор"

# 2. Hybrid search для лучшего качества
python -m src.cli.main search "PostgreSQL" --strategy hybrid

# 3. Больше результатов
python -m src.cli.main search "документация" -k 10

# 4. Без reranking (быстрее, но менее точно)
python -m src.cli.main search "быстрый запрос" --no-rerank

# 5. Точный поиск в русских руководствах
python -m src.cli.main search "установка" \
    --language ru \
    --doc-type user_manual

# 6. Поиск API в документации конкретной версии
python -m src.cli.main search "API методы" \
    --doc-type api_reference \
    --version 8.3.26

# 7. Adaptive RAG - автоматический выбор стратегии
python -m src.cli.main search "архитектура платформы" --strategy adaptive

# 8. GraphRAG Local поиск
python -m src.cli.main search "конфигуратор" --strategy graphrag_local --top-k 5

# 9. GraphRAG Global - высокоуровневый ответ
python -m src.cli.main search "связи компонентов 1С" --strategy graphrag_global

# 10. Parent-Child поиск (auto_merge)
python -m src.cli.main search "объекты конфигурации" --strategy auto_merge

# 11. RAPTOR иерархический поиск
python -m src.cli.main search "общая концепция" --strategy raptor --top-k 5

# 12. BM25 лексический поиск (быстрый, 5-14ms)
python -m src.cli.main search "модуль внешнего соединения" --strategy bm25

# 13. Hybrid с BM25 + Vector + Graph (Qdrant native RRF)
python -m src.cli.main search "роли и права доступа" --strategy hybrid -k 10
```

---

## Python API

### Базовое использование

```python
import asyncio
from src.api.dependencies.components import Components

async def search_example():
    # Инициализация
    components = Components()
    await components.initialize()

    # Простой поиск
    response = await components.search_manager.search(
        query="документация 1С Предприятие",
        strategy="vector",
        k=5,
    )

    # Вывод результатов
    for i, result in enumerate(response.results, 1):
        print(f"{i}. Score: {result.score:.4f}")
        print(f"   {result.chunk.content[:100]}...")
        print()

asyncio.run(search_example())
```

### С фильтрацией

```python
async def filtered_search():
    components = Components()
    await components.initialize()

    # Поиск с фильтрами
    response = await components.search_manager.search(
        query="конфигуратор",
        strategy="hybrid",
        k=10,
        filter={
            "language": "ru",
            "document_type": "documentation",
            "version": "8.3",
        },
        rerank=True,  # По умолчанию включен
    )

    for result in response.results:
        meta = result.chunk.metadata
        print(f"Type: {meta['document_type']}")
        print(f"Lang: {meta['language']}")
        print(f"Version: {meta['version']}")
        print(f"Score: {result.score:.4f}")
        print()

asyncio.run(filtered_search())
```

### Отключение reranking

```python
# Для очень быстрых queries
response = await components.search_manager.search(
    query="быстрый поиск",
    strategy="vector",
    k=5,
    rerank=False,  # Отключить reranking
)
```

### Доступ к metadata

```python
response = await components.search_manager.search(
    query="PostgreSQL",
    strategy="hybrid",
    k=5,
)

for result in response.results:
    chunk = result.chunk

    # Structured fields (Phase 1.3)
    print(f"Document Type: {chunk.metadata.get('document_type')}")
    print(f"Language: {chunk.metadata.get('language')}")
    print(f"Version: {chunk.metadata.get('version')}")
    print(f"Source: {chunk.metadata.get('source')}")
    print(f"Title: {chunk.metadata.get('title')}")
    print()
```

---

## Индексация с metadata enrichment

При индексации новых PDF документов, metadata автоматически добавляется.

### CLI команды индексации

```bash
# Базовая индексация
pdf-framework index "path/to/document.pdf"

# С графом сущностей
pdf-framework index "path/to/document.pdf" --graph

# С community detection
pdf-framework index "path/to/document.pdf" --graph --communities

# С parent-child структурой
pdf-framework index "path/to/document.pdf" --parent-child

# С RAPTOR
pdf-framework index "path/to/document.pdf" --raptor

# С summarization
pdf-framework index "path/to/document.pdf" --summarize

# С layout-aware parsing
pdf-framework index "path/to/document.pdf" --layout-aware

# С извлечением таблиц
pdf-framework index "path/to/document.pdf" --extract-tables

# С извлечением изображений
pdf-framework index "path/to/document.pdf" --extract-images

# Комбо: все фичи
pdf-framework index "path/to/document.pdf" \
  --graph --communities --parent-child --raptor \
  --summarize --layout-aware

# Рекурсивная индексация директории
pdf-framework index "path/to/docs/" --recursive --graph

# С указанием tenant
pdf-framework index "path/to/document.pdf" --tenant company-a
```

### Python API индексации

```python
from src.api.dependencies.components import Components

async def index_with_metadata():
    components = Components()
    await components.initialize()

    # Загрузить PDF
    document = await components.loader.load("path/to/document.pdf")

    # Обработать - metadata enrichment автоматический
    chunks = components.pipeline.process(document)

    # Проверить metadata
    print("Sample chunk metadata:")
    print(chunks[0].metadata)
    # {
    #   'document_type': 'documentation',
    #   'language': 'ru',
    #   'version': '8.3.26',
    #   'source': 'path/to/document.pdf',
    #   'title': 'Document Title',
    #   ...
    # }

    # Индексировать
    result = await components.indexer.index_chunks(
        chunks,
        document_id=document.id,
        source_path=document.source_path,
    )

    print(f"Indexed: {result.chunks_stored} chunks")

asyncio.run(index_with_metadata())
```

---

## Настройка конфигурации

### Файл .env

```env
# === Reranking (Phase 1.1) ===
AGENT__RERANKER_ENABLED=true
AGENT__RERANKER_MODEL=BAAI/bge-reranker-v2-m3
AGENT__RERANKER_TOP_K=20

# === Hybrid Search Weights (Phase 1.2) ===
SEARCH__HYBRID_VECTOR_WEIGHT=0.6
SEARCH__HYBRID_GRAPH_WEIGHT=0.4
SEARCH__HYBRID_RRF_K=60

# === MMR & Diversity (Phase 2) ===
SEARCH__MMR_DIVERSITY=0.3
SEARCH__QUERY_EXPANSION_ENABLED=false
SEARCH__QUERY_EXPANSION_MODEL=default

# === Two-Stage Pipeline (Phase 3) ===
TWO_STAGE__ENABLED=true
TWO_STAGE__FIRST_STAGE_K=50
TWO_STAGE__RERANKER=flashrank
TWO_STAGE__RERANKER_MODEL=ms-marco-MiniLM-L-6-v2
TWO_STAGE__CONTEXTUAL_RETRIEVAL=false

# === Self-RAG (Phase 5) ===
SELF_RAG__ENABLED=true
SELF_RAG__GRADER_MODEL=claude-haiku-4-5-20251001
SELF_RAG__RELEVANCE_THRESHOLD=0.5
SELF_RAG__MAX_REWRITE_ATTEMPTS=2

# === GraphRAG (Phase 6) ===
GRAPH_RAG__COMMUNITY_DETECTION=true
GRAPH_RAG__COMMUNITY_ALGORITHM=leiden
GRAPH_RAG__LOCAL_SEARCH_K=10
GRAPH_RAG__GLOBAL_MAP_LLM=claude-haiku-4-5-20251001
GRAPH_RAG__GLOBAL_REDUCE_LLM=claude-sonnet-4-5-20250929

# === Parent-Child (Phase 7) ===
PARENT_CHILD__ENABLED=true
PARENT_CHILD__PARENT_SIZE=2000
PARENT_CHILD__CHILD_SIZE=400
PARENT_CHILD__MERGE_THRESHOLD=3

# === Adaptive RAG (Phase 8) ===
ADAPTIVE__ROUTING_ENABLED=true
ADAPTIVE__CLASSIFIER_MODEL=claude-haiku-4-5-20251001
ADAPTIVE__DECOMPOSE_THRESHOLD=complex

# === Conversational (Phase 9) ===
CONVERSATION__MAX_HISTORY=10
CONVERSATION__STORAGE=sqlite
CONVERSATION__DB_PATH=data/conversations.db

# === Observability (Phase 11) ===
OBSERVABILITY__TRACER=jsonfile
OBSERVABILITY__TRACE_DIR=data/traces
CACHE__EMBEDDING_ENABLED=true
CACHE__LLM_ENABLED=true

# === Multi-Tenancy (Phase 12) ===
AUTH__ENABLED=true
AUTH__JWT_SECRET=your-secret-key-min-32-chars-long
AUTH__JWT_EXPIRATION_HOURS=24

# === RAPTOR (Phase 13) ===
RAPTOR__ENABLED=true
RAPTOR__MAX_LEVELS=4
RAPTOR__CLUSTERING_MODEL=kmeans
RAPTOR__SUMMARY_MODEL=claude-haiku-4-5-20251001
SUMMARY_INDEX__ENABLED=true
SUMMARY_INDEX__MIN_CHUNKS=10

# === Image Understanding (Phase 15) ===
VISION__MODEL=claude-sonnet-4-5-20250929
VISION__MAX_TOKENS=2048
VISION__MIN_IMAGE_SIZE=50

# === BM25 Lexical Search (Phase 16) ===
SEARCH__BM25_DB_PATH=data/bm25_index.db
SEARCH__BM25_BACKEND=qdrant
# BM25 backend: "qdrant" (native sparse) | "fts5" (SQLite pymorphy3) | "both"

# === Qdrant Native BM25 (Phase 24) ===
VECTOR_STORE__QDRANT_BM25_ENABLED=true
VECTOR_STORE__QDRANT_BM25_LANGUAGE=russian
VECTOR_STORE__PROVIDER=qdrant
VECTOR_STORE__QDRANT_URL=http://localhost:6333
VECTOR_STORE__QDRANT_COLLECTION=pdf_documents

# === Semantic Cache (Phase 17) ===
CACHE__SEMANTIC_ENABLED=true
CACHE__SEMANTIC_THRESHOLD=0.95
CACHE__SEMANTIC_TTL=3600

# === Incremental Indexing (Phase 18) ===
INDEXING__INCREMENTAL=true
INDEXING__WATCH_ENABLED=false
INDEXING__WATCH_DIR=data/pdfs

# === Embedding (Phase 15+) ===
EMBEDDING__MODEL=intfloat/multilingual-e5-large
EMBEDDING__DIMENSIONS=1024
# E5 models require prefix: "query: " for search, "passage: " for indexing

# === LLM ===
ANTHROPIC__API_KEY=your-api-key
ANTHROPIC__BASE_URL=https://api.anthropic.com
AGENT__MODEL=claude-opus-4-6
AGENT__FAST_MODEL=claude-sonnet-4-5-20250929
```

### Альтернативные reranker модели

```env
# Быстрая модель (English)
AGENT__RERANKER_MODEL=ms-marco-MiniLM-L-6-v2

# Самая точная (медленнее)
AGENT__RERANKER_MODEL=BAAI/bge-reranker-large

# Multilingual (рекомендуемая для русского)
AGENT__RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

### Настройка весов для разных типов запросов

```env
# Для концептуальных вопросов ("что такое", "как работает")
SEARCH__HYBRID_VECTOR_WEIGHT=0.7
SEARCH__HYBRID_GRAPH_WEIGHT=0.3

# Для фактических вопросов ("версия", "имя файла")
SEARCH__HYBRID_VECTOR_WEIGHT=0.4
SEARCH__HYBRID_GRAPH_WEIGHT=0.6

# Универсальные (default)
SEARCH__HYBRID_VECTOR_WEIGHT=0.6
SEARCH__HYBRID_GRAPH_WEIGHT=0.4
```

---

## RAG (Question Answering)

```bash
# Задать вопрос с использованием RAG
python -m src.cli.main ask "Что такое 1С Предприятие?"

# С hybrid search
python -m src.cli.main ask "Как работать с PostgreSQL?" --strategy hybrid
```

```python
async def ask_question():
    from src.pdf_framework.chains.qa.retrieval_qa import RetrievalQAChain

    components = Components()
    await components.initialize()

    # Поиск контекста с фильтрацией
    search_response = await components.search_manager.search(
        query="Что такое конфигуратор?",
        strategy="hybrid",
        k=5,
        filter={"language": "ru"},
    )

    # RAG ответ
    chain = RetrievalQAChain(
        settings=components.settings.agent,
        api_key=components.settings.anthropic_api_key,
    )

    answer = await chain.answer(
        question="Что такое конфигуратор?",
        search_response=search_response,
    )

    print(f"Answer: {answer}")

asyncio.run(ask_question())
```

---

## Типичные сценарии использования

### 1. Поиск в технической документации

```bash
# Найти все упоминания PostgreSQL в русской документации
python -m src.cli.main search "PostgreSQL СУБД" \
    --strategy hybrid \
    --language ru \
    --doc-type documentation \
    -k 10
```

### 2. Поиск инструкций для пользователей

```bash
# Инструкции по установке в руководствах пользователя
python -m src.cli.main search "установка настройка" \
    --doc-type user_manual \
    --language ru
```

### 3. Быстрый поиск без фильтров

```bash
# Максимальная скорость
python -m src.cli.main search "быстрый запрос" \
    --strategy vector \
    --no-rerank \
    -k 3
```

### 4. Точный поиск с максимальным качеством

```bash
# Максимальная точность
python -m src.cli.main search "сложный технический вопрос" \
    --strategy hybrid \
    --language ru \
    -k 10
# Reranking enabled by default
```

### 5. Поиск API документации

```bash
# API методы в справочнике
python -m src.cli.main search "API методы базы данных" \
    --doc-type api_reference \
    --version 8.3
```

---

## Phase 2: Продвинутый поиск

### MMR (Maximal Marginal Relevance)

MMR обеспечивает разнообразие результатов, устраняя дублирующиеся или слишком похожие фрагменты.

```bash
# MMR поиск с дефолтным разнообразием (0.3)
python -m src.cli.main search "настройка сервера 1С" --strategy mmr

# Увеличить разнообразие результатов
python -m src.cli.main search "настройка сервера 1С" --strategy mmr --diversity 0.7

# MMR с фильтрацией
python -m src.cli.main search "установка" --strategy mmr --language ru --diversity 0.5
```

```python
# Python API: MMR поиск
response = await components.search_manager.search(
    query="настройка сервера 1С",
    strategy="mmr",
    k=10,
    diversity=0.5,  # 0.0 = только релевантность, 1.0 = максимальное разнообразие
)
```

### Query Expansion (расширение запроса)

Автоматически расширяет запрос синонимами и перефразировками для улучшения полноты поиска.

```bash
# Поиск с расширением запроса
python -m src.cli.main search "установка базы данных" --expand-query

# Комбинация с hybrid search
python -m src.cli.main search "настройка PostgreSQL" --strategy hybrid --expand-query

# MMR + расширение запроса
python -m src.cli.main search "конфигуратор" --strategy mmr --expand-query --diversity 0.4
```

```python
# Python API: Query Expansion
response = await components.search_manager.search(
    query="установка базы данных",
    strategy="hybrid",
    k=10,
    expand_query=True,
)
```

---

## Phase 3: Two-Stage Pipeline

### Двухэтапный поиск

Two-Stage Pipeline объединяет быстрый первый этап (recall) с точным вторым этапом (reranking через FlashRank) для оптимального баланса скорости и качества.

```bash
# Two-Stage поиск
python -m src.cli.main search "работа с транзакциями" --strategy two_stage

# Two-Stage с фильтрацией
python -m src.cli.main search "управление блокировками" \
    --strategy two_stage \
    --language ru \
    --doc-type developer_guide \
    -k 10
```

```python
# Python API: Two-Stage Pipeline
response = await components.search_manager.search(
    query="работа с транзакциями",
    strategy="two_stage",
    k=10,
    filter={"language": "ru"},
)

# Two-Stage автоматически:
# 1. Извлекает top-N кандидатов (быстрый recall)
# 2. Применяет FlashRank reranking (точная сортировка)
# 3. Возвращает top-k лучших результатов
```

### Contextual Retrieval (индексация с контекстом)

При индексации добавляет контекст всего документа к каждому чанку, улучшая качество поиска.

```bash
# Индексация с contextual retrieval
python -m src.cli.main index "path/to/document.pdf" --contextual

# Индексация директории с контекстом
python -m src.cli.main index "path/to/docs/" --contextual --recursive
```

```python
# Python API: Contextual Indexing
from src.pdf_framework.processing.contextual import ContextualProcessor

processor = ContextualProcessor(settings=components.settings)

# Добавить контекст к чанкам перед индексацией
enriched_chunks = await processor.enrich_chunks(
    chunks=chunks,
    document=document,
)

# Индексировать обогащённые чанки
result = await components.indexer.index_chunks(
    enriched_chunks,
    document_id=document.id,
)
```

---

## Phase 4: Evaluation

### Оценка качества поиска и RAG

Framework для автоматической оценки включает метрики RAG Triad и benchmark runner.

### CLI команда eval

```bash
# Запуск оценки на стандартном наборе данных
python -m src.cli.main eval --dataset "data/eval/benchmark.json"

# Оценка конкретной стратегии
python -m src.cli.main eval --dataset "data/eval/benchmark.json" --strategy hybrid

# Сравнение стратегий
python -m src.cli.main eval --dataset "data/eval/benchmark.json" \
    --strategy vector,hybrid,mmr,two_stage

# Вывод подробного отчёта
python -m src.cli.main eval --dataset "data/eval/benchmark.json" --verbose

# Сохранение результатов в файл
python -m src.cli.main eval --dataset "data/eval/benchmark.json" \
    --output "reports/eval_report.json"
```

### RAG Triad метрики

Три ключевые метрики для оценки качества RAG:

```python
from src.pdf_framework.evaluation.rag_triad import RAGTriadEvaluator

evaluator = RAGTriadEvaluator(settings=components.settings)

# Оценка одного ответа
result = await evaluator.evaluate(
    question="Что такое конфигуратор?",
    answer="Конфигуратор — это инструмент для разработки...",
    contexts=search_response.results,
)

print(f"Faithfulness:       {result.faithfulness:.2f}")   # Верность контексту
print(f"Answer Relevance:   {result.answer_relevance:.2f}")  # Релевантность ответа
print(f"Context Relevance:  {result.context_relevance:.2f}") # Релевантность контекста
```

### Benchmark Runner

```python
from src.pdf_framework.evaluation.benchmark import BenchmarkRunner

runner = BenchmarkRunner(
    settings=components.settings,
    search_manager=components.search_manager,
)

# Запуск бенчмарка
report = await runner.run(
    dataset_path="data/eval/benchmark.json",
    strategies=["vector", "hybrid", "mmr", "two_stage"],
)

# Вывод сводки
print(report.summary())

# Сохранение отчёта
report.save("reports/benchmark_results.json")
```

---

## Phase 5: Self-RAG Agent

Self-RAG автоматически контролирует качество поиска и генерации ответа.

### Document Grading

```bash
# Оценка релевантности документов
python -m src.cli.main ask "Что такое конфигуратор?" --verbose
```

**Verbose вывод:**
```
[GRADE] Document 1: relevant (score: 0.85)
[GRADE] Document 2: relevant (score: 0.72)
[GRADE] Relevance ratio: 0.78
```

### Query Rewriting

```bash
# Автоматическая переписка запроса при низкой релевантности
python -m src.cli.main ask "как сделать штуку с формами" --verbose
```

**Verbose вывод:**
```
[REWRITE] Original: как сделать штуку с формами
[REWRITE] Rewritten: как создать форму в управляемом приложении 1С
```

### Hallucination Check

```bash
# Проверка ответа на соответствие контексту
python -m src.cli.main ask "Когда вышла версия 8.3.26?" --verbose
```

**Verbose вывод:**
```
[HALLUCINATION] Check: grounded (yes)
[HALLUCINATION] Answer is supported by retrieved context
```

### Отключение Self-RAG

```bash
# Более быстрый ответ без Self-RAG
python -m src.cli.main ask "Что такое конфигуратор?" --no-self-rag
```

---

## Phase 6: GraphRAG (Global & Local Search)

### Local Search - поиск по ближайшим сущностям

```bash
# Local GraphRAG
python -m src.cli.main search "конфигуратор" --strategy graphrag_local --top-k 5
```

Local Search использует:
- Ближайшие сущности в графе
- Связи между сущностями
- Community summaries (если доступны)

### Global Search - высокоуровневые ответы

```bash
# Global GraphRAG
python -m src.cli.main search "архитектура платформы 1С" --strategy graphrag_global --top-k 5
```

Global Search выполняет:
- Map-reduce по всем community summaries
- Синтез высокоуровневого ответа
- Идеально для концептуальных вопросов

### Индексация с GraphRAG

```bash
# Индексация с графом и communities
python -m src.cli.main index "path/to/document.pdf" --graph --communities

# Индексация директории
python -m src.cli.main index "path/to/docs/" --graph --communities --recursive
```

---

## Phase 7: Parent-Child Retrieval

### Auto-Merge Strategy

```bash
# Parent-Child поиск (auto_merge)
python -m src.cli.main search "объекты конфигурации" --strategy auto_merge --top-k 5
```

**Как работает:**
1. Поиск по child chunks (~400 символов) - точный поиск
2. Возврат parent chunks (~2000 символов) - полный контекст
3. Auto-merge при 3+ child из одного parent

### Индексация с Parent-Child

```bash
# Индексация с parent-child структурой
python -m src.cli.main index "path/to/document.pdf" --parent-child

# Комбинированная индексация
python -m src.cli.main index "path/to/document.pdf" --parent-child --graph
```

---

## Phase 8: Adaptive RAG

### Автоматический выбор стратегии

```bash
# Adaptive RAG - автоматический выбор
python -m src.cli.main search "Что такое модуль?" --strategy adaptive --verbose
```

**Verbose вывод:**
```
[CLASSIFY] Query type: factual
[CLASSIFY] Complexity: simple
[ROUTE] Selected strategy: vector
```

### Query Decomposition

```bash
# Сложные вопросы автоматически decompose
python -m src.cli.main search "Сравните конфигуратор и пользовательский режим" \
    --strategy adaptive --verbose
```

**Verbose вывод:**
```
[DECOMPOSE] Sub-questions:
  1. Что такое конфигуратор?
  2. Что такое пользовательский режим?
  3. В чем различия между ними?
```

### Force Route

```bash
# Принудительный выбор стратегии
python -m src.cli.main search "архитектура" \
    --strategy adaptive \
    --force-route graphrag_global
```

---

## Phase 9: Conversational RAG

### Interactive Chat

```bash
# Запуск интерактивного чата
pdf-framework chat --strategy hybrid
```

**Команды чата:**
```
> Что такое конфигуратор?
(ответ)

> А какие у него функции?
(ответ с учётом контекста)

> /history
(история диалога)

> /clear
(очистка истории)

> /strategy vector
(смена стратегии)

> /quit
(выход)
```

### Streaming Responses

```bash
# Потоковый вывод ответа
python -m src.cli.main ask "Опишите архитектуру 1С:Предприятие" --stream
```

### Thread Management

```bash
# Чат с сохранением истории
pdf-framework chat --thread test-session-1 --strategy adaptive

# Продолжение предыдущей сессии
pdf-framework chat --thread test-session-1
```

---

## Phase 10: Layout-Aware Parsing

### Индексация с layout-aware

```bash
# Распознавание структуры документа
python -m src.cli.main index "path/to/document.pdf" --layout-aware

# Извлечение таблиц
python -m src.cli.main index "path/to/document.pdf" --extract-tables

# Извлечение изображений
python -m src.cli.main index "path/to/document.pdf" --extract-images
```

### Metadata из структуры

```python
# После layout-aware индексации
chunk.metadata.get('heading_level')  # h1, h2, h3...
chunk.metadata.get('section')  # секция документа
chunk.metadata.get('element_type')  # paragraph, table, image...
```

---

## Phase 11: Observability & Caching

### Tracing

```bash
# Включить verbose логирование
python -m src.cli.main search "конфигуратор" --verbose

# Trace сохраняется в data/traces/
```

### Cache Statistics

```bash
# Статистика кэша
pdf-framework cache stats
```

**Вывод:**
```
Cache Statistics:
  Embedding: 156 entries, 23% hit rate
  LLM: 42 entries, 67% hit rate
```

### Cache Management

```bash
# Очистить embedding cache
pdf-framework cache clear --type embedding

# Очистить LLM cache
pdf-framework cache clear --type llm

# Очистить весь кэш
pdf-framework cache clear --type all
```

### Metrics Dashboard

```bash
# Запуск сервера с метриками
pdf-framework server --port 8000

# Открыть http://localhost:8000/metrics/html
```

**Показывает:**
- Количество запросов
- Средняя задержка
- Hit rate кэша
- Использование стратегий

---

## Phase 12: Multi-Tenancy & Auth

### Tenant Management

```bash
# Создать тенант
pdf-framework tenant create --id company-a

# Список тенантов
pdf-framework tenant list

# Удалить тенант
pdf-framework tenant delete --id company-a
```

### JWT Authorization

```bash
# Генерация токена
pdf-framework auth token --tenant company-a --role admin

# Токен для viewer (только search/ask)
pdf-framework auth token --tenant company-a --role viewer

# Токен для editor (search/ask/index)
pdf-framework auth token --tenant company-a --role editor
```

### Индексация с tenant

```bash
# Индексация для конкретного тенанта
pdf-framework index "path/to/document.pdf" --tenant company-a

# Поиск в тенанте
pdf-framework search "конфигуратор" --tenant company-a
```

---

## Phase 13: RAPTOR & HyDE

### RAPTOR Tree

```bash
# Индексация с RAPTOR
python -m src.cli.main index "path/to/document.pdf" --raptor

# RAPTOR поиск
python -m src.cli.main search "общая концепция" --strategy raptor --top-k 5
```

**RAPTOR создаёт:**
- Level 0: оригинальные чанки
- Level 1+: суммаризированные кластеры

### HyDE (Hypothetical Document Embeddings)

```bash
# Поиск с HyDE
python -m src.cli.main search "как создать форму" \
    --strategy vector \
    --expand-query \
    --verbose
```

**Verbose вывод:**
```
[HyDE] Generating hypothetical document...
[HyDE] Hypothetical: Для создания формы в 1С:Предприятие...
[HyDE] Using hypothetical document for search
```

### Summary Index

```bash
# Индексация с summarization
python -m src.cli.main index "path/to/document.pdf" --summarize
```

---

## Phase 14: UI & Developer Experience

### Web UI

```bash
# Запуск backend
pdf-framework server --port 8000

# Запуск UI (отдельный терминал)
pdf-framework ui --port 7860 --api-url http://localhost:8000
```

**Открыть:** http://localhost:7860

**Вкладки:**
- **Chat** - Диалог с AI
- **Search** - Поиск с фильтрами
- **Documents** - Загрузка и индексация PDF
- **Graph** - Визуализация графа сущностей
- **Settings** - Статистика и конфигурация

### QuickRAG API

```python
from src.pdf_framework import QuickRAG

# 3-строчный usage
rag = QuickRAG()
rag.add("data/pdfs/Введение __ 1С_Предприятие 8.3.26. Документация.pdf")
answer = rag.ask("Что такое конфигуратор?")
print(answer)
```

### Async QuickRAG

```python
import asyncio
from src.pdf_framework import QuickRAG

async def main():
    rag = QuickRAG()
    await rag.aadd("data/pdfs/document.pdf")
    results = await rag.asearch("конфигуратор", k=3)
    answer = await rag.aask("Что это?")
    stats = await rag.astats()
    print(answer)

asyncio.run(main())
```

### OpenAI-Compatible API

```bash
# Запуск сервера
pdf-framework server --port 8000

# Chat completions (OpenAI формат)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "pdf-rag",
    "messages": [{"role": "user", "content": "Что такое конфигуратор?"}]
  }'
```

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed",
)

response = client.chat.completions.create(
    model="pdf-rag",
    messages=[{"role": "user", "content": "Что такое конфигуратор?"}],
)
print(response.choices[0].message.content)
```

### Query Suggestions

```bash
# Entity-based предложения
pdf-framework suggest --method entity

# Frequency-based (по истории запросов)
pdf-framework suggest --method frequency

# LLM-based предложения
pdf-framework suggest --query "конфигуратор 1С" --method llm --top-k 5
```

---

## Phase 15: Image Understanding & Multimodal RAG

### Извлечение и описание изображений

При индексации PDF изображения автоматически извлекаются и описываются через Claude Vision API.

```bash
# Индексация с извлечением изображений
python -m src.cli.main index "path/to/document.pdf" --extract-images

# Комбо: текст + изображения + граф
python -m src.cli.main index "path/to/document.pdf" \
    --extract-images --graph --communities
```

### Как это работает

1. **Извлечение** — PyMuPDF извлекает изображения (min 50×50px)
2. **Vision API** — Claude Sonnet 4.5 описывает каждое изображение
3. **System Prompt** — OCR-транскриптор с few-shot примером для таблиц
4. **Chunking** — Описания становятся отдельными чанками с `page_number`
5. **Индексация** — Image chunks индексируются вместе с текстовыми (dense + BM25)

### Результаты на Глава 5

| Метрика | Значение |
|---------|----------|
| Image chunks | 119 |
| Средняя длина описания | 1237 символов |
| Markdown таблицы | 97/119 (81.5%) |
| Формат таблиц | `\|` markdown |

### Python API

```python
from src.pdf_framework.processing.image_extractor import ImageExtractor

extractor = ImageExtractor(settings=components.settings.vision)

# Извлечь и описать изображения
image_chunks = await extractor.extract_and_describe(
    pdf_path="path/to/document.pdf",
)

for chunk in image_chunks:
    print(f"Page {chunk.metadata.get('page_number')}: {chunk.content[:100]}...")
```

---

## Phase 16: BM25 Lexical Search + Hybrid Fusion

### BM25 поиск

BM25 — полнотекстовый лексический поиск через SQLite FTS5 с русской морфологией (pymorphy3).

```bash
# BM25 поиск (5-14ms, в 50-60× быстрее vector)
python -m src.cli.main search "модуль внешнего соединения" --strategy bm25

# BM25 с фильтрацией
python -m src.cli.main search "регистр накопления" --strategy bm25 --language ru
```

### Hybrid Search (BM25 + Vector + Graph)

```bash
# Hybrid = RRF(vector, bm25, graph) — лучшее качество
python -m src.cli.main search "роли и права доступа" --strategy hybrid -k 10
```

**Как работает Hybrid Search (Phase 24: Qdrant Native):**
1. **Prefetch dense** — семантический поиск через E5-large embeddings
2. **Prefetch BM25** — лексический поиск через Qdrant sparse vectors
3. **RRF Fusion** — server-side Reciprocal Rank Fusion в Qdrant
4. **Graph merge** — добавление результатов из графа знаний

### Русская морфология

pymorphy3 лемматизация обеспечивает корректный поиск по русским словоформам:

```
"регистром" → находит "регистр"
"накопления" → находит "накопление"
"справочников" → находит "справочник"
```

### Python API

```python
# BM25 поиск
response = await components.search_manager.search(
    query="модуль внешнего соединения",
    strategy="bm25",
    k=10,
)

# Hybrid (vector + BM25 + graph)
response = await components.search_manager.search(
    query="роли и права доступа",
    strategy="hybrid",
    k=10,
)
```

### Пересборка BM25 индекса

```bash
# Через скрипт (пересобирает FTS5 из Qdrant)
python build_bm25_index.py

# Через API
curl -X POST http://localhost:8000/documents/rebuild-bm25

# Через UI — кнопка «Пересобрать BM25» на вкладке Documents
```

---

## Phase 17: Semantic Caching

### Семантический кэш

Если новый запрос >= 0.95 похож на кэшированный, возвращаем кэш без пересчёта.

```bash
# Первый запрос: ~38 секунд (embedding + LLM)
python -m src.cli.main search "конфигуратор 1С"

# Повторный/похожий запрос: < 1 секунды (из кэша)
python -m src.cli.main search "конфигуратор в 1С Предприятие"
```

### Управление кэшем

```bash
# Статистика кэша
curl http://localhost:8000/cache/stats

# Очистка всего кэша
curl -X DELETE http://localhost:8000/cache/clear

# Очистка при переиндексации — автоматическая
```

### Python API

```python
from src.pdf_framework.search.semantic_cache import SemanticCache

cache = SemanticCache(
    threshold=0.95,  # cosine similarity порог
    ttl=3600,        # TTL в секундах (1 час)
)

# Проверить кэш
cached = await cache.get(query="конфигуратор 1С", strategy="hybrid")
if cached:
    return cached  # < 1ms

# Сохранить в кэш
await cache.put(
    query="конфигуратор 1С",
    strategy="hybrid",
    response=search_response,
)
```

---

## Phase 18: Incremental Indexing

### Инкрементальная индексация

Индексируются только изменённые документы и чанки (delta indexing).

```bash
# Инкрементальная индексация (по умолчанию)
python -m src.cli.main index "path/to/document.pdf"
# → Индексирует только изменённые чанки

# Полная переиндексация
python -m src.cli.main index "path/to/document.pdf" --full-reindex
```

### File Watcher

```bash
# Автоматический мониторинг директории
python -m src.cli.main watch "data/pdfs/"
# → При изменении/добавлении PDF → автоматическая переиндексация
```

### Версионирование документов

```python
from src.pdf_framework.processing.versioning import DocumentVersioning

versioning = DocumentVersioning()

# Проверить, изменился ли документ
is_changed = await versioning.has_changed(
    document_id="doc_123",
    content_hash="sha256:abc...",
)

if is_changed:
    # Delta: индексировать только новые/изменённые чанки
    await indexer.index_delta(new_chunks, document_id="doc_123")
```

---

## Phase 19: Deep Research Agent

### Глубокое исследование

Deep Research Agent декомпозирует сложные вопросы на подзадачи и проводит итеративный поиск.

```bash
# Deep Research (многошаговый поиск)
python -m src.cli.main research "Сравните все типы модулей в 1С и их области применения"
```

### Как работает

1. **Planner** — разбивает вопрос на 3-5 подвопросов
2. **Multi-Step Retrieval** — итеративный поиск по каждому подвопросу
3. **Quality Checker** — проверяет полноту найденной информации
4. **Synthesizer** — синтезирует финальный ответ с цитированием источников

### Python API

```python
from src.pdf_framework.agents.deep.research_agent import DeepResearchAgent

agent = DeepResearchAgent(
    search_manager=components.search_manager,
    settings=components.settings,
)

result = await agent.research(
    question="Сравните все типы модулей в 1С и их области применения",
    max_steps=5,
)

print(result.answer)
print(f"Sources: {len(result.sources)}")
print(f"Sub-questions: {result.sub_questions}")
```

---

## Phase 20: AutoRAG Optimization

### Автоматическая оптимизация параметров RAG

```bash
# Запуск AutoRAG на benchmark наборе
python -m src.cli.main autorag --dataset "data/eval/benchmark.json"

# С ограничением grid
python -m src.cli.main autorag --dataset "data/eval/benchmark.json" \
    --strategies vector,hybrid,bm25 \
    --k-values 3,5,10
```

### Python API

```python
from src.pdf_framework.evaluation.autorag import AutoRAGRunner, ParameterGrid

# Определить сетку параметров
grid = ParameterGrid(
    strategies=["vector", "hybrid", "bm25", "mmr"],
    k_values=[3, 5, 10],
    rerank=[True, False],
)

runner = AutoRAGRunner(
    search_manager=components.search_manager,
    grid=grid,
)

# Запуск оптимизации
results = await runner.run(dataset_path="data/eval/benchmark.json")

# Лучшая конфигурация
best = results.best_config()
print(f"Best: strategy={best.strategy}, k={best.k}, rerank={best.rerank}")
print(f"Score: {best.score:.4f}")
```

---

## Phase 21: RAGAS Evaluation

### Оценка через RAGAS framework

```bash
# Запуск RAGAS оценки
python -m src.cli.main eval --dataset "data/eval/benchmark.json" --evaluator ragas

# Regression testing (сравнение с предыдущей версией)
python -m src.cli.main eval --dataset "data/eval/benchmark.json" \
    --evaluator ragas --compare-with "reports/prev_eval.json"
```

### Python API

```python
from src.pdf_framework.evaluation.ragas_adapter import RAGASAdapter

adapter = RAGASAdapter(settings=components.settings)

# Оценка
result = await adapter.evaluate(
    questions=["Что такое конфигуратор?"],
    answers=["Конфигуратор — это..."],
    contexts=[retrieved_contexts],
    ground_truths=["Конфигуратор — средство разработки..."],
)

print(f"Faithfulness: {result.faithfulness:.2f}")
print(f"Answer Relevancy: {result.answer_relevancy:.2f}")
print(f"Context Precision: {result.context_precision:.2f}")
```

---

## Phase 22: Self-Learning Feedback

### Пользовательская обратная связь

```bash
# Отправить feedback через API
curl -X POST http://localhost:8000/feedback/ \
    -H "Content-Type: application/json" \
    -d '{"query": "конфигуратор", "result_id": "chunk_123", "score": 5, "comment": "точный ответ"}'
```

### Как работает

1. **Feedback Store** — сохраняет оценки пользователей (1-5 stars)
2. **Few-Shot** — лучшие примеры (5 stars) используются как few-shot в промптах
3. **Score Boost** — документы с позитивным фидбеком получают boost при поиске

### Python API

```python
from src.pdf_framework.feedback.store import FeedbackStore

store = FeedbackStore()

# Записать feedback
await store.add(
    query="конфигуратор",
    chunk_id="chunk_123",
    score=5,
    comment="Отличный ответ",
)

# Получить лучшие примеры для few-shot
examples = await store.get_best_examples(query="конфигуратор", top_k=3)
```

---

## Phase 23: Production Hardening (Qdrant)

### Миграция на Qdrant

Framework перешёл с ChromaDB на Qdrant для production-grade vector storage.

```bash
# Запуск Qdrant через Docker
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/data/qdrant_storage:/qdrant/storage \
    qdrant/qdrant:v1.15.5
```

```env
# .env
VECTOR_STORE__PROVIDER=qdrant
VECTOR_STORE__QDRANT_URL=http://localhost:6333
VECTOR_STORE__QDRANT_COLLECTION=pdf_documents
```

### Rate Limiting

```env
# Ограничение запросов
RATE_LIMIT__ENABLED=true
RATE_LIMIT__REQUESTS_PER_MINUTE=60
RATE_LIMIT__BURST=10
```

---

## Phase 24: Qdrant Native BM25

### Нативный BM25 через sparse vectors

Qdrant 1.15.5 поддерживает BM25 через sparse vectors с server-side inference.

```python
# Коллекция создаётся с dense + sparse vectors
# dense: E5-large (1024d), distance=COSINE
# bm25: SparseVectorParams(modifier=Modifier.IDF)

# Hybrid search — server-side RRF
results = await vector_store.hybrid_search(
    query_embedding=embedding,
    query_text="роли и права доступа",
    k=10,
)
```

### Пересборка FTS5 из Qdrant

```bash
# Пересобрать FTS5 индекс из текущих данных Qdrant
python build_bm25_index.py

# Через API
curl -X POST http://localhost:8000/documents/rebuild-bm25
```

### UI

На вкладке **Documents** в Web UI доступна кнопка **«Пересобрать BM25»** для ручной синхронизации FTS5 индекса с Qdrant.

---

## Текущий стек технологий

| Компонент | Технология | Описание |
|-----------|------------|----------|
| **Main LLM** | Claude Opus 4.6 | Генерация ответов, RAG agent |
| **Fast LLM** | Claude Sonnet 4.5 | Grading, rewriting, hallucination check |
| **Vision** | Claude Sonnet 4.5 | Описание изображений из PDF |
| **Embedding** | intfloat/multilingual-e5-large | 1024 dims, multilingual, prefix "query:"/"passage:" |
| **Vector Store** | Qdrant 1.15.5 (Docker) | Dense (1024d) + BM25 sparse vectors + IDF |
| **BM25** | SQLite FTS5 + pymorphy3 | Лексический поиск, русская лемматизация |
| **Graph Store** | NetworkX | Граф знаний, entity extraction |
| **Web Framework** | FastAPI | REST API + OpenAI-compatible endpoints |
| **UI** | Gradio | 5 вкладок: Chat, Search, Documents, Graph, Settings |
| **Reranker** | BAAI/bge-reranker-v2-m3 | Multilingual cross-encoder reranking |

### Текущий индекс

| Метрика | Значение |
|---------|----------|
| PDF документы | 1 (Глава 5) |
| Всего чанков | 953 (834 текст + 119 изображений) |
| Qdrant коллекция | dense (1024d) + bm25 sparse + IDF modifier |
| FTS5 индекс | 953 чанков, pymorphy3 lemmatization |
| BM25 латентность | 5-14ms (vs vector 415-475ms) |
| Покрытие страниц | 218/218 (100%) |

---

## Проверка работы

### Тесты

```bash
# Unit-тесты
pytest tests/ -v
```

### Проверка поиска

```bash
# Vector search
python -m src.cli.main search "конфигуратор" --strategy vector

# BM25 search (быстрый)
python -m src.cli.main search "модуль внешнего соединения" --strategy bm25

# Hybrid search (лучшее качество)
python -m src.cli.main search "роли и права доступа" --strategy hybrid

# Проверка image chunks
python -m src.cli.main search "таблица регистров" --strategy hybrid -k 10
```

### Проверка API

```bash
# Health check
curl http://localhost:8000/health

# Search через API
curl -X POST http://localhost:8000/search/ \
    -H "Content-Type: application/json" \
    -d '{"query": "конфигуратор", "strategy": "hybrid", "k": 5}'

# Cache stats
curl http://localhost:8000/cache/stats
```

### Проверка metadata

```bash
python -c "
import asyncio
from src.api.dependencies.components import Components

async def check():
    c = Components()
    await c.initialize()
    r = await c.search_manager.search('документация', k=1)
    print(r.results[0].chunk.metadata)

asyncio.run(check())
"
```

---

## Troubleshooting

### Reranker не загружается

```bash
pip install --upgrade sentence-transformers

# Альтернативная модель в .env:
AGENT__RERANKER_MODEL=ms-marco-MiniLM-L-6-v2
```

### Медленный поиск

```bash
# BM25 — самый быстрый (5-14ms)
python -m src.cli.main search "query" --strategy bm25

# Vector без reranking
python -m src.cli.main search "query" --strategy vector --no-rerank

# Уменьшить top_k в .env:
AGENT__RERANKER_TOP_K=10
```

### BM25 возвращает 0 результатов

```bash
# Пересобрать FTS5 индекс из Qdrant
python build_bm25_index.py

# Или через API
curl -X POST http://localhost:8000/documents/rebuild-bm25

# Проверить синхронизацию
python -c "
from src.pdf_framework.search.bm25_store import BM25Store
import asyncio

async def check():
    store = BM25Store()
    await store.initialize()
    count = await store.count()
    print(f'BM25 chunks: {count}')

asyncio.run(check())
"
```

### Qdrant не доступен

```bash
# Проверить, что Docker контейнер запущен
docker ps | grep qdrant

# Запустить Qdrant
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/data/qdrant_storage:/qdrant/storage \
    qdrant/qdrant:v1.15.5

# Проверить здоровье
curl http://localhost:6333/healthz
```

### Embedding dimension mismatch

```bash
# Убедиться, что .env соответствует модели
# E5-large = 1024 dims
EMBEDDING__MODEL=intfloat/multilingual-e5-large
EMBEDDING__DIMENSIONS=1024

# ВАЖНО: E5 модели требуют prefix
# "query: " для поисковых запросов
# "passage: " для индексации документов

# При смене модели — полная переиндексация
python -m src.cli.main index "path/to/document.pdf" --full-reindex
```

### Image descriptions не генерируются

```bash
# Проверить Vision настройки
VISION__MODEL=claude-sonnet-4-5-20250929
VISION__MAX_TOKENS=2048

# Для PDF с 100+ изображениями увеличить timeout
# В коде или через переменные — timeout 1h+
```

### Фильтры не работают

```bash
# Переиндексировать с metadata enrichment
python reindex_with_graph.py
```

---

## REST API Endpoints

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/health` | Health check |
| `POST` | `/search/` | Поиск |
| `POST` | `/ask/` | RAG question-answering |
| `POST` | `/documents/index` | Индексация PDF |
| `POST` | `/documents/rebuild-bm25` | Пересборка BM25 FTS5 |
| `GET` | `/documents/` | Список документов |
| `DELETE` | `/documents/{id}` | Удаление документа |
| `GET` | `/cache/stats` | Статистика кэша |
| `DELETE` | `/cache/clear` | Очистка кэша |
| `POST` | `/feedback/` | Отправка feedback |
| `GET` | `/metrics/` | Метрики |
| `POST` | `/v1/chat/completions` | OpenAI-compatible API |
| `POST` | `/auth/token` | JWT токен |
| `GET` | `/graph/stats` | Статистика графа |

---

## Дополнительные ресурсы

- [ROADMAP_V3.md](ROADMAP_V3.md) - Полная roadmap v0.15.0 (24 фазы РЕАЛИЗОВАНО)
- [docs/roadmap/](../roadmap/) - Детальная документация по каждой фазе (15-25)
- [docs/api/](../api/) - API документация
- [docs/guides/](../guides/) - Руководства по интеграции

---

**Версия:** v0.15.0 (Phases 1-24 COMPLETE)
**Дата:** 2026-02-10
**Стек:** Qdrant + E5-large + Claude Opus 4.6 + BM25 (FTS5 + Qdrant sparse)
