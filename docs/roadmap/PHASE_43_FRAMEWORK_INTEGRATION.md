# Phase 43: Framework Integration (v0.33.1)

> Based on analysis of `docs/rag_agent_frameworks_ru.md` — RAG agent frameworks landscape 2025-2026.

## Summary

Analyzed 22 recommendations from the RAG frameworks document against the current framework (42 phases).
**18 of 22 recommendations were already implemented.** Integrated the 3 most impactful missing features:

1. **ONNX/OpenVINO Embedding Acceleration** — ~7x CPU speedup
2. **LangGraph Checkpointing** — agent state persistence between sessions
3. **LangGraph Middleware** — token tracking, content guard, per-node metrics

## Gap Analysis

| Recommendation | Status Before | Status After |
|---|---|---|
| Think-Act-Observe cycle | Already done (Phase 5) | - |
| Corrective RAG | Already done (Phase 5) | - |
| Self-RAG | Already done (Phase 5) | - |
| Adaptive RAG | Already done (Phase 8) | - |
| Graph RAG | Already done (Phases 6, 38) | - |
| Plan-and-Execute | Already done (Phase 33) | - |
| Hybrid search | Already done (Phases 16, 24, 27) | - |
| GigaEmbeddings | Already done (Phase 31) | - |
| Qdrant | Already done (Phase 23) | - |
| DSPy optimization | Already done (Phase 34) | - |
| RAGAS evaluation | Already done (Phase 21) | - |
| Multi-agent orchestration | Already done (Phase 39) | - |
| Document discovery tools | Already done (Phase 37 MCP) | - |
| Conversation memory | Already done (Phase 9) | - |
| Web search fallback | Already done (Phase 37) | - |
| Query decomposition | Already done (Phases 26, 42) | - |
| Reranking | Already done (Phases 25, 35) | - |
| Adaptive chunking | Already done (Phase 2) | - |
| **ONNX/OpenVINO** | **Missing** | **Implemented** |
| **LangGraph Checkpointing** | **Missing** | **Implemented** |
| **LangGraph Middleware** | **Missing** | **Implemented** |
| Domain fine-tuning | Missing | Deferred (needs dataset) |

## Feature 1: ONNX/OpenVINO Embedding Backend

### Problem
Embedding generation on CPU is slow (~38 req/sec with PyTorch). The document recommends
ONNX/OpenVINO backends for ~7x speedup (~266 req/sec on CPU).

### Solution
Added `backend` field to `EmbeddingSettings`:
```env
EMBEDDING__BACKEND=onnx       # or "openvino" or "torch" (default)
```

sentence-transformers v2.3+ natively supports `backend="onnx"` and `backend="openvino"`.
The `LocalEmbeddingEngine._get_model()` now passes backend to `SentenceTransformer()`.

Requirements:
- ONNX: `pip install onnxruntime` (or `onnxruntime-gpu`)
- OpenVINO: `pip install openvino`

### Files Changed
- `src/pdf_framework/config.py` — added `backend` to `EmbeddingSettings`
- `src/pdf_framework/embeddings/providers/local.py` — pass `backend` to `SentenceTransformer()`

## Feature 2: LangGraph Checkpointing

### Problem
Agent state was ephemeral — lost between invocations. The document recommends
LangGraph checkpointing for state persistence, enabling:
- Resume long-running agent sessions
- Conversation continuity across API restarts
- Debugging by replaying agent steps

### Solution
`create_rag_agent()` now reads `settings.checkpointer` (already existed as config field):
- `"memory"` — in-memory `MemorySaver` (default, no persistence)
- `"sqlite"` — `SqliteSaver` to `data/agent_checkpoints.db`

When checkpointing is enabled, callers pass `config={"configurable": {"thread_id": "..."}}` to
`graph.ainvoke()` to enable per-thread state tracking.

### Files Changed
- `src/pdf_framework/agents/rag/agent.py` — added checkpointer to `graph.compile()`

## Feature 3: LangGraph Middleware (Token Tracking + Content Guard)

### Problem
No visibility into per-node token usage or LLM call costs within the agent pipeline.

### Solution
Created `middleware.py` with two callback handlers:

1. **TokenTracker** — accumulates input/output/cache tokens, latency, and call count per node
2. **ContentGuard** — warns on unusually long outputs

Both are attached to main_llm and fast_llm via `with_middleware()`. Each agent node calls
`token_tracker.set_node("node_name")` for per-node attribution.

Token usage is attached to `state["metadata"]["token_usage"]` at the end of generation.
The compiled graph also exposes `graph.token_tracker` for direct access.

### Files Changed
- `src/pdf_framework/agents/rag/middleware.py` — **NEW** (TokenTracker, ContentGuard, with_middleware)
- `src/pdf_framework/agents/rag/agent.py` — middleware integration, per-node tracking

## Configuration

```env
# ONNX acceleration (default: torch)
EMBEDDING__BACKEND=onnx

# LangGraph checkpointing (default: memory)
AGENT__CHECKPOINTER=sqlite

# All existing settings unchanged
```

## Verification

```python
# Test ONNX embedding
from src.pdf_framework.config import EmbeddingSettings
s = EmbeddingSettings(backend="onnx")
# Verify: model loads with ONNX runtime

# Test checkpointing
from src.pdf_framework.agents.rag.agent import create_rag_agent
agent = create_rag_agent(search_manager, settings=AgentSettings(checkpointer="sqlite"))
result = await agent.ainvoke({"question": "test"}, config={"configurable": {"thread_id": "t1"}})
# Verify: data/agent_checkpoints.db created

# Test middleware
print(agent.token_tracker.usage.to_dict())
# Verify: shows input_tokens, output_tokens, calls, per-node stats
```
