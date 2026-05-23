---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8bc-789b-abbf-c59547c7aece
---

# 1.7 Template Method

**Где используется:** `loaders/templates/base.py`
**Ключевые классы:** `ParseTemplate`, `GenericTemplate`, `ResearchPaperTemplate`, `UserManualTemplate`
**Как работает:** Базовый класс определяет скелет парсинга, а подклассы переопределяют хуки `element_priorities`,
`skip_elements`, `chunk_size_overrides`.
**Пример:**

```python
class ResearchPaperTemplate(ParseTemplate):
    element_priorities = {"abstract": 10, "methodology": 8}
    skip_elements = ["acknowledgements"]
```
