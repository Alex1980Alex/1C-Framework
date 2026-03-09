# Phase 65: Hybrid Reranking BSL

**Priority:** MEDIUM | **Effort:** 2-3 days | **Depends on:** Phase 60 | **Effect:** +10-15% precision

**Goal:** 5-stage pipeline optimized for BSL code search.

---

## Pipeline Architecture

```
Query
  |
  +-- Stage 1: BM25 top-50 (5ms)
  |     SQLite FTS5, multi-column (symbol_name 10x, body 1x)
  |
  +-- Stage 2: Vector top-50 (50ms)
  |     Qdrant bsl_code_v3, Qwen3 embeddings
  |
  +-- Stage 3: RRF Fusion top-20 (1ms)
  |     Reciprocal Rank Fusion, k=60
  |
  +-- Stage 4: Call Graph Boost (5ms)
  |     PageRank score adjustment
  |
  +-- Stage 5: LLM Reranker top-5 (1-3s)
        Claude Sonnet via Z.AI
```

**Total latency: ~1-3.5s (dominated by LLM reranker)**

---

## Tasks

### Task 65.1: BM25 Stage (Stage 1)

#### 65.1.1 Multi-Column FTS5 for Symbols
- Columns: `symbol_name` (weight 10x), `module_path` (weight 5x), `body` (weight 1x)
- Tokenizer: unicode61 + trigram for partial matches
- Result: top-50 candidates with BM25 scores

#### 65.1.2 Query Preprocessing
- Detect query type: natural language vs code pattern vs symbol name
- Symbol name query: boost symbol_name column weight to 20x
- Code pattern: search in body with higher weight
- Natural language: balanced weights

### Task 65.2: Vector Stage (Stage 2)

#### 65.2.1 Qdrant Search
- Collection: `bsl_code_v3` (Qwen3 1024d)
- Instruction-prefixed query embedding
- Top-50 results with cosine scores
- Optional: filter by module_type, subsystem

#### 65.2.2 Query Expansion (Optional)
- For short queries: expand with synonyms
- Example: "блокировка" -> "блокировка, запрет, ограничение"
- Use embedding model for expansion candidates

### Task 65.3: RRF Fusion (Stage 3)

#### 65.3.1 Reciprocal Rank Fusion
- Merge BM25 and vector results
- Formula: `RRF(d) = sum(1 / (k + rank_i(d)))` where k=60
- Produce top-20 fused candidates

#### 65.3.2 Score Normalization
- Normalize RRF scores to [0, 1] range
- Track source (BM25-only, vector-only, both)

### Task 65.4: Call Graph Boost (Stage 4)

#### 65.4.1 PageRank Scoring
- Compute PageRank on call graph (Phase 61)
- Cache PageRank scores (recompute on graph update)
- Higher PageRank = more important/central procedure

#### 65.4.2 Score Adjustment
- `final_score = rrf_score * (1 + alpha * pagerank_score)`
- Alpha: tunable parameter (default 0.1)
- Effect: well-connected procedures ranked slightly higher

#### 65.4.3 Recency Boost (Optional)
- Recently modified files get slight boost
- `recency_factor = exp(-days_since_modification / 30)`
- Weight: 0.05 (subtle preference for recent code)

### Task 65.5: LLM Reranker (Stage 5)

#### 65.5.1 Reranker Prompt
- Send top-20 candidates to Claude Sonnet
- Prompt: "Given query '{query}', rank these BSL code snippets by relevance"
- Return top-5 with relevance scores

#### 65.5.2 BSL-Specific Instructions
- "Consider 1C Enterprise BSL conventions"
- "Prioritize procedures that directly implement the requested functionality"
- "Distinguish between helper utilities and main business logic"

#### 65.5.3 Cost Management
- Only invoke LLM reranker for complex/ambiguous queries
- Simple queries (exact symbol name match): skip to Stage 3
- Threshold: if BM25 top-1 score > 0.9, skip LLM reranker

---

## Configuration

```env
BSL_SEARCH__BM25_TOP_K=50
BSL_SEARCH__VECTOR_TOP_K=50
BSL_SEARCH__RRF_K=60
BSL_SEARCH__RRF_TOP_K=20
BSL_SEARCH__PAGERANK_ALPHA=0.1
BSL_SEARCH__LLM_RERANKER_TOP_K=5
BSL_SEARCH__LLM_RERANKER_SKIP_THRESHOLD=0.9
```

---

## Expected Effect

| Metric | Before (Phase 60) | After (Phase 65) | Improvement |
|--------|-------------------|-------------------|-------------|
| Precision@5 | ~0.65 | ~0.80 | +10-15% |
| MRR | ~0.60 | ~0.75 | +25% |
| Latency (simple) | ~50ms | ~60ms | Minimal |
| Latency (complex) | ~50ms | ~1-3s | LLM cost |

---

## Deliverables

- [ ] `src/bsl/search/pipeline.py` — 5-stage search pipeline
- [ ] `src/bsl/search/rrf_fusion.py` — RRF merging logic
- [ ] `src/bsl/search/pagerank_boost.py` — PageRank score adjustment
- [ ] `src/bsl/search/llm_reranker.py` — LLM reranking stage
- [ ] `src/bsl/search/query_classifier.py` — query type detection
- [ ] Configuration via `.env`
- [ ] A/B eval report

---

## Acceptance Criteria

1. 5-stage pipeline runs end-to-end
2. Simple queries (symbol name) resolve in <100ms (skip LLM)
3. Complex queries use LLM reranker, complete in <3.5s
4. Eval shows precision@5 improvement over Phase 60 baseline
5. PageRank scores cached and updated on graph change
6. Cost: LLM reranker invoked only when needed
