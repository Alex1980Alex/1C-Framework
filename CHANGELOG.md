# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.5.0] - 2026-02-12

### Added
- Phase 43: Framework Integration — ONNX/OpenVINO embedding backends, LangGraph checkpointing, token tracking middleware

## [1.4.0] - 2026-02-11

### Added
- Phase 42: Answer Enrichment Loop — FAIR-RAG completeness check, sub-query generation, context enrichment
- Phase 41: Section-Referenced Answers — prompt rules + post-processing navigation block

## [1.3.0] - 2026-02-10

### Added
- Phase 40: Enterprise Analytics — QueryTracker, CostTracker, AuditLogger, analytics API (7 endpoints)
- Phase 39: Multi-Agent Orchestration — 4 agents (retriever, analyzer, synthesizer, verifier), verify-rewrite loop

## [1.2.0] - 2026-02-09

### Added
- Phase 38: LightRAG Mode — entity/relation embeddings in Qdrant, auto-selection classifier
- Phase 37: MCP + External Sources — web search integration, source fusion, 12 MCP tools

## [1.1.0] - 2026-02-08

### Added
- Phase 36: Research Agent v2 — plan-tree DAG, evidence graph, quality gates, session persistence
- Phase 35: ColBERT Late Interaction — token-level MaxSim, RAGatouille, 70/30 blending

## [1.0.0] - 2026-02-07

### Added
- Phase 34: DSPy Prompt Optimization — modules, metrics, MIPROv2 optimizer, A/B API
- Phase 33: Analytical RAG Agent — planner, evidence collector, comparator, structured output
- Phase 32: Multi-Document KB — collections, registry, batch indexing, scoped search

### Changed
- Version bump to 1.0.0 — all core features complete

## [0.30.0] - 2026-02-06

### Added
- Phase 31: GigaEmbeddings — giga provider, instruction prompting, BGE-M3
- Phase 30: Hierarchical RAG — section-first pipeline, breadcrumb context, section summaries, ToC API

## [0.21.0] - 2026-02-05

### Added
- Phase 29: Post-Indexing Improvements — GPU embeddings, chunk dedup, ToC parser, breadcrumb metadata, section-scoped search

## [0.19.0] - 2026-02-04

### Added
- Phase 28: Resilient Hybrid Loader — PyMuPDF4LLM + fitz tables + Docling tables + Level 4 Vision OCR + coverage verification

### Fixed
- Docling page loss on large PDFs (218 pages → only 100 indexed). Hybrid Loader achieves 100% coverage

## [0.18.0] - 2026-02-03

### Added
- Phase 27: Section-Aware Search — header propagation in chunks, FTS5 multi-column (title 10x), two-pass RRF

### Fixed
- BM25 FTS5 schema migration: old single-column → new multi-column (DROP + recreate)
- pymupdf4llm page numbering: pages already 1-based, removed double +1

## [0.17.0] - 2026-02-02

### Added
- Phase 26: Turbo Search Pipeline — rule-based fast classify (90% coverage, 0ms), BM25 early termination, parallel sub-queries

## [0.16.0] - 2026-02-01

### Added
- Phase 25: LLM Reranker — Claude Sonnet via Z.AI, replaces CrossEncoder (60-120s → 1-3s)

## [0.15.0] - 2026-01-31

### Added
- Phase 24: Qdrant Native BM25 + FTS5 Fallback — sparse vectors, hybrid_search, rebuild endpoint

### Changed
- Vector store switched from ChromaDB to Qdrant (Docker)
- BM25 sparse vectors stored natively in Qdrant alongside dense vectors

## [0.14.0] - 2026-01-30

### Added
- Phase 23: Production Hardening — Qdrant provider, PgVector provider, rate limiting middleware, RBAC (JWT + roles)

## [0.13.0] - 2026-01-29

### Added
- Phase 22: Self-Learning Feedback — feedback store, few-shot boosting, strategy weight tuning

## [0.12.0] - 2026-01-28

### Added
- Phase 21: RAGAS Evaluation — adapter, regression testing, error analysis, history tracking

## [0.11.0] - 2026-01-27

### Added
- Phase 20: AutoRAG Optimization — ParameterGrid, SmartGrid, Runner, Analyzer

## [0.10.0] - 2026-01-26

### Added
- Phase 19: Deep Research Agent — planner, synthesizer, quality checker

## [0.9.0] - 2026-01-25

### Added
- Phase 18: Incremental Indexing — deterministic IDs, delta indexing, file watcher, resume support

### Fixed
- Incomplete indexing: deterministic IDs + batched checkpointing + resume

## [0.8.0] - 2026-01-24

### Added
- Phase 17: Semantic Search Cache — query embedding cache with TTL

## [0.7.0] - 2026-01-23

### Added
- Phase 16: BM25 Lexical Search + Hybrid Fusion — FTS5 index, pymorphy3 lemmatization, header propagation

## [0.6.0] - 2026-01-22

### Added
- Phase 15: Image Understanding — Claude Vision for image descriptions, markdown table extraction (82% accuracy)

## [0.5.0] - 2026-01-20

### Added
- Phase 4: Evaluation Framework — Precision@k, Recall@k, MRR, NDCG@k, MAP, RAG Triad (LLM-as-a-Judge)
- Phases 5-14: Self-RAG, GraphRAG, Parent-Child, Adaptive, Conversational, Layout-Aware, Observability, Multi-tenant, RAPTOR/HyDE, UI/DX

## [0.4.0] - 2026-01-15

### Added
- Phase 3: Contextual Retrieval, FlashRank, Two-Stage Pipeline

## [0.3.0] - 2026-01-10

### Added
- Phase 2: MMR Strategy, Semantic Chunking, Query Expansion (LLM/synonym/HyDE)

## [0.2.0] - 2026-01-05

### Added
- Phase 1: Reranking (cross-encoder), Hybrid Weights, Metadata Filtering

## [0.1.0] - 2026-01-01

### Added
- Initial release: PDF loading (PyMuPDF), recursive splitting, local embeddings (sentence-transformers), ChromaDB vector store, NetworkX graph store, RAG agent (LangGraph), CLI, REST API, MCP Server
