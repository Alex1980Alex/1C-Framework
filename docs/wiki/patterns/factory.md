---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 1.6 Factory

**Где используется:** `processing/pipeline.py`, `search/manager.py`, `agents/rag/agent.py`
**Ключевые классы:** `_create_splitter()`, `_create_reranker()`, `create_rag_agent()`, `get_loader()`
**Как работает:** Фабричные функции принимают конфигурацию и возвращают нужный объект, инкапсулируя логику выбора и инициализации.
**Пример:**
```python
splitter = _create_splitter(settings)   # → SemanticTextSplitter / RecursiveTextSplitter
reranker = _create_reranker(settings)   # → LLMReranker / CrossEncoderReranker
```
