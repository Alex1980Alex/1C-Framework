---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b2-74bd-9647-f66374eaaeda
---

# 1.15 Change Detector

**Где используется:** `graph_store/change_detector.py`
**Ключевые классы:** `GraphChangeDetector`, `IncrementalGraphUpdater`
**Как работает:** Детектор сравнивает версии документов и находит дельту. Инкрементальный обновлитель применяет только
изменения к графу без полной перестройки.

---
