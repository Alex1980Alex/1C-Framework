---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
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
