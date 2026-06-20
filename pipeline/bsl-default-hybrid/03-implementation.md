# 03 — Реализация

- [`src/bsl/semantic_search/services/search.py`](../../src/bsl/semantic_search/services/search.py) — `_call_qdrant_search`: docstring + hybrid-ветка → RRF + 3 fallback-ветки.
- CLAUDE.md — нота «default = hybrid RRF» (исправление устаревшего «pure BM25»).
- Память `feedback-bsl-sparse-bm25-dominance` — помечена СУПЕРСЕДЕД (dense здоров, default = hybrid).
- ⚠ Прод-MCP `bsl-semantic-search` держит старый код до `/mcp reconnect` ([[feedback-mcp-stale-code-reconnect]]) — применить для боевого эффекта.
