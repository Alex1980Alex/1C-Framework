---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b4-7300-8cd1-f840e4b6814e
---

# 1.3 DI Container

**Где используется:** `api/dependencies/components.py`
**Ключевые классы:** `Components`
**Как работает:** Синглтон `Components` создаёт и связывает stores, engines и strategies. Функция `get_components()` возвращает готовый контейнер с инжектированными зависимостями.
**Пример:**
```python
c = await get_components()  # Components singleton
results = await c.search_manager.search("запрос", strategy="auto")
```
