---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b8-7132-9b90-355b57869308
---

# 1.9 Router / Classifier

**Где используется:** `search/routing/`
**Ключевые классы:** `QueryClassifier`, `StrategyRouter`, `SubQuestionDecomposer`
**Как работает:** Классификатор определяет тип запроса, роутер выбирает стратегию, декомпозер разбивает сложные вопросы на подзапросы.
**Пример:**
```python
classification = QueryClassifier.classify("сравни A и B")
decision = StrategyRouter.route(classification)  # → "hybrid"
```
