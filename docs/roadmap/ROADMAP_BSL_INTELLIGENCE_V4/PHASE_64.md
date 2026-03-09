# Phase 64: BSL Code Intelligence MCP

**Priority:** MEDIUM | **Effort:** 3-4 days | **Depends on:** Phases 59, 61, 62 | **Effect:** Unified API

**Goal:** Unified MCP server: bsl-code-intelligence — single entry point for all code analysis tools.

---

## Problem Statement

After Phases 59-63, multiple capabilities exist in separate modules:
- Symbol search (Phase 59)
- Call graph (Phase 61)
- Object metadata (Phase 62)
- Contextual search (Phase 63)

Without a unified MCP server, Claude must know which tool to call for each query type. A single server with smart routing simplifies usage.

---

## Tools

| Tool | Description | Depends On | Latency |
|------|------------|------------|---------|
| bsl_search_symbols | Search by symbol name/description | Phase 59 | <50ms |
| bsl_call_graph | Call graph (callers/callees) | Phase 61 | <10ms |
| bsl_impact_analysis | Impact analysis for changes | Phase 61 | <100ms |
| bsl_dead_code | Find unused exported procedures | Phase 61 | <500ms |
| bsl_object_info | Object metadata (attrs, tables) | Phase 62 | <10ms |
| bsl_related_objects | Related objects graph | Phase 62 | <10ms |
| bsl_code_context | Full coding context for a module | Phase 63 | <50ms |
| bsl_similar_code | Find similar procedures | Phases 59, 60 | <100ms |
| bsl_complexity | Code complexity metrics | Phase 59 | <50ms |
| bsl_duplicates | Find duplicate code blocks | Phase 60 | <200ms |

---

## Tasks

### Task 64.1: MCP Server Structure

#### 64.1.1 Server Setup
- Single MCP server: `bsl-code-intelligence`
- Registered in `.mcp/bsl.json`
- Stdio transport (standard for Claude Code)

#### 64.1.2 Tool Registry
- Each tool as a separate module in `src/bsl/mcp_server/tools/`
- Common response format: `{status, data, metadata}`
- Error handling: graceful errors with helpful messages

#### 64.1.3 Shared Infrastructure
- Database connections pool (SQLite call graph + knowledge graph)
- Qdrant client (for embedding-based tools)
- Caching layer (LRU for frequent queries)

### Task 64.2: Search Tools

#### 64.2.1 bsl_search_symbols
- Input: query (text), filters (module_type, is_export, subsystem)
- Search: Qdrant vector search + FTS5 text search
- Output: ranked list of symbols with metadata
- Options: top_k, search_type (vector/text/hybrid)

#### 64.2.2 bsl_similar_code
- Input: symbol_id or code snippet
- Method: embed input, find nearest neighbors in Qdrant
- Output: similar procedures with similarity scores
- Use case: "find code similar to this procedure"

### Task 64.3: Analysis Tools

#### 64.3.1 bsl_call_graph
- Input: module, method, direction (in/out/both), depth
- Query: SQLite call graph (Phase 61)
- Output: graph as adjacency list + metadata per node

#### 64.3.2 bsl_impact_analysis
- Input: module, method (or object_type, object_name)
- Algorithm: BFS traversal of call graph, depth-limited
- Output: affected modules sorted by distance, with paths

#### 64.3.3 bsl_dead_code
- Input: scope (subsystem, module_type), exclude_patterns
- Algorithm: find exported symbols with 0 external callers
- Filter: exclude event handlers, test modules
- Output: list of unused symbols with location

#### 64.3.4 bsl_complexity
- Input: module (or symbol_id)
- Metrics: cyclomatic complexity, lines of code, nesting depth
- Output: per-symbol metrics + module-level aggregation

#### 64.3.5 bsl_duplicates
- Input: min_similarity (default 0.95), scope
- Method: pairwise cosine similarity on embeddings
- Output: pairs of similar procedures with similarity score

### Task 64.4: Metadata Tools

#### 64.4.1 bsl_object_info
- Input: object name
- Source: knowledge graph (Phase 62)
- Output: type, attributes, table parts, movements, related modules

#### 64.4.2 bsl_related_objects
- Input: object name, depth, relation_types
- Source: knowledge graph (Phase 62)
- Output: related objects graph

#### 64.4.3 bsl_code_context
- Input: module name (or symbol_id)
- Aggregates: module info + dependencies + call graph + related objects
- Output: full coding context for Claude
- Use case: auto-context when writing BSL code

### Task 64.5: Testing & Documentation

#### 64.5.1 Integration Tests
- Test each tool with real data
- Test error cases (missing module, invalid params)
- Test performance (all tools within latency targets)

#### 64.5.2 Tool Descriptions
- Clear descriptions for Claude to understand when to use each tool
- Input/output JSON schemas
- Usage examples

---

## Deliverables

- [ ] `src/bsl/mcp_server/server.py` — unified MCP server
- [ ] `src/bsl/mcp_server/tools/search_symbols.py`
- [ ] `src/bsl/mcp_server/tools/similar_code.py`
- [ ] `src/bsl/mcp_server/tools/call_graph.py`
- [ ] `src/bsl/mcp_server/tools/impact_analysis.py`
- [ ] `src/bsl/mcp_server/tools/dead_code.py`
- [ ] `src/bsl/mcp_server/tools/complexity.py`
- [ ] `src/bsl/mcp_server/tools/duplicates.py`
- [ ] `src/bsl/mcp_server/tools/object_info.py`
- [ ] `src/bsl/mcp_server/tools/related_objects.py`
- [ ] `src/bsl/mcp_server/tools/code_context.py`
- [ ] Updated `.mcp/bsl.json` with new server
- [ ] Integration tests
- [ ] Tool documentation

---

## Acceptance Criteria

1. All 10 tools registered and accessible from Claude Code
2. Each tool meets latency targets (see table above)
3. Graceful error handling (no crashes on bad input)
4. Tool descriptions clear enough for Claude to route correctly
5. Integration tests pass for all tools
