---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b5-7113-82cc-d3bdb6de75d8
---

# 1.6 Factory

**Где используется:** `processing/pipeline.py`, `search/manager.py`, `agents/rag/agent.py`
**Ключевые классы:** `_create_splitter()`, `_create_reranker()`, `create_rag_agent()`, `get_loader()`
**Как работает:** Фабричные функции принимают конфигурацию и возвращают нужный объект, инкапсулируя логику выбора и
инициализации.
**Пример:**

```python
splitter = _create_splitter(settings)   # → SemanticTextSplitter / RecursiveTextSplitter
reranker = _create_reranker(settings)   # → LLMReranker / CrossEncoderReranker
```
