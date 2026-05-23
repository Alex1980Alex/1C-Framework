---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8ba-7d5b-84d4-1abd314ca4e1
---

# 1.11 State Machine

**Где используется:** `agents/rag/state.py`, `agents/rag/agent.py` (LangGraph)
**Ключевые классы:** `RAGState`
**Как работает:** Граф состояний LangGraph: `analyze → search → grade → rewrite → generate`. Переходы зависят от оценки
релевантности (Self-RAG).
