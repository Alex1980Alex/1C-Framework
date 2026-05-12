---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8ba-799a-9257-9ceaf9c20d35
---

# 1.12 Singleton

**Где используется:** `config/_base.py`, `api/dependencies/components.py`
**Ключевые классы:** `get_settings()`, `get_components()`
**Как работает:** Глобальные точки доступа гарантируют единственный экземпляр конфигурации и контейнера компонентов в рамках процесса.
