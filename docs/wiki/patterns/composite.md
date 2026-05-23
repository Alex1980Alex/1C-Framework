---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b3-7b0c-973e-0f42275ddb12
---

# 1.8 Composite

**Где используется:** `search/strategies/hybrid_search.py`
**Ключевые классы:** `HybridSearchStrategy`
**Как работает:** Компонует Vector + Graph + BM25, объединяя результаты через Reciprocal Rank Fusion (RRF). Стратегия
сама является `BaseSearchStrategy`.
**Пример:**

```python
hybrid = HybridSearchStrategy(vector=vs, graph=gs, bm25=bs)
results = await hybrid.search("запрос")  # RRF fusion
```
