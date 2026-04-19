---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 1.11 State Machine

**Где используется:** `agents/rag/state.py`, `agents/rag/agent.py` (LangGraph)
**Ключевые классы:** `RAGState`
**Как работает:** Граф состояний LangGraph: `analyze → search → grade → rewrite → generate`. Переходы зависят от оценки релевантности (Self-RAG).
