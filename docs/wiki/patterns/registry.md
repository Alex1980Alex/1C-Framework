---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b8-7315-83cd-a6c6d4074c52
---

# 1.5 Registry

**Где используется:** `search/manager.py`, `loaders/templates/base.py`, `knowledge_base/document_registry.py`
**Ключевые классы:** `SearchManager` (стратегии), `TEMPLATE_REGISTRY` (шаблоны парсинга), `DocumentRegistry` (документы)
**Как работает:** Каждый реестр — `dict[str, type]` с методами `register`/`get`. Позволяет динамически подключать новые компоненты.
**Пример:**
```python
TEMPLATE_REGISTRY["research_paper"] = ResearchPaperTemplate
tpl = get_template("research_paper")
```
