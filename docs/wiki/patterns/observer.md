---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b7-7258-9302-623da5505f8b
---

# 1.14 Observer

**Где используется:** `feedback/collector.py`, `analytics/tracker.py`, `analytics/cost.py`
**Ключевые классы:** `FeedbackCollector`, `QueryTracker`, `CostTracker`
**Как работает:** Трекеры подписываются на события поиска и собирают метрики: запросы, стоимость, обратную связь — без влияния на основной поток.
