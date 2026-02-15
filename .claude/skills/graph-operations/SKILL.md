# Graph Operations

## Когда использовать
- "граф знаний", "сущности", "связи", "entities"
- "LightRAG", "GraphRAG", "graph traversal"
- Построение графа, поиск по графу, entity extraction

## Режимы поиска по графу

| Режим | Стоимость | Латентность | Когда |
|-------|-----------|------------|-------|
| **LightRAG** | ~100 tokens | <500ms | Простые/средние вопросы (default) |
| **GraphRAG Local** | ~2000 tokens | 2-5s | Сложные вопросы с контекстом |
| **GraphRAG Global** | ~5000 tokens | 5-10s | Тематические обзоры, map-reduce |
| **Auto** | varies | varies | Классификатор → LightRAG или Full |

## LightRAG (Phase 38)

Поиск по embeddings сущностей/связей в Qdrant `graph_embeddings` collection:
- 6694 точек (3166 entities + 3528 relations)
- Entity text: `"EntityName (TYPE): key=val"`
- Relation text: `"Source -[TYPE]-> Target: key=val"`
- Auto-select: simple/moderate → LightRAG, complex/thematic → Full GraphRAG

## Операции

```python
# Построение графа из чанков
builder = GraphBuilder(extractor, graph_store, concurrency=5)
stats = await builder.build_from_chunks(chunks)

# Построение entity embeddings
entity_builder = EntityEmbeddingBuilder(embedding_engine, lightrag_settings)
await entity_builder.build(graph_store)

# Поиск соседей
neighbors = await graph_store.get_neighbors(entity_id, depth=2)

# Поиск пути
path = await graph_store.find_path(source_id, target_id, max_depth=5)
```

## Конфиг

```env
GRAPHRAG__COMMUNITY_DETECTION_ENABLED=true
GRAPHRAG__LEIDEN_RESOLUTION=1.0
GRAPHRAG__LOCAL_SEARCH_DEPTH=1
GRAPHRAG__GLOBAL_SEARCH_MAX_COMMUNITIES=20
LIGHTRAG__ENABLED=true
LIGHTRAG__ENTITY_TOP_K=10
LIGHTRAG__RELATION_TOP_K=10
LIGHTRAG__AUTO_SELECT_ENABLED=true
GRAPHSTORE__PROVIDER=networkx     # networkx|neo4j
```

## Диагностика

| Симптом | Причина | Решение |
|---------|---------|---------|
| Пустой граф | Entity extraction без результатов | Проверить LLM prompt + token limits |
| LightRAG fallback на vector | Нет entity embeddings | Запустить `entity_builder.build(graph_store)` |
| Дубли сущностей | Dedup key mismatch | Ключ: `name.lower().strip() + entity_type` |
| NetworkX медленный | >10K entities | Использовать `set_batch_mode(True)` + `flush()` |

## Файлы
- Base: `src/pdf_framework/graph_store/base.py`
- NetworkX: `src/pdf_framework/graph_store/providers/networkx_store.py`
- Builder: `src/pdf_framework/graph_store/construction/builder.py`
- Entity embeddings: `src/pdf_framework/graph_store/entity_embeddings.py`
- Strategies: `src/pdf_framework/search/strategies/graph_search.py`, `graphrag_light.py`, `graphrag_global.py`, `graphrag_auto.py`
- Extractor: `src/pdf_framework/processing/extractors/entity_extractor.py`
