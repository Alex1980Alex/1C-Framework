---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b7-7cf8-82d1-cb2f3474adc1
---

# 1.1 Provider Pattern

**Где используется:** `vector_store/`, `graph_store/`, `embeddings/`, `loaders/` (4 домена)
**Ключевые классы:** `BaseVectorStore`, `BaseGraphStore`, `BaseEmbeddingEngine`, `BaseLoader`
**Как работает:** Каждый домен изолирован: абстрактный интерфейс в `base.py` и конкретные реализации в `providers/`.
Фабричные функции скрывают детали инстанцирования от клиента.
**Пример:**

```python
store = get_vector_store(settings)      # → QdrantVectorStore / ChromaVectorStore
engine = get_embedding_engine(settings) # → LocalEmbeddingEngine / JinaEmbeddingEngine
```
