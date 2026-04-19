---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
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
