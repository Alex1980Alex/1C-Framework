# BSL Intelligence v4 Roadmap — Index

**Date:** 2026-03-09 | **Status:** PLANNING

**Goal:** Maximize search, analysis, and coding quality for 1C Enterprise BSL files

**Current base:** Phases 44-57 (migration done), Qdrant + SQLite FTS5, Serena LSP, 12,838 docs

---

## Current State

| Component | Technology | Quality |
|-----------|-----------|---------|
| Code search | SQLite FTS5 + Qdrant (nomic 768d) | Medium - text search, no structure understanding |
| Code analysis | ast-grep-mcp + Serena LSP | Basic - patterns, symbols, no dependency graph |
| Coding | Claude + bsl-platform-context API | Good - knows 1C API, but no project context |
| Indexing | smart_index_bsl.py to SQLite FTS5 | Basic - whole file, no per-function splitting |
| Embeddings | nomic-embed-text (768d) | Outdated - not optimized for code |

### Key Problems

1. Search doesn't understand BSL structure - searches file text, not procedures/functions
2. No dependency graph - "which modules call BlockVehicle()?" impossible to answer
3. Embeddings not for code - nomic-embed-text is general purpose, loses code semantics
4. No context when coding - Claude can't see related modules and dependencies
5. No eval dataset - impossible to measure improvements

---

## Target Architecture

```
BSL files (2,004)
  |
  +-- [Phase 59] BSL Parser --> AST (procedures, functions, variables, calls)
  |                                 |
  |                                 +-- Symbol Index (Qdrant)
  |                                 +-- Call Graph (SQLite)
  |                                 +-- Dependency Graph
  |
  +-- [Phase 60] Code Embeddings --> Qwen3-Embedding (code-optimized)
  |                                 |
  |                                 +-- Qdrant collection: bsl_code_v3 (1024d)
  |
  +-- [Phase 62] Knowledge Graph --> 1C Objects <-> Modules <-> Subsystems
  |                                 |
  |                                 +-- SQLite graph
  |
  +-- [Phase 63] Contextual RAG --> Module context in search
  |
  +-- [Phase 64] Code Intelligence MCP --> call graph, impact analysis, dead code
  |
  +-- [Phase 65] Eval & Benchmark --> 100 query-result pairs
```

---

## Phases

| Phase | Name | Priority | Days | Depends On | Effect | File | Checklist |
|-------|------|----------|------|------------|--------|------|-----------|
| **58** | Eval Dataset and Baseline | CRITICAL | 1-2 | -- | Measurement | [PHASE_58.md](PHASE_58.md) | [Checklist](PHASE_58_CHECKLIST.md) |
| **59** | AST-based BSL Indexing | CRITICAL | 3-5 | -- | +44% recall | [PHASE_59.md](PHASE_59.md) | [Checklist](PHASE_59_CHECKLIST.md) |
| **60** | Code-Optimized Embeddings | HIGH | 2-3 | 58 | +55% recall | [PHASE_60.md](PHASE_60.md) | [Checklist](PHASE_60_CHECKLIST.md) |
| **61** | Call Graph and Dependencies | HIGH | 5-7 | 59 | New capability | [PHASE_61.md](PHASE_61.md) | [Checklist](PHASE_61_CHECKLIST.md) |
| **62** | 1C Object Knowledge Graph | MEDIUM | 4-6 | -- | Context | [PHASE_62.md](PHASE_62.md) | [Checklist](PHASE_62_CHECKLIST.md) |
| **63** | Contextual BSL Search | MEDIUM | 2-3 | 59,60,62 | +15-20% recall | [PHASE_63.md](PHASE_63.md) | [Checklist](PHASE_63_CHECKLIST.md) |
| **64** | Code Intelligence MCP | MEDIUM | 3-4 | 59,61,62 | Unified API | [PHASE_64.md](PHASE_64.md) | [Checklist](PHASE_64_CHECKLIST.md) |
| **65** | Hybrid Reranking BSL | MEDIUM | 2-3 | 60 | +10-15% precision | [PHASE_65.md](PHASE_65.md) | [Checklist](PHASE_65_CHECKLIST.md) |
| **66** | Coding Assistant | HIGH | 3-5 | 59,61,62 | Code quality | [PHASE_66.md](PHASE_66.md) | [Checklist](PHASE_66_CHECKLIST.md) |
| **67** | External Tools | LOW | 2-4 | -- | Ecosystem | [PHASE_67.md](PHASE_67.md) | [Checklist](PHASE_67_CHECKLIST.md) |

**Total: 27-42 days**

---

## Implementation Order

```
Sprint 1 (week 1-2): FOUNDATION
  +-- Phase 58: Eval Dataset
  +-- Phase 59: AST BSL Indexing

Sprint 2 (week 2-3): EMBEDDINGS + GRAPH
  +-- Phase 60: Qwen3 Embeddings
  +-- Phase 61: Call Graph

Sprint 3 (week 3-4): INTELLIGENCE
  +-- Phase 62: Object Knowledge Graph
  +-- Phase 63: Contextual Search
  +-- Phase 64: Code Intelligence MCP

Sprint 4 (week 4-5): POLISH
  +-- Phase 65: Hybrid Reranking
  +-- Phase 66: Coding Assistant
  +-- Phase 67: External Tools
```

---

## Target Metrics

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| Recall@5 (BSL search) | ~0.30-0.45 | >0.85 | 2-3x |
| Recall@10 | ~0.45-0.60 | >0.95 | 2x |
| MRR | ~0.25-0.35 | >0.75 | 2-3x |
| "Who calls X?" | Impossible | <10ms | New |
| Impact analysis | Impossible | <100ms | New |
| Dead code detection | Manual | Automatic | New |
| Context when coding | None | Automatic | New |
| Embeddings | nomic 768d | Qwen3 1024d | SOTA |

---

## Sources and Inspiration

### MCP Servers for Code Intelligence
- DeepContext MCP (github.com/Wildcard-Official/deepcontext-mcp)
- codebase-memory-mcp (github.com/DeusData)
- code-graph-mcp (github.com/entrepeneur4lyf)
- Code Pathfinder (codepathfinder.dev/mcp)
- claude-context (github.com/zilliztech)
- Context+ (github.com/ForLoopCodes)
- Axon (github.com/harshkedia177)

### 1C Tools
- bsl-parser (github.com/1c-syntax) - ANTLR4 BSL grammar
- bsl-language-server (github.com/1c-syntax) - LSP, 388 stars
- sonar-bsl-plugin (github.com/1c-syntax) - SonarQube, 252 stars
- mdclasses (github.com/1c-syntax) - 1C metadata parsing

### Embedding Models
- Qwen3-Embedding (github.com/QwenLM) - SOTA code + multilingual
- Jina Embeddings v5 (elastic.co)
- BGE-M3 (huggingface.co/BAAI)

### Claude Code Ecosystem
- awesome-claude-code (github.com/hesreallyhim)
- awesome-claude-code-toolkit (github.com/rohitg00)
- Best MCP Servers 2026 (builder.io/blog)
- RAG Best Practices (superlinked.com/vectorhub)
- Claude Code Best Practices (code.claude.com/docs/en/best-practices)
