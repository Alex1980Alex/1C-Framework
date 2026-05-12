---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b1-7721-8ba9-5026f83d7b0d
---

# 1.4 Abstract Base Class (ABC)

**Где используется:** `vector_store/base.py`, `graph_store/base.py`, `embeddings/engine.py`, `loaders/base.py`
**Ключевые классы:** `BaseVectorStore`, `BaseGraphStore`, `BaseEmbeddingEngine`, `BaseLoader`
**Как работает:** Четыре контракта определяют обязательные методы: `add_documents`, `search`, `delete` и др. Провайдеры
наследуют ABC и реализуют все абстрактные методы.
**Пример:**

```python
class QdrantVectorStore(BaseVectorStore):
    async def add_documents(self, docs): ...
    async def search(self, query, k=5): ...
```
