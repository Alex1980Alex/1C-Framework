---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 1.8 Composite

**Где используется:** `search/strategies/hybrid_search.py`
**Ключевые классы:** `HybridSearchStrategy`
**Как работает:** Компонует Vector + Graph + BM25, объединяя результаты через Reciprocal Rank Fusion (RRF). Стратегия сама является `BaseSearchStrategy`.
**Пример:**
```python
hybrid = HybridSearchStrategy(vector=vs, graph=gs, bm25=bs)
results = await hybrid.search("запрос")  # RRF fusion
```
