# Phase 60: Code-Optimized Embeddings

**Priority:** HIGH | **Effort:** 2-3 days | **Depends on:** Phase 58 | **Effect:** +55% recall

**Goal:** Replace nomic-embed-text with code-optimized model.

---

## Problem Statement

Current nomic-embed-text (768d) is a general-purpose text model:
- Not optimized for code semantics
- Weak on Russian language
- Misses structural patterns in BSL code
- 768d vs modern 1024d models

---

## Model Comparison

| Model | Size | Dims | Code MTEB | Multilingual | Local |
|-------|------|------|-----------|-------------|-------|
| nomic-embed-text (current) | 137M | 768 | Medium | Weak RU | Ollama |
| Qwen3-Embedding-0.6B | 600M | 1024 | Good | 100+ langs+code | Ollama |
| **Qwen3-Embedding-4B-Q4_K_M** | 2.5 GB | 1024 | **SOTA** | 100+ langs+code | Ollama |
| Voyage 3.5 | API | 1024 | Excellent | Good | No |
| Jina v5-text | 200M-600M | 1024 | Good | SOTA | Docker |
| BGE-M3 | 567M | 1024 | Good | 100+ | Ollama |

**Decision: Qwen3-Embedding-4B-Q4_K_M** — best quality/resource ratio for CPU-only setup.

---

## 3-Level Embedding Architecture

```
Level 1: DeepInfra API (primary)
  -> Qwen3-Embedding-4B, ~50ms, ~$0.05/10K embeddings
  -> For search and indexing when internet is available

Level 2: Ollama CPU (fallback)
  -> qwen3-embedding:4b-q4_K_M (2.5 GB, ~3 GB RAM)
  -> ~3-5s per embedding, $0
  -> When offline or API unavailable

Level 3: SQLite FTS5 (emergency fallback)
  -> Text search, ~5ms, $0
  -> Already implemented in Phase 45
```

**Why this works:**
- Same model (Qwen3-Embedding-4B) on all levels = compatible embeddings, single Qdrant index
- $0-5/month API cost
- Always works, even without internet and GPU
- Q4_K_M quantization: ~1-2% quality loss, 3x size reduction

---

## Tasks

### Task 60.1: Ollama Model Setup

#### 60.1.1 Pull Model
- `ollama pull qwen3-embedding:4b-q4_K_M` (2.5 GB download)
- Verify local inference works
- Benchmark: latency per embedding, memory usage

#### 60.1.2 Test Compatibility
- Generate embeddings from Ollama and DeepInfra
- Verify cosine similarity between same-model outputs
- Confirm single Qdrant collection works for both

### Task 60.2: Embedding Provider with Fallback Chain

#### 60.2.1 Provider Interface
- Implement `Qwen3EmbeddingProvider` extending base embedding provider
- Config: `EMBEDDING__PROVIDER=qwen3`
- Support batch embedding (multiple texts at once)

#### 60.2.2 Fallback Chain
- Level 1: Try DeepInfra API first
- Level 2: On API failure/timeout, fall back to Ollama local
- Level 3: On Ollama failure, fall back to FTS5 text search
- Logging: record which level was used for each request

#### 60.2.3 Configuration
- `EMBEDDING__QWEN3_API_URL` — DeepInfra endpoint
- `EMBEDDING__QWEN3_API_KEY` — DeepInfra API key
- `EMBEDDING__QWEN3_OLLAMA_MODEL` — Ollama model name
- `EMBEDDING__QWEN3_FALLBACK_ORDER` — comma-separated: `api,ollama,fts5`
- `EMBEDDING__QWEN3_API_TIMEOUT` — timeout in seconds (default: 10)

### Task 60.3: New Qdrant Collection

#### 60.3.1 Create Collection
- Name: `bsl_code_v3`
- Dense vectors: 1024 dimensions, cosine distance
- Payload index on: module_type, is_export, subsystem
- Keep old `bsl_code_v2` for A/B comparison

#### 60.3.2 Migration Strategy
- Dual-write during transition: index to both v2 and v3
- Switch search to v3 after eval confirms improvement
- Delete v2 after validation period

### Task 60.4: BSL Instruction Prompts

#### 60.4.1 Query Instructions
```
Instruct: Find BSL 1C Enterprise procedure or function by description
Query: {user_query}
```

#### 60.4.2 Passage Instructions
```
Instruct: BSL 1C Enterprise code module with procedures and functions
Passage: {chunk_content}
```

#### 60.4.3 Instruction Variants
- Test 3-5 instruction variants
- Measure recall difference on eval dataset
- Select best performing variant

### Task 60.5: Full Reindex

#### 60.5.1 Batch Reindex via DeepInfra
- Batch all 2,004 files (or ~15,000-20,000 symbols from Phase 59)
- Batch size: 32 texts per API call
- Progress tracking and resume on failure
- Estimated: ~30 min via API

#### 60.5.2 Offline Reindex via Ollama
- Fallback: overnight CPU reindex
- ~3-5s per embedding, ~15,000 symbols = ~12-18 hours
- Checkpoint every 100 symbols

### Task 60.6: A/B Evaluation

#### 60.6.1 Run Eval
- Run Phase 58 eval dataset against both collections
- Compare: nomic (v2) vs Qwen3 (v3)
- Per-category analysis

#### 60.6.2 Report
- Metrics comparison table
- Category-level breakdown
- Decision: switch or keep both

---

## Expected Results

| Metric | nomic (current) | Qwen3 (target) | Improvement |
|--------|----------------|-----------------|-------------|
| Recall@5 | ~0.45 | ~0.70 | +55% |
| Recall@10 | ~0.60 | ~0.85 | +42% |
| MRR | ~0.35 | ~0.60 | +71% |
| RU query quality | Weak | Strong | Significant |

---

## Cost

- DeepInfra API: ~$0-5/month
- Ollama local: $0 (CPU time only)

---

## Deliverables

- [ ] `src/bsl/embeddings/qwen3_provider.py` — embedding provider with fallback
- [ ] `src/bsl/embeddings/config.py` — Qwen3 configuration
- [ ] Qdrant collection `bsl_code_v3` created and indexed
- [ ] Instruction prompt variants tested
- [ ] A/B comparison report

---

## Acceptance Criteria

1. Fallback chain works: API -> Ollama -> FTS5
2. All 2,004+ files reindexed to `bsl_code_v3`
3. Eval shows measurable improvement over nomic baseline
4. Latency: <100ms for API, <5s for Ollama per query
5. Compatible embeddings between API and Ollama (same model)
