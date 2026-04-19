---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 1.15 Change Detector

**Где используется:** `graph_store/change_detector.py`
**Ключевые классы:** `GraphChangeDetector`, `IncrementalGraphUpdater`
**Как работает:** Детектор сравнивает версии документов и находит дельту. Инкрементальный обновлитель применяет только изменения к графу без полной перестройки.

---
