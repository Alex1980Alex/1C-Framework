# P1 Search Quality — Implementation Analysis

**Domain:** rag, search
**Category:** analysis
**Created:** 2026-02-16
**Source:** `docs/roadmap/GAP_P1_SEARCH_QUALITY.md`

## Summary

P1 covers 4 phases (47-50) targeting search quality. Overall: ~30% implemented.
- Q3 (Streaming) ~80% done — SSE works, WebSocket missing
- Q1 (Embedding) ~40% — infrastructure ready, Jina provider missing
- Q2 (Late Chunking) 0% — blocked by Q1
- Q4 (Contextual Retrieval) 0% — independent, not started

## Q1 — Embedding Upgrade (Phase 47): ~40%

### Already Implemented
- `src/pdf_framework/embeddings/providers/local.py` — E5 multilingual-e5-large (1024d)
- `src/pdf_framework/embeddings/providers/giga.py` — Giga-Embeddings-instruct + BGE-M3
- `src/pdf_framework/config/embedding.py` — provider enum: `openai | voyage | local | giga`
- ONNX/OpenVINO backend support (Phase 43): `EMBEDDING__BACKEND=onnx|openvino|torch`
- Factory pattern in `src/pdf_framework/embeddings/__init__.py`

### Missing
- `JinaEmbeddingProvider` — no `providers/jina.py`
- `"jina"` not in provider enum, no `JINA_API_KEY` config
- `scripts/embedding_benchmark.py` — not created
- `scripts/migrate_embeddings.py` — not created
- `data/eval/embedding_benchmark.json` (50 Q&A pairs) — not created
- Dimension truncation (matryoshka) — not implemented

### Notes
- Provider pattern well-established — adding Jina is straightforward (~100 lines)
- Jina-v3 target: 1024d, Late Chunking, MTEB 68.5%, multilingual
- Current E5: MTEB ~63% (2022 model, 2 generations behind)

## Q2 — Late Chunking (Phase 48): 0%

- `src/pdf_framework/embeddings/late_chunking.py` — does not exist
- Zero references to "late chunking" in codebase
- **Blocked by Q1** — Late Chunking is Jina-specific
- Concept: embed full doc → extract chunk embeddings by token spans → preserves cross-chunk context

## Q3 — Token Streaming (Phase 49): ~80%

### Already Implemented
- `src/pdf_framework/agents/rag/streaming.py` — `StreamingRAGRunner` (297 lines)
  - Event types: TOKEN, SOURCE, STATUS, ERROR, DONE
- `src/api/routes/search.py` — `/search/ask` accepts `stream: bool = False`
  - When `stream=true`: SSE via `StreamingResponse(media_type="text/event-stream")`
- `src/api/routes/chat.py` — full chat streaming with SSE

### Missing
- WebSocket endpoint `/ws/search` — no `routes/websocket.py`
- MCP `ask_question` streaming — returns full text, not streamed
- TTFT optimization (flush first token) — not explicit
- Progress events (retrieval %, grading %) — not implemented

### Notes
- Core streaming value (SSE for search) already works
- WebSocket is nice-to-have for bidirectional cancel support
- MCP protocol may not support streaming natively (check MCP spec)

## Q4 — Contextual Retrieval (Phase 50): 0%

### Missing Entirely
- `src/pdf_framework/processing/contextual_retrieval.py` — not created
- `contextual_content` field not in `src/pdf_framework/schemas/documents.py`
- `FEATURES__CONTEXTUAL_RETRIEVAL` not in `src/pdf_framework/config/features.py`
- No prompt template for context generation
- No SQLite context cache
- No cost optimization (prompt caching, concurrency limiter)

### Existing Infrastructure (reusable)
- Features config file exists: `src/pdf_framework/config/features.py`
- Pipeline: `src/pdf_framework/processing/pipeline.py` — extensible after split step
- Header propagation already adds `section_title` to chunks
- Ralph Wiggum self-correction pattern available (10 files, 13 points)
- LLM clients configured (Claude Haiku for economy)

### Notes
- Anthropic's Contextual Retrieval paper: +5-10% recall with context prefix
- Cost: ~$0.01/page with Haiku
- Independent of Q1/Q2 — can start anytime

## Recommended Implementation Order

1. **Q3** (1 day) — finish streaming: WebSocket + progress events. 80% already done.
2. **Q4** (2-3 days) — Contextual Retrieval. Independent, high impact (+5-10% recall).
3. **Q1** (2-3 days) — Jina-v3 provider + benchmark baseline + migration script.
4. **Q2** (1-2 days) — Late Chunking. After stable Jina provider.

**Critical path:** Q1 → Q2 (sequential). Q3 and Q4 are parallel/independent.
**Total estimate:** 6-9 days (matches roadmap).

## Checklist Status

- [ ] Jina-v3 provider: `EMBEDDING__PROVIDER=jina`
- [ ] Migration script for re-embedding
- [ ] recall@10 improvement ≥3% vs E5 baseline
- [ ] Late Chunking toggle
- [x] `/search/ask?stream=true` streams tokens (SSE)
- [ ] WebSocket `/ws/search`
- [ ] Contextual Retrieval context prefix
- [ ] BM25 + vector use contextual content
- [ ] Unit test coverage for new code
