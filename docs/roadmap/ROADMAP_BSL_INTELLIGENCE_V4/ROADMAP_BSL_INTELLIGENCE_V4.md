# BSL Intelligence v4 Roadmap

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

## Phase 58: BSL Eval Dataset and Baseline (Priority: CRITICAL)

**Goal:** Create eval dataset, establish baseline. Without this, cannot measure any improvement.

### Tasks

1. Create 100 pairs (query, expected_modules) by category:
   - Functionality search: "document posting handler" -> specific modules
   - API search: "FindByCode catalog" -> modules with this call
   - Business logic: "vehicle blocking" -> relevant modules
   - Pattern search: "temp table in query" -> modules
2. Auto-evaluation script: recall@5, recall@10, MRR, nDCG
3. Baseline metrics of current search (SQLite FTS5 + Qdrant nomic)

### Expected Baseline

| Metric | FTS5 | Qdrant nomic | Target |
|--------|------|-------------|--------|
| Recall@5 | ~0.30 | ~0.45 | >0.80 |
| Recall@10 | ~0.45 | ~0.60 | >0.90 |
| MRR | ~0.25 | ~0.35 | >0.70 |

### Effort: 1-2 days

---

## Phase 59: AST-based BSL Indexing (Priority: CRITICAL)

**Goal:** Parse BSL -> index by symbols (procedure, function), not by files.

### Problem Now

```
File: CommonModule.DocumentProcessing.bsl (500 lines, 15 procedures)
  -> One chunk in index -> one embedding -> loss of individual procedure semantics
```

### Target State

```
File: CommonModule.DocumentProcessing.bsl
  -> Procedure HandlePosting() -> separate embedding + metadata
  -> Function GetMovements() -> separate embedding + metadata
  -> ...15 symbols -> 15 embeddings with context
```

### Tasks

1. BSL AST Parser (Python)
   - Use ANTLR4 grammar from 1c-syntax/bsl-parser (github)
   - Or regex-based parser (simpler, sufficient for symbols)
   - Extract: procedures, functions, params, module vars, compilation directives
   - Extract calls: CommonModule.Method(), New Structure(), Query.Text = ...

2. Symbol-level chunking
   - Each symbol -> separate chunk
   - Metadata: name, type, export flag, params, module, subsystem
   - Context: first 3 lines + comment before procedure

3. Update smart_index_bsl.py with --ast mode

### Technology Options

| Approach | Pros | Cons |
|----------|------|------|
| ANTLR4 (Java) from bsl-parser | Full parser, 100% coverage | Requires Java |
| Regex-based (Python) | Simple, fast, sufficient | Can't parse complex constructs |
| Tree-sitter BSL grammar | Incremental, fast | DOES NOT EXIST - create from scratch |
| BSL Language Server API | Has LSP, symbols, diagnostics | Heavy (JVM), slow startup |

**Recommendation:** Start with regex-based parser, then migrate to ANTLR4.

### Regex-based BSL Parser (MVP)

```python
PROCEDURE_RE = r"(?:^|\n)\s*(Procedure|Function)\s+(\w+)\s*\(([^)]*)\)(?:\s+Export)?"
END_RE = r"(?:^|\n)\s*(EndProcedure|EndFunction)"
VAR_RE = r"(?:^|\n)\s*Var\s+(\w+)"
CALL_RE = r"(\w+)\.(\w+)\s*\("
```

Note: Russian-language equivalents also supported in actual implementation.

### Expected Effect

| Metric | Before (file) | After (symbol) | Improvement |
|--------|---------------|----------------|-------------|
| Recall@5 | ~0.45 | ~0.65 | +44% |
| Recall@10 | ~0.60 | ~0.80 | +33% |

### Effort: 3-5 days

---

## Phase 60: Code-Optimized Embeddings (Priority: HIGH) — IN PROGRESS

**Goal:** Replace nomic-embed-text with code-optimized model.

**Status:** Implementation started. Qwen3-Embedding installed, provider created, reindexing in progress.

### Model Comparison

| Model | Size | Dims | Code MTEB | Multilingual | Local |
|-------|------|------|-----------|-------------|-------|
| nomic-embed-text (current) | 137M | 768 | Medium | Weak RU | Ollama |
| **qwen3-embedding (actual)** | 4.7 GB | **4096** | **SOTA** | 100+ langs+code | Ollama |
| Voyage 3.5 | API | 1024 | Excellent | Good | No |
| Jina v5-text | 200M-600M | 1024 | Good | SOTA | Docker |
| BGE-M3 | 567M | 1024 | Good | 100+ | Ollama |

**Decision: qwen3-embedding** via Ollama. Actual dims = 4096 (not 1024 as initially estimated).

### Architecture (Implemented)

```
Level 1: Ollama CPU (primary)
  -> qwen3-embedding (4.7 GB, ~6 GB RAM)
  -> ~4-5s per embedding on CPU, $0
  -> Instruction prompts for BSL code search

Level 2: SQLite FTS5 (emergency fallback)
  -> Text search, ~5ms, $0
  -> Already implemented in Phase 45
```

### Performance

- Single embed: ~6.7s on CPU
- Batch of 5: ~21.5s on CPU (~4.3s/embed)
- Full reindex (34,936 chunks): ~42h on CPU — run overnight
- Sample reindex (500 chunks): ~35 min

### Implementation

1. ✅ `ollama pull qwen3-embedding` (4.7 GB)
2. ✅ Embedding provider: `src/bsl/semantic_search/services/qwen3_embedding.py`
   - Qwen3EmbeddingService with singleton, instruction prompts, batch support
3. ✅ Qdrant collection: `bsl_code_v3` (4096d, cosine)
4. ✅ Instruction prompts for BSL:
   - Query: "Instruct: Find BSL code procedure or function\nQuery: ..."
   - Document: "Instruct: BSL code module from 1C Enterprise\nDocument: ..."
5. ✅ Reindex script: `scripts/reindex_bsl_qwen3.py` (--limit for sampling)
6. ✅ Eval script updated: `scripts/eval_bsl_search.py` (--mode qwen3)
7. 🔄 A/B comparison via eval dataset (Phase 58)

### Expected: +55% recall, significantly better on RU queries

### Cost: $0 (Ollama CPU only) | Effort: 2-3 days

---

## Phase 61: BSL Call Graph and Dependency Analysis (Priority: HIGH) — COMPLETE

**Goal:** Build call graph between modules for impact analysis and navigation.

**Status:** COMPLETE. 33,074 symbols, 78,707 calls, 3,475 dead code candidates. Build time: 29.6s.

### Implementation

1. `src/bsl/call_graph/store.py` — CallGraphStore (SQLite, WAL mode)
   - `add_module(BSLModule)` — batch insert symbols + calls
   - `callers_of(name)` / `callees_of(symbol_id)` — direct graph queries
   - `impact_analysis(name, depth=3)` — transitive callers via BFS
   - `dead_code()` — exported symbols never called (found 3,475)
   - `stats()` — symbol/call/module counts
2. `scripts/build_call_graph.py` — CLI builder (--project, --clear)
3. Database: `cache/bsl_call_graph.db`
4. MCP tools planned for Phase 64

### Inspiration
- codebase-memory-mcp (github.com/DeusData) - 64 langs, tree-sitter, Louvain clustering
- code-graph-mcp (github.com/entrepeneur4lyf) - PageRank, ast-grep
- Axon (github.com/harshkedia177) - graph + embeddings + communities

### Data Schema

```sql
CREATE TABLE symbols (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    module_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    is_export BOOLEAN,
    params TEXT,
    doc_comment TEXT
);

CREATE TABLE calls (
    id INTEGER PRIMARY KEY,
    caller_id TEXT REFERENCES symbols(id),
    callee_name TEXT NOT NULL,
    callee_module TEXT,
    line_number INTEGER,
    call_type TEXT
);

CREATE TABLE module_metadata (
    path TEXT PRIMARY KEY,
    module_type TEXT,
    subsystem TEXT,
    object_type TEXT,
    object_name TEXT
);
```

### Effort: 5-7 days

---

## Phase 62: 1C Object Knowledge Graph (Priority: MEDIUM) — COMPLETE (folder-based)

**Goal:** Metadata object graph from EDT folder structure.

**Status:** Folder-based extraction complete. 959 objects discovered. XML parsing deferred.

### Results

| Type | Count |
|------|-------|
| CommonModule | 424 |
| InformationRegister | 162 |
| Catalog | 90 |
| CommonForm | 79 |
| DataProcessor | 77 |
| Constant | 42 |
| Report | 32 |
| Document | 25 |
| Enum | 12 |
| Subsystem | 11 |

### Implementation

1. `src/bsl/knowledge_graph/metadata_extractor.py` — MetadataExtractor
   - `extract_objects()` — scan EDT folders, return ObjectInfo list
   - `get_objects_by_type(type)` / `get_object_by_name(name)`
   - `get_object_modules(name)` — BSL file paths for an object
   - `stats()` — counts by type
2. ObjectInfo dataclass: name, object_type, path, modules, forms
3. Supports both English and Russian EDT folder names

### Deferred
- XML parsing for attributes, table parts, movements
- MCP tools (Phase 64)

### Effort: 0.5 days (folder-based)

---

## Phase 63: Contextual BSL Search (Priority: MEDIUM) — COMPLETE

**Goal:** Add module context to each chunk during indexing. +15-20% retrieval quality.

### Implementation

`src/bsl/parser/context_enricher.py` — BSLContextEnricher class.

Each chunk gets context prefix prepended to content with object type, forms list,
callers/dependencies from call graph. Metadata enriched with `object_type`,
`object_name`, `forms`, `caller_count`, `cross_module_deps`.

Integration:
- `scripts/reindex_bsl_qwen3.py` — `--no-context` flag to disable
- Uses MetadataExtractor (Phase 62) + CallGraphStore (Phase 61)
- Path-based fallback when extractor not available
- Object resolution cached per module_path

### Effort: 0.5 days

---

## Phase 64: BSL Code Intelligence MCP (Priority: MEDIUM) — COMPLETE

**Goal:** Unified MCP server: bsl-code-intelligence.

### Implementation

4 new tools added to existing `src/bsl/semantic_search/mcp.py` (FastMCP server):

| Tool | Status | Description |
|------|--------|------------|
| bsl_call_graph | DONE | Callers/callees query with direction param |
| bsl_impact_analysis | DONE | BFS transitive callers, configurable depth |
| bsl_dead_code | DONE | 3,475 exported-but-never-called symbols found |
| bsl_object_info | DONE | EDT folder metadata + call graph enrichment |

Deferred (require Phase 63 or separate effort):
- bsl_related_objects, bsl_code_context, bsl_similar_code, bsl_complexity, bsl_duplicates

### Key decisions
- Tools integrated into existing MCP server (not separate server)
- Auto-detection of EDT project root under `src/projects/configuration/`
- Lazy singletons for CallGraphStore and MetadataExtractor
- Partial name matching with ambiguity handling in bsl_object_info

### Effort: 0.5 days (4 core tools)

---

## Phase 65: Hybrid Reranking BSL (Priority: MEDIUM)

**Goal:** 5-stage pipeline optimized for BSL.

```
Query -> BM25 top-50 (5ms) -> Vector top-50 (50ms) -> RRF top-20
      -> Call Graph Boost (PageRank) -> LLM Reranker top-5 (1-3s)
```

### Effort: 2-3 days

---

## Phase 66: BSL Coding Assistant (Priority: HIGH)

**Goal:** Improve BSL code generation via project context.

### Tasks

1. Auto-context hook - on BSL request, auto-fetch:
   - Similar procedures from index
   - Related objects
   - Module dependencies
2. Code Style Extractor - rules from existing code
3. Template Generator - templates by module type

### Effort: 3-5 days

---

## Phase 67: External Tools Integration (Priority: LOW)

Integration candidates: claude-hud, codebase-memory-mcp, parry, sonar-bsl-plugin, bsl-language-server.

### Effort: 2-4 days

---

## Summary Table

| Phase | Name | Priority | Days | Depends On | Effect |
|-------|------|----------|------|------------|--------|
| **58** | Eval Dataset and Baseline | CRITICAL | 1-2 | -- | Measurement |
| **59** | AST-based BSL Indexing | CRITICAL | 3-5 | -- | +44% recall |
| **60** | Code-Optimized Embeddings | HIGH | 2-3 | 58 | +55% recall |
| **61** | Call Graph and Dependencies | HIGH | 5-7 | 59 | New capability |
| **62** | 1C Object Knowledge Graph | MEDIUM | 4-6 | -- | Context |
| **63** | Contextual BSL Search | MEDIUM | 2-3 | 59,60,62 | +15-20% recall |
| **64** | Code Intelligence MCP | MEDIUM | 3-4 | 59,61,62 | Unified API |
| **65** | Hybrid Reranking BSL | MEDIUM | 2-3 | 60 | +10-15% precision |
| **66** | Coding Assistant | HIGH | 3-5 | 59,61,62 | Code quality |
| **67** | External Tools | LOW | 2-4 | -- | Ecosystem |

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
