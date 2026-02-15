# Architecture Overview

## PDF Vector & Graph Framework

A framework for intelligent PDF document processing using vector databases (semantic search, RAG) and knowledge graphs (entity relations). Built with Python, LangChain, LangGraph, and FastAPI.

---

## Architecture Layers

```
┌───────────────────────────────────────────────────────────────────────┐
│                        Interface Layer                                │
│        CLI (Typer)  │  REST API (FastAPI)  │  MCP Server              │
├───────────────────────────────────────────────────────────────────────┤
│                      Orchestration Layer                              │
│  Components (DI) │ SearchManager │ RAG Agent │ Multi-Agent │ DSPy     │
├───────────────────────────────────────────────────────────────────────┤
│                      Business Logic Layer                             │
│  Loaders │ Pipeline │ Indexer │ Chains │ Reranking │ Evaluation       │
├───────────────────────────────────────────────────────────────────────┤
│                        Storage Layer                                  │
│  Qdrant (Vector+BM25) │ FTS5 (BM25 fallback) │ NetworkX (Graph)      │
├───────────────────────────────────────────────────────────────────────┤
│                      Infrastructure Layer                             │
│  Embeddings │ Cache (3 types) │ Observability │ Config │ Analytics    │
├───────────────────────────────────────────────────────────────────────┤
│                     Claude Code Integration                           │
│  Hooks (12) │ Skills (9) │ MCP Tools (12) │ Ralph Wiggum │ Triad     │
└───────────────────────────────────────────────────────────────────────┘
```

## Core Design Principles

- **Provider Pattern** — all stores extend abstract base classes (`*/base.py`)
- **Dependency Injection** — `Components` class assembles all providers
- **Async-first** — all I/O is `async`, sync libs wrapped with `asyncio.to_thread()`
- **Pydantic contracts** — data models in `schemas/` as single source of truth
- **Configuration** — `pydantic-settings` with `__` env delimiter

---

## Key Components

### Components (DI Container)

[components.py](../../src/api/dependencies/components.py) — central assembly point:

```python
class Components:
    loader: BaseLoader              # PDF loading (Hybrid/PyMuPDF/Docling)
    pipeline: ProcessingPipeline    # Splitting, cleaning, metadata
    embedding_engine: EmbeddingEngine  # E5 multilingual (1024d)
    vector_store: QdrantVectorStore # Dense + sparse vectors
    graph_store: NetworkXGraphStore # Knowledge graph
    indexer: DocumentIndexer        # Orchestrates indexing
    search_manager: SearchManager   # Routes to strategies
    bm25_store: BM25Store          # FTS5 lexical search
```

### Search Strategies

| Strategy | Class | Description |
|----------|-------|-------------|
| `vector` | `VectorSearchStrategy` | Cosine similarity via bi-encoder |
| `bm25` | `BM25SearchStrategy` | FTS5 lexical search (5-14ms) |
| `hybrid` | `HybridSearchStrategy` | Qdrant native RRF (dense + BM25 sparse) |
| `graph` | `GraphSearchStrategy` | Entity graph traversal |
| `mmr` | `MMRSearchStrategy` | Maximal Marginal Relevance |
| `two_stage` | `TwoStagePipeline` | Broad recall + precise reranking |
| `section` | Section-first pipeline | BM25 section detection + hybrid within section |
| `bm25` (FTS5) | `BM25SearchStrategy` | FTS5 fallback with pymorphy3 lemmatization |
| `raptor` | `RAPTORSearchStrategy` | Tree-based recursive summarization |
| `web` | `WebSearchStrategy` | External web search via MCP |
| `graphrag_auto` | `GraphRAGAutoStrategy` | Auto-select local/global/lightrag |
| `lightrag` | `LightRAGStrategy` | Entity/relation embedding search |

### Search Pipelines

- **Turbo Pipeline** — rule-based fast classify (0ms), BM25 early termination for simple queries
- **Section-Aware Pipeline** — two-pass: BM25 detects dominant section, hybrid searches within it
- **Hierarchical Pipeline** — section-first with breadcrumb context

### Reranking

| Reranker | Config | Latency |
|----------|--------|---------|
| LLM (Claude Sonnet) | `AGENT__RERANKER_TYPE=llm` | 1-3s |
| CrossEncoder | `AGENT__RERANKER_TYPE=cross_encoder` | 60-120s |
| FlashRank | Token-budget selection | <1s |
| ColBERT | Late interaction MaxSim | ~2s |

---

## Data Flows

### Indexing

```
PDF file
  → Hybrid Loader (PyMuPDF4LLM + fitz tables + Docling tables + Vision OCR)
  → ProcessingPipeline (split + clean + metadata + page numbers)
  → ImageExtractor (Claude Vision descriptions)
  → EmbeddingEngine (E5 multilingual, "passage: " prefix)
  → Qdrant (dense vectors + BM25 sparse vectors)
  → FTS5 (multi-column: title 10x, body 1x)
  → NetworkX (entity extraction + relation building)
```

### Search

```
Query
  → Fast Classify (rule-based, 0ms)
  → BM25 early check (simple queries → 5-14ms)
  → Qdrant hybrid (dense + sparse RRF)
  → Graph merge (if complex query)
  → LLM Reranker (Claude Sonnet via Z.AI)
  → Results with section context + page numbers
```

### RAG Agent (LangGraph)

```
Question
  → Query Analysis (classify + strategy selection)
  → Search (via SearchManager)
  → Relevance Grading (parallel, with Ralph self-correction)
  → Hallucination Check (grounded/not_grounded)
  → Answer Generation (with section references)
  → Enrichment Loop (FAIR-RAG completeness check)
```

---

## Storage

### Qdrant (Primary Vector Store)

- Dense vectors: 1024 dimensions (E5 multilingual)
- Sparse vectors: BM25 with IDF modifier
- Named vectors: `dense` + `bm25`
- Hybrid search: native RRF (dense + BM25 prefetch)
- IDs: UUID5 from deterministic string IDs

### FTS5 (BM25 Fallback)

- SQLite virtual table with multi-column schema
- Columns: title (weight 10x) + body (weight 1x)
- Lemmatization: pymorphy3 for Russian morphology
- Section titles stored as bold markdown (`**5.8.Справочники**`)

### NetworkX (Graph)

- Entities: 3166 nodes with typed properties
- Relations: 3528 edges with typed connections
- LightRAG: entity/relation embeddings in Qdrant `graph_embeddings` collection
- Graph batch mode for construction

---

## Configuration

Hierarchical via `pydantic-settings` (`src/pdf_framework/config/`):

```
Settings (root)
├── EmbeddingSettings        # model, backend (torch/onnx/openvino)
├── VectorStoreSettings      # provider (qdrant/chroma), collection
├── GraphStoreSettings       # provider (networkx/neo4j)
├── PDFSettings              # loader, splitter, chunk sizes
├── AgentSettings            # LLM, reranker, checkpointer
├── SearchSettings           # hybrid weights, MMR, BM25 threshold
├── InfrastructureSettings   # rate limits, batch sizes
├── ObservabilitySettings    # tracer, metrics
├── CacheSettings            # embedding/llm/document TTLs
├── AuthSettings             # JWT, RBAC
├── FeaturesSettings         # feature flags
├── ExternalSettings         # API keys, proxy URLs
└── APISettings / MCPServerSettings
```

Environment variables: `EMBEDDING__MODEL=intfloat/multilingual-e5-large`, `VECTOR_STORE__PROVIDER=qdrant`

---

## Claude Code Integration

The framework extends Claude Code CLI with a **Hooks + Skills + MCP Triad**:

### Structure (`.claude/`)

| Component | Count | Contents |
|-----------|-------|----------|
| **Hooks** | 12 | Ralph Wiggum (2), Guards (3), Domain routing (3), Enforcement (4) |
| **Skills** | 9 | Procedural (4), Knowledge with cache (4), Project-specific (1) |

All hooks and skills live in `.claude/` within the project directory.

### Ralph Wiggum Autonomous Loop

Prevents premature task completion:
- **Activator** detects complex tasks, sets iteration limits (8-15)
- **Stop hook** blocks exit until criteria are met
- **5 tiers**: Factory, Phase, Brainstorm, Research, Multi-step
- **Safety**: 2-hour staleness timeout, max iterations cap

### Self-Correcting LLM Calls

All 13 LLM integration points use feedback-driven retries:
- Max 2 attempts, pass failure reason to next attempt
- Validators: format, length, language, JSON structure, identity

---

## Implemented Phases (v1.5.0)

All 43 phases complete:

| Phase | Version | Feature |
|-------|---------|---------|
| 1-4 | v0.2-0.5 | Reranking, MMR, Contextual Retrieval, Evaluation |
| 5-14 | — | Self-RAG, GraphRAG, Parent-Child, Adaptive, Conversational, Layout, Observability, Multi-tenant, RAPTOR/HyDE, UI |
| 15 | v0.6.0 | Image Understanding (Claude Vision) |
| 16 | v0.7.0 | BM25 Lexical Search + Hybrid Fusion |
| 17 | v0.8.0 | Semantic Search Cache |
| 18 | v0.9.0 | Incremental Indexing (deterministic IDs, resume) |
| 19 | v0.10.0 | Deep Research Agent |
| 20 | v0.11.0 | AutoRAG Optimization |
| 21 | v0.12.0 | RAGAS Evaluation |
| 22 | v0.13.0 | Self-Learning Feedback |
| 23 | v0.14.0 | Production Hardening (Qdrant, PgVector, RBAC) |
| 24 | v0.15.0 | Qdrant Native BM25 + FTS5 Fallback |
| 25 | v0.16.0 | LLM Reranker (Claude via Z.AI) |
| 26 | v0.17.0 | Turbo Search Pipeline |
| 27 | v0.18.0 | Section-Aware Search |
| 28 | v0.19.0 | Resilient Hybrid Loader |
| 29 | v0.20.0 | Post-Indexing + Hierarchical Search |
| 30 | v0.21.0 | Hierarchical RAG |
| 31 | v0.23.0 | GigaEmbeddings (BGE-M3) |
| 32 | v0.24.0 | Multi-Document KB |
| 33 | v0.25.0 | Analytical RAG Agent |
| 34 | v0.26.0 | DSPy Prompt Optimization |
| 35 | v0.27.0 | ColBERT Late Interaction |
| 36 | v0.28.0 | Research Agent v2 (plan-tree DAG) |
| 37 | v0.29.0 | MCP + External Sources |
| 38 | v0.22.0 | LightRAG Mode |
| 39 | v0.30.0 | Multi-Agent Orchestration |
| 40 | v0.31.0 | Enterprise Analytics |
| 41 | v0.32.0 | Section-Referenced Answers |
| 42 | v0.33.0 | Answer Enrichment Loop (FAIR-RAG) |
| 43 | v0.33.1 | Framework Integration (ONNX/OpenVINO, LangGraph checkpointing) |

---

## Project Structure

```
src/
  pdf_framework/           # Core library
    config/                # Pydantic settings (12 modules)
    loaders/               # PDF loading (hybrid, pymupdf4llm, docling)
    processing/            # Splitting, cleaning, metadata, pipeline
    embeddings/            # Embedding providers + cache
    vector_store/          # Vector DB (qdrant, chroma, pgvector)
    graph_store/           # Graph DB + LightRAG
    search/                # Strategies, pipelines, reranking, BM25
    agents/                # RAG, analytical, research, multi-agent
    chains/                # QA chains, enrichment
    tools/                 # LangChain tools
    schemas/               # Pydantic models
    evaluation/            # RAGAS, benchmarks
    feedback/              # Self-learning store
    callbacks/             # Token tracking middleware
    indexing/              # Batch indexing, dedup
    analytics/             # QueryTracker, CostTracker, AuditLogger
    knowledge_base/        # Collections, document registry
    optimization/          # DSPy modules, MIPROv2, metrics
    multitenancy/          # Tenant store, tenant graph
    utils/                 # ID generator, helpers
  mcp_server/              # MCP server (12 tools)
  api/                     # REST API (FastAPI)
    routes/                # 14 routers: search, documents, graph, analytics, toc, auth, cache, chat, collections, feedback, health, metrics, openai_compat, optimization
    auth/                  # JWT, RBAC
    middleware/             # Rate limiting, token tracking
    dependencies/          # Components DI
  cli/                     # CLI interface (Typer)
  ui/                      # Streamlit UI
```

---

## Architecture Documents

| Document | Description |
|----------|-------------|
| [Integration Structure](core-framework-separation.md) | All 12 hooks + 9 skills in `.claude/` |
| [Triad Architecture](triad-architecture.md) | Hooks + Skills + MCP: when, how, and with what |
| [Hooks Reference](hooks-reference.md) | All 12 hooks: events, matchers, logic, signals |
| [Skills Reference](skills-reference.md) | All 9 skills: triggers, workflows, cache |
| [Ralph Wiggum](ralph-wiggum.md) | Autonomous loop system + self-correcting LLM retries |

## See Also

- [Roadmap V3](../ROADMAP_V3.md) — full phase roadmap
- [Usage Guide](../USAGE_GUIDE.md) — getting started
- [API Documentation](../api/) — REST API reference
