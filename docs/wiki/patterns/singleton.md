---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 1.12 Singleton

**Где используется:** `config/_base.py`, `api/dependencies/components.py`
**Ключевые классы:** `get_settings()`, `get_components()`
**Как работает:** Глобальные точки доступа гарантируют единственный экземпляр конфигурации и контейнера компонентов в рамках процесса.
