---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 1.14 Observer

**Где используется:** `feedback/collector.py`, `analytics/tracker.py`, `analytics/cost.py`
**Ключевые классы:** `FeedbackCollector`, `QueryTracker`, `CostTracker`
**Как работает:** Трекеры подписываются на события поиска и собирают метрики: запросы, стоимость, обратную связь — без влияния на основной поток.
