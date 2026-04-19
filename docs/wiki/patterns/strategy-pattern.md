---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 1.2 Strategy Pattern

**Где используется:** `search/strategies/` (14 стратегий)
**Ключевые классы:** `SearchManager`, `VectorSearchStrategy`, `HybridSearchStrategy`, `AdaptiveSearchStrategy`
**Как работает:** `SearchManager` хранит реестр стратегий и делегирует вызов выбранной. Новые алгоритмы добавляются без изменения менеджера.
**Стратегии:** Vector, Hybrid, BM25, GraphRAG (local/global/light/auto), AutoMerge, Adaptive, RAPTOR, Web, Visual, TwoStage, Semantic
**Пример:**
```python
manager = SearchManager()
manager.register_strategy("hybrid", HybridSearchStrategy())
results = await manager.search("query", strategy="hybrid")
```
